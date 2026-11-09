"""Builds a read-only mirror of the finished runs, so that extract_banc.py (used unchanged) never writes into the raw data.
Usage: python3 -I analyse/mirror.py <banc-runs dir> <mirror dir> <campaign> [<campaign> ...]
Data freeze (deviation 17): with FREEZE_AT=<ISO date-time with offset, e.g. 2026-11-09T05:30:00+01:00> in the environment, a run
counts as finished only if its exit.txt was written at or before that instant; later runs are listed as unfinished at the freeze.
For every run folder <campaign>/<package>/<scenario>/<run>/ that has exit.txt (finished), the mirror gets a real folder
whose entries are symlinks to the raw entries (final_message.txt excepted: extract_banc.py writes it, in the mirror).
extract_banc.py also writes judge/ and monitor/ next to the package folders: in the mirror too. Runs without exit.txt
are in flight (or were killed) and are listed in <mirror>/<campaign>/_unfinished.txt.
The mirror is rebuilt from scratch at each call (idempotent)."""
import os, sys, shutil, glob
from datetime import datetime
FREEZE = os.environ.get("FREEZE_AT", "")
FREEZE_TS = datetime.fromisoformat(FREEZE).timestamp() if FREEZE else None

src, dst = sys.argv[1], sys.argv[2]
for camp in sys.argv[3:]:
    m = os.path.join(dst, camp)
    if os.path.isdir(m):
        shutil.rmtree(m)
    os.makedirs(m)
    unfinished, done = [], 0
    for rd in sorted(glob.glob(os.path.join(src, camp, "*", "*", "*"))):
        top = os.path.relpath(rd, os.path.join(src, camp)).split(os.sep)[0]
        if not os.path.isdir(rd) or top in ("judge", "monitor") or top.startswith("_"):
            continue   # folders starting with "_" (e.g. _quota_d, deviation 12) hold runs set aside by the orchestrator
        rel = os.path.relpath(rd, os.path.join(src, camp))
        ex = os.path.join(rd, "exit.txt")
        if not os.path.exists(ex) or (FREEZE_TS is not None and os.path.getmtime(ex) > FREEZE_TS):
            unfinished.append(rel)
            continue
        md = os.path.join(m, rel)
        os.makedirs(md)
        for e in os.listdir(rd):
            if e == "final_message.txt":
                continue
            os.symlink(os.path.join(rd, e), os.path.join(md, e))
        done += 1
    aside = []   # runs moved by the orchestrator into <campaign>/_<name>/ (deviations 12, 14, 15): listed, never analysed
    for sd in sorted(glob.glob(os.path.join(src, camp, "_*"))):
        for rj in sorted(glob.glob(os.path.join(sd, "**", "run.json"), recursive=True)):
            try:
                import json
                j = json.load(open(rj))
                ident = f"{j['harness']}-{j['model']}/{j['scenario']}/{j['run_id']}"
            except Exception:
                ident = os.path.relpath(os.path.dirname(rj), sd)
            aside.append(f"{os.path.basename(sd)}\t{ident}\t{os.path.relpath(os.path.dirname(rj), os.path.join(src, camp))}")
    with open(os.path.join(m, "_set_aside.txt"), "w") as f:
        f.write("".join(a + "\n" for a in aside))
    with open(os.path.join(m, "_unfinished.txt"), "w") as f:
        f.write("".join(u + "\n" for u in unfinished))
    open(os.path.join(m, "_freeze.txt"), "w").write(FREEZE + "\n")
    print(f"{camp}: {done} finished runs mirrored, {len(unfinished)} unfinished, {len(aside)} set aside")
