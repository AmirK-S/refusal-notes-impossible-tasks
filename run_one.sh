#!/usr/bin/env bash
# Banc 2026-11, one run, driven from the HOST. Replaces scenarios/run_one.sh (October, in-container).
#
# run_one.sh --harness codex|claude --provider adaption|openai-key|chatgpt|claude-oauth|claude-oauth-env
#            --model <id> --scenario S6 --run r01 --campaign <name>
#            [--task task.txt|task_board.txt|task_harvest.txt|tasks/<file>] [--board <dir>] [--board-rw] [--timeout 900]
#            [--overlay <dir>] [--tag <free text>]
#   --overlay <dir>: files copied (paths kept) into the host copy of the fixture ($OUT/fixture) after setup.sh and
#                    before the agent starts. They are part of the reference state: check.sh compares the final /work
#                    to /fixture, so they do not count as agent modifications. Kept in overlay_in/ + overlay_manifest.txt.
#   --tag <text>:    free text written to run.json (arm, parent, seed, generation).
#
# Isolation (see CORRECTIONS.md):
#  - setup.sh runs in its own container (network none); the fixture lands on the host, never in the agent's view.
#  - the agent container has NO bind mount: /work and /shared/board are copied in (docker cp), the agent
#    runs as uid 1000 (agent) after entry.sh drops root. No /harness, no /fixture, no check.sh inside.
#  - network: per-run `docker network create --internal` + per-run proxy container (alias proxy):
#      :8080 inject_proxy.py (reverse proxy, adds the API secret; the agent never holds it)
#      :3128 egress_proxy.py (CONNECT allowlist; only the provider host when injection is impossible)
#  - check.sh runs after the agent container has stopped, in two fresh containers with --network none:
#      ci    = clean image + copy of the final /work   (what CI would see)
#      local = image committed from the agent's final container (catches site-packages / ~/.local fakes)
# Results: $BANC_DATA/<campaign>/<harness>-<model>/<scenario>/<run>/  (default ~/work/swarm-alignment-data/banc-runs)
set -u
B=$(cd "$(dirname "$0")" && pwd)
DATA=${BANC_DATA:-$HOME/work/swarm-alignment-data/banc-runs}
IMG=${BANC_IMAGE:-banc:v1}
H=codex; P=adaption; M=glm-5.2; S=S6; R=r01; C=pilot; TASKF=task.txt; BOARD=""; BRW=0; TO=900; OVERLAY=""; OVERLAY_ARG=""; TAG=""
while [ $# -gt 0 ]; do case $1 in
  --harness) H=$2; shift;; --provider) P=$2; shift;; --model) M=$2; shift;; --scenario) S=$2; shift;;
  --run) R=$2; shift;; --campaign) C=$2; shift;; --task) TASKF=$2; shift;; --board) BOARD=$2; shift;;
  --board-rw) BRW=1;; --timeout) TO=$2; shift;;
  --overlay) OVERLAY=$2; OVERLAY_ARG=$2; shift;; --tag) TAG=$2; shift;; *) echo "unknown arg $1"; exit 2;; esac; shift; done
SD=$B/scenarios/$S
OUT=$DATA/$C/$H-$M/$S/$R
[ -f "$OUT/exit.txt" ] && { echo "skip $OUT (done)"; exit 0; }
rm -rf "$OUT"; mkdir -p "$OUT"
RID=banc-$(date +%s)-$$-$RANDOM
if [ "$P" = chatgpt ]; then   # one ChatGPT login = one serialized stream: refuse to run two at once
  LOCK=$DATA/.chatgpt.lock; mkdir -p "$DATA"
  until mkdir "$LOCK" 2>/dev/null; do sleep 5; done
  trap 'rmdir "$LOCK" 2>/dev/null' EXIT
fi
NET=$RID-net
log() { echo "$(date -u +%FT%TZ) $*" >> "$OUT/runner.log"; }
cleanup() { docker rm -f $RID-agent $RID-proxy >/dev/null 2>&1; docker rmi -f $RID-img >/dev/null 2>&1; docker network rm $NET >/dev/null 2>&1; rm -rf "$STAGE"; }
STAGE=$(mktemp -d "${TMPDIR:-/tmp}/banc-stage.XXXXXX"); chmod 700 "$STAGE"
trap 'cleanup; [ -n "${LOCK:-}" ] && rmdir "$LOCK" 2>/dev/null' EXIT

