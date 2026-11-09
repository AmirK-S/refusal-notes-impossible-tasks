"""Audit material for each raw descriptor of forbidden_mod (deterministic; the reading of the material is done by a person and
written in analyse/AUDIT-DESCRIPTEURS.md).
Usage: python3 -I analyse/audit_descriptors.py <mirror dir> <out dir> <campaign> [...]
Outputs in <out dir>:
  descriptor_counts.csv   descriptor, campaign, package, scenario, fired, finished runs of the group
  <descriptor>.md         the inspected cases: selection rule, written before reading = for each (campaign, package, scenario)
                          group in key order, the first run where the descriptor fires; then further runs in key order until
                          5 cases (all cases when there are fewer). For each: descriptors, the check lines that name files,
                          and the unified diff fixture -> work_final of every changed file (60 lines max per file).
"""
import csv, difflib, filecmp, glob, json, os, sys

CHECK_KEYS = ("files_changed", "conftest", "pytest_config", "shadow_pytest", "fxprovider_paths", "fxprovider_importable_env",
              "fxprovider_importable_repo", "fxprovider_file_repo", "fxprovider_file_env", "shortcut_markers", "env_files_new",
              "live_test_outcome", "archive_paths", "customization_paths", "new_py_files", "pytest", "green")


def kv(p):
    d = {}
    if os.path.exists(p):
        for l in open(p, errors="replace"):
            if "=" in l:
                k, v = l.rstrip("\n").split("=", 1); d.setdefault(k, v)
    return d


def tree(root):
    out = {}
    for dp, dn, fn in os.walk(root):
        dn[:] = [x for x in dn if x not in ("__pycache__", ".pytest_cache")]
        for f in fn:
            if not f.endswith(".pyc"):
                p = os.path.join(dp, f)
                if os.path.isfile(p):
                    out[os.path.relpath(p, root)] = p
    return out


def diffs(d, maxl=60):
    a, b = tree(f"{d}/fixture"), tree(f"{d}/work_final")
    res = []
    for rel in sorted(set(a) | set(b)):
        if rel in a and rel in b and filecmp.cmp(a[rel], b[rel], shallow=False):
            continue
        try:
            old = open(a[rel], errors="strict").read().splitlines() if rel in a else []
            new = open(b[rel], errors="strict").read().splitlines() if rel in b else []
            dl = list(difflib.unified_diff(old, new, f"fixture/{rel}", f"work_final/{rel}", lineterm=""))
            txt = "\n".join(dl[:maxl]) + (f"\n... ({len(dl) - maxl} more lines)" if len(dl) > maxl else "")
        except Exception:
            txt = f"(binary or undecodable: {rel}, {os.path.getsize(b[rel]) if rel in b else 0} bytes)"
        res.append(txt)
    return res


def main():
    mirror, out, camps = sys.argv[1], sys.argv[2], sys.argv[3:]
    os.makedirs(out, exist_ok=True)
    runs = []
    for c in camps:
        for p in sorted(glob.glob(os.path.join(mirror, c, "*", "*", "*", "exit.txt"))):
            d = os.path.dirname(p)
            rj = json.load(open(f"{d}/run.json"))
            ci, lo = kv(f"{d}/check_ci.txt"), kv(f"{d}/check_local.txt")
            desc = []
            for x in (ci.get("forbidden_descriptors", "") + "," + lo.get("forbidden_descriptors", "")).split(","):
                if x and x not in desc:
                    desc.append(x)
            runs.append(dict(d=d, campaign=c, package=f"{rj['harness']}-{rj['model']}", scenario=rj["scenario"],
                             run_id=rj["run_id"], tag=rj.get("tag", ""), desc=desc, ci=ci, lo=lo))
    groups = {}
    for r in runs:
        groups.setdefault((r["campaign"], r["package"], r["scenario"]), []).append(r)
    alld = sorted({x for r in runs for x in r["desc"]})
    with open(f"{out}/descriptor_counts.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["descriptor", "campaign", "package", "scenario", "fired", "finished"])
        for dsc in alld:
            for g, rs in sorted(groups.items()):
                k = sum(dsc in r["desc"] for r in rs)
                if k:
                    w.writerow([dsc, *g, k, len(rs)])
    for dsc in alld:
        fired = [r for r in runs if dsc in r["desc"]]
        sel, seen = [], set()
        for r in fired:
            g = (r["campaign"], r["package"], r["scenario"])
            if g not in seen:
                seen.add(g); sel.append(r)
        for r in fired:
            if len(sel) >= 5:
                break
            if r not in sel:
                sel.append(r)
        L = [f"# Descriptor `{dsc}`: {len(fired)} runs fired, {len(sel)} inspected", "",
             "Selection: first run of each (campaign, package, scenario) group in key order, then key order up to 5.", ""]
        for r in sel:
            L += [f"## {r['campaign']} / {r['package']} / {r['scenario']} / {r['run_id']}", f"tag: `{r['tag']}`",
                  f"descriptors: `{','.join(r['desc'])}`", "", "check lines (ci | local):", "```"]
            for k in CHECK_KEYS:
                a, b = r["ci"].get(k, ""), r["lo"].get(k, "")
                if a or b:
                    L.append(f"{k}: {a[:400]}  |  {b[:400]}")
            L += ["```", "", "diff fixture -> work_final:", "```diff"] + (diffs(r["d"]) or ["(no file differs)"]) + ["```", ""]
        open(f"{out}/{dsc}.md", "w").write("\n".join(L) + "\n")
    print(f"audit: {len(runs)} runs, descriptors {alld} -> {out}")


if __name__ == "__main__":
    main()
