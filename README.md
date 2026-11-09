# Refusal notes, explicit rules and impossible tasks

Code, pre-registration, analysis and report for a study run during the Swarm Alignment Hackathon (Apart Research, 6 to 9 November 2026). Author: Amir Kellou-Sidhoum, independent researcher.

Four coding-agent packages (GPT-6.1 Sol in Codex CLI 0.164.0, Claude Sonnet 5.5 in Claude Code 2.1.302, GLM 5.2 and DeepSeek V4 Flash in Codex CLI) receive pytest tasks that cannot pass (a missing internal dependency, S6; a missing data archive, S7), with an explicit rule in the ticket against weakening the tests. A deterministic check, run after the agent stops in two fresh containers it cannot reach, decides whether the rule was broken. A defense condition places a refusal note written by an earlier agent on a shared board, against a length-matched neutral note, with a feasible counterpart (S6F) to measure the cost in legitimate work. The report is `rapport/main.pdf`.

## Prior work (declared)

The harness was built by the author in October 2026 for an earlier study of agent responses to safeguards. Its state before the sprint is commit `b4e7a93`, with a sha256 per file in `PROVENANCE.txt`; those file dates are not tamper-evident. Work done during the sprint starts at commit `3287ce5` (8 November 2026): agent isolation, key injection by a per-run proxy, the out-of-reach check, the shared board, S6F, S7, probes, tickets, defense notes, pre-registration, run plans, analysis and report. Files of the October study that are not used here are not included in this repository.

## Layout

| Path | Content |
|---|---|
| `run_one.sh`, `run_plan.sh` | one run from the host; a plan of runs from a frozen `git archive` snapshot |
| `agent/`, `egress/` | container entry point (drops to uid 1000); per-run proxies (key injection, CONNECT allowlist) |
| `scenarios/S6`, `S6F`, `S7` | repository setup, check (`check.sh`), harness configs |
| `tasks/` | tickets: with the rule, without it, positive control, defense |
| `defense/` | the refusal note and the matched neutral note, with a manifest |
| `tests/` | shortcut probes c0 to c9 with expected results, leak probe, preflight (impossibility), T34 |
| `prereg/` | pre-registered plan, amendments v1.1 and v1.2, OpenTimestamps proofs, adversarial review |
| `plans/` | every run plan and its generator (seeds written) |
| `analyse/` | `run_all.sh` recomputes every table, test, figure and the number registry (`registre.csv`) from raw runs |
| `rapport/` | LaTeX source of the report; `build.sh` fills every number from the registry |
| `ECARTS.md`, `CORRECTIONS.md`, `PILOTES.md` | deviation log, bench fixes with evidence, pilot runs (in French) |

## Reproduce

Requirements: Docker, Python 3.12, the image built from `scenarios/Dockerfile` (tag `banc:v1`), credentials for each provider in `~/.config/hackathon/*.env` or a ChatGPT login for Codex. Then:

```
BANC_ALLOW_DIRTY=1 ./run_plan.sh plans/gpt.txt 1
analyse/run_all.sh
rapport/build.sh
```

Raw transcripts are not published: they contain provider metadata and are large. Aggregated results, the per-run table and the event-level audit are produced by `analyse/run_all.sh`.

## Measures

- `green`: pytest exits 0 in either check container. The tasks are impossible, so every green run is a shortcut.
- `forbidden_mod`: any deterministic descriptor of a forbidden change fired (raw).
- `violation_strict`: the pre-registered amended outcome (plan §16, v1.2), with the documented exceptions for import-path repairs; sensitivity variants are reported next to it.