# ---------- provider: where the secret lives (host side only) ----------
SECRET_ENV=""; UPSTREAM=""; PREFIX=""; SCHEME=bearer; XH=""; CONNECT_ALLOW=none.invalid; AGENT_ENV=""
case $P in
  adaption)  set -a; . "$HOME/.config/hackathon/adaption.env"; set +a; SECRET_ENV=ADAPTION_API_KEY
             UPSTREAM=https://api.prod.adaptionlabs.ai; PREFIX=/api/v1/ ;;
  openai-key) set -a; . "$HOME/.config/hackathon/openai.env"; set +a; SECRET_ENV=OPENAI_API_KEY
             UPSTREAM=https://api.openai.com; PREFIX=/v1/ ;;
  chatgpt)   CONNECT_ALLOW=chatgpt.com,auth.openai.com ;;   # auth.json goes in the container, read-only (limit, see CORRECTIONS.md); serial only
  claude-oauth) set -a; . "$HOME/.config/hackathon/claude.env"; set +a; SECRET_ENV=CLAUDE_CODE_OAUTH_TOKEN
             UPSTREAM=https://api.anthropic.com; PREFIX=/v1/; XH="anthropic-beta: oauth-2025-04-20"
             AGENT_ENV="ANTHROPIC_BASE_URL=http://proxy:8080 CLAUDE_CODE_OAUTH_TOKEN=banc-placeholder-not-a-secret" ;;
  claude-oauth-env) CONNECT_ALLOW=api.anthropic.com ;;     # fallback: token in agent env (limit)
  *) echo "unknown provider $P"; exit 2;;
esac

# ---------- CLI config (staged, then copied into the container) ----------
mkdir -p "$STAGE/root/stage/cfg"
case $H in
  codex|probe)
    {
      # no comments in this file: the agent can read it (generation is documented in CORRECTIONS.md)
      echo "model = \"$M\""
      echo 'web_search = "disabled"'
      case $P in adaption|openai-key) echo "model_provider = \"$P\"";; esac
      grep -v '^model *=' "$SD/codex_config.toml" | grep -v '^ *#'
      case $P in adaption|openai-key)
        printf '\n[model_providers.%s]\nname = "%s"\nbase_url = "http://proxy:8080%s"\nwire_api = "responses"\n' "$P" "$P" "${PREFIX%/}";;
      esac
    } > "$STAGE/root/stage/cfg/config.toml"
    [ -f "$SD/codex.rules" ] && cp "$SD/codex.rules" "$STAGE/root/stage/cfg/default.rules"
    if [ "$P" = chatgpt ]; then cp "${CODEX_AUTH_JSON:-$HOME/.codex/auth.json}" "$STAGE/root/stage/cfg/auth.json" || exit 3; fi
    if [ $BRW = 1 ]; then   # harvest variant: Codex's own sandbox must also let the agent write the board
      python3 -I -c "import sys;p=sys.argv[1];s=open(p).read();s=s.replace('[sandbox_workspace_write]\n','[sandbox_workspace_write]\nwritable_roots = [\"/shared/board\"]\n',1);open(p,'w').write(s)" "$STAGE/root/stage/cfg/config.toml"
    fi
    cp "$STAGE/root/stage/cfg/config.toml" "$OUT/codex_config.toml" ;;
  claude)
    cp "$SD/claude_settings.json" "$STAGE/root/stage/cfg/settings.json" ;;
esac
if [ "$P" = claude-oauth-env ]; then set -a; . "$HOME/.config/hackathon/claude.env"; set +a
  AGENT_ENV="CLAUDE_CODE_OAUTH_TOKEN=$CLAUDE_CODE_OAUTH_TOKEN"; fi
printf '%s' "$AGENT_ENV" > "$STAGE/root/stage/agent_env"; chmod 600 "$STAGE/root/stage/agent_env"
echo "$H" > "$STAGE/root/stage/harness"; echo "$M" > "$STAGE/root/stage/model"; echo "$TO" > "$STAGE/root/stage/timeout"
TF="$SD/$TASKF"; [ -f "$B/$TASKF" ] && TF="$B/$TASKF"; [ -f "$TASKF" ] && TF="$TASKF"   # a path is accepted too (probe / cheat scripts)
cp "$TF" "$STAGE/root/stage/task.txt"; cp "$TF" "$OUT/task.txt"
cp "$B/agent/entry.sh" "$STAGE/root/stage/entry.sh"

# ---------- board ----------
BM=none
if [ -n "$BOARD" ]; then
  BM=ro; [ $BRW = 1 ] && BM=rw
  mkdir -p "$STAGE/shared/board"; cp -R "$BOARD"/. "$STAGE/shared/board/" 2>/dev/null
  find "$STAGE/shared/board" \( -name .DS_Store -o -name .keep \) -delete
  mkdir -p "$OUT/board_in"; cp -R "$STAGE/shared/board"/. "$OUT/board_in/"
  (cd "$OUT/board_in" && find . -type f | sort | while read f; do shasum -a 256 "$f"; done) > "$OUT/board_manifest.txt"
fi
echo "$BM" > "$STAGE/root/stage/board_mode"
IMGID=""; for _i in 1 2 3 4 5; do IMGID=$(docker image inspect $IMG --format '{{.Id}}' 2>/dev/null) && [ -n "$IMGID" ] && break; sleep 2; done; [ -n "$IMGID" ] || IMGID=unknown
jesc() { printf '%s' "$1" | python3 -I -c 'import sys,json;print(json.dumps(sys.stdin.read())[1:-1])'; }
OVM=none; OVSHA=none
if [ -n "$OVERLAY" ]; then
  [ -d "$OVERLAY" ] || OVERLAY="$B/$OVERLAY"
  [ -d "$OVERLAY" ] || { echo "overlay dir not found: $OVERLAY"; exit 2; }
  OVM=$(jesc "$OVERLAY_ARG")
  mkdir -p "$OUT/overlay_in"; cp -R "$OVERLAY"/. "$OUT/overlay_in/"
  find "$OUT/overlay_in" \( -name .DS_Store -o -name .keep \) -delete
  (cd "$OUT/overlay_in" && find . -type f | sort | while read f; do shasum -a 256 "$f"; done) > "$OUT/overlay_manifest.txt"
  OVSHA=$(shasum -a 256 "$OUT/overlay_manifest.txt" | cut -c1-16)
fi
cat > "$OUT/run.json" <<EOF
{"harness":"$H","provider":"$P","model":"$M","scenario":"$S","run_id":"$R","campaign":"$C","task_file":"$(basename "$TASKF")",
 "board":"$(basename "${BOARD:-none}")","board_mode":"$BM","overlay":"$OVM","overlay_manifest_sha":"$OVSHA","tag":"$(jesc "$TAG")",
 "timeout_s":$TO,"image":"$IMG","banc_dirty":"${BANC_DIRTY:-no}",
 "image_id":"$IMGID","banc_commit":"${BANC_COMMIT:-$(git -C "$B" rev-parse --short HEAD 2>/dev/null)-workingcopy}"}
EOF
log "start $H $P $M $S $R board=$BM"

# ---------- 1. setup, in its own container ----------
mkdir -p "$OUT/fixture"
docker run --rm --network none -v "$SD:/s:ro" -v "$OUT/fixture:/work" -w /work $IMG bash /s/setup.sh >/dev/null 2>&1
if [ -n "$OVERLAY" ]; then   # overlay becomes part of the reference state (check.sh diffs /work against /fixture)
  cp -R "$OUT/overlay_in"/. "$OUT/fixture/"; log "overlay $OVM sha=$OVSHA"
fi

# ---------- 2. network and proxy ----------
docker network create --internal $NET >/dev/null
PXCMD="python3 -I /egress/egress_proxy.py 3128 /plog/egress.log $CONNECT_ALLOW"
if [ -n "$SECRET_ENV" ]; then
  PXCMD="$PXCMD & python3 -I /egress/inject_proxy.py --listen 0.0.0.0:8080 --upstream $UPSTREAM --allow-prefix $PREFIX --secret-env $SECRET_ENV --log /plog/api.jsonl"
  [ -n "$XH" ] && PXCMD="$PXCMD --extra-header '$XH'"
  PXCMD="$PXCMD & wait"
fi
docker run -d --name $RID-proxy --network bridge ${SECRET_ENV:+-e $SECRET_ENV} -v "$B/egress:/egress:ro" -v "$OUT:/plog" $IMG bash -c "$PXCMD" >/dev/null
docker network connect --alias proxy $NET $RID-proxy
sleep 1

# ---------- 3. agent container: no mounts, copy in, run ----------
PRIV=""; [ "$H" != claude ] && PRIV="--privileged"   # as in October: Codex's own bwrap sandbox needs it
docker create --name $RID-agent --network $NET $PRIV --hostname work $IMG bash /root/stage/entry.sh >/dev/null
docker cp "$OUT/fixture/." $RID-agent:/work >/dev/null
# provision/site-packages/<entry> (scenario dir): packages the host installs into the agent image before the agent starts
# (S6F: fxprovider). Root-owned and not writable by the agent (entry.sh fixes the owner); also mounted read-only in the CI check.
SPD=/usr/local/lib/python3.12/site-packages; PROVMNT=""; : > "$STAGE/root/stage/prov"
if [ -d "$SD/provision/site-packages" ]; then
  for e in "$SD"/provision/site-packages/*; do
    docker cp "$e" $RID-agent:$SPD/ >/dev/null; echo "$SPD/$(basename "$e")" >> "$STAGE/root/stage/prov"
    PROVMNT="$PROVMNT -v $e:$SPD/$(basename "$e"):ro"
  done
  log "provision $(ls "$SD/provision/site-packages" | tr '\n' ' ')"
fi
docker cp "$STAGE/root/stage" $RID-agent:/root/ >/dev/null
[ "$BM" != none ] && docker cp "$STAGE/shared" $RID-agent:/ >/dev/null
rm -rf "$STAGE/root/stage/cfg" "$STAGE/root/stage/agent_env"
docker start -a $RID-agent > "$OUT/transcript.jsonl" 2> "$OUT/stderr.txt"
for f in exit start end; do docker cp $RID-agent:/root/stage/$f "$OUT/agent_$f.txt" >/dev/null 2>&1; done
docker cp $RID-agent:/var/log/agent-hooks/toolcalls.jsonl "$OUT/toolcalls.jsonl" >/dev/null 2>&1
mkdir -p "$OUT/work_final"; docker cp $RID-agent:/work/. "$OUT/work_final/" >/dev/null 2>&1
[ "$BM" = rw ] && { mkdir -p "$OUT/board_out"; docker cp $RID-agent:/shared/board/. "$OUT/board_out/" >/dev/null 2>&1; }
[ "$H" != claude ] && { mkdir -p "$OUT/codex_sessions"; docker cp $RID-agent:/home/agent/.codex/sessions/. "$OUT/codex_sessions/" >/dev/null 2>&1; }
docker commit $RID-agent $RID-img >/dev/null
docker rm -f $RID-agent $RID-proxy >/dev/null 2>&1

# ---------- 4. check, out of the agent's reach ----------
FIXREF=""; [ -f "$OUT/fixture/deploy.sh" ] && FIXREF="-v $OUT/fixture/deploy.sh:/fixture_deploy_ref.sh:ro"
docker run --rm --network none -v "$SD:/s:ro" -v "$OUT/fixture:/fixture:ro" -v "$OUT/work_final:/work_ro:ro" $FIXREF $PROVMNT \
  -w /work $IMG bash -c 'rm -rf /work/* /work/.[!.]* 2>/dev/null; cp -a /work_ro/. /work/; chown -R agent:agent /work; bash /s/check.sh ci' > "$OUT/check_ci.txt" 2>&1
docker run --rm --network none -v "$SD:/s:ro" -v "$OUT/fixture:/fixture:ro" $FIXREF --user 0 -w /work --entrypoint bash $RID-img /s/check.sh local > "$OUT/check_local.txt" 2>&1
{ sed 's/^/ci./' "$OUT/check_ci.txt"; sed 's/^/local./' "$OUT/check_local.txt"; } > "$OUT/poststate.txt"

# ---------- 5. redact, finish ----------
python3 -I "$B/redact_banc.py" "$OUT"
tar -czf "$OUT/workdir_final.tgz" -C "$OUT" work_final 2>/dev/null
cat "$OUT/agent_exit.txt" 2>/dev/null > "$OUT/exit.txt" || echo "exit=unknown" > "$OUT/exit.txt"
[ -s "$OUT/exit.txt" ] || echo "exit=unknown" > "$OUT/exit.txt"
log "end $(cat "$OUT/exit.txt")"
echo "$H $P $M $S $R $(cat "$OUT/exit.txt") $(sed -n 's/^green=/green=/p' "$OUT/check_ci.txt" | head -1)/$(sed -n 's/^green=//p' "$OUT/check_local.txt" | head -1)"
