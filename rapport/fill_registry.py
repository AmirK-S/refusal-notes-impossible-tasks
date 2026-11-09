#!/usr/bin/env python3
"""Generate rapport/registry.tex from analyse/registre.csv and copy the figures into rapport/fig/.

Every number of a result in the report is printed by a macro that reads this file; nothing is typed by hand.

  \\reg{key}      value formatted (integer as is, float with 3 significant digits, text as is)
  \\regpct{key}   value x 100 with a percent sign (0 decimals, 1 decimal under 10 %)
  \\regp{key}     p-value (3 significant digits, "< 0.001" below 0.001)
  A key that is absent from the registry prints a red "??" and is listed by this script.

Registry: CSV with columns key,value[,denominator,script,commit,date]; the last row for a key wins.
Derived keys (the only computation done here): <key>.denom = the denominator column when it is a single integer,
used by \\kd{key} to print k/n; <key>.pp = |Newcombe bound| in percentage points (integer);
derived.registry_sha256 = SHA-256 of the registry file (the analysis's own registry.sha256 key wins if present).
Optional rapport/aliases.csv (report_key,registry_key) maps a key used in the .tex to another registry key.
Figures: figA and figB are looked for in the derive folder (default ~/work/swarm-alignment-data/derive, recursive),
under names starting with figA, fig_a, fig-a, figureA, figure_a (pdf first, then png; newest wins), e.g. figures/figA_baseline_violations.pdf; copied to rapport/fig/figA.<ext>.

Usage: python3 -I rapport/fill_registry.py [--registry analyse/registre.csv] [--derive DIR]
"""
import argparse, csv, glob, math, os, re, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def fmt_num(v):
    if v.startswith("not computable"):
        return "n/c"
    try:
        f = float(v)
    except ValueError:
        return None
    if math.isnan(f):
        return "n/a"
    if re.fullmatch(r"-?\d+", v.strip()) or (f.is_integer() and abs(f) >= 1 and "e" not in v.lower()):
        return f"{int(f)}"
    if f == 0:
        return "0"
    d = max(0, 2 - int(math.floor(math.log10(abs(f)))))
    return f"{f:.{d}f}"


def fmt_pct(v):
    if v.startswith("not computable"):
        return "n/c"
    try:
        f = float(v)
    except ValueError:
        return tex_escape(v)
    if math.isnan(f):
        return "n/a"
    x = 100 * f
    return (f"{x:.1f}" if abs(x) < 10 and x != 0 else f"{x:.0f}") + r"\,\%"


def fmt_p(v):
    if v.startswith("not computable"):
        return "n/c"
    try:
        f = float(v)
    except ValueError:
        return tex_escape(v)
    if math.isnan(f):
        return "n/a"
    if f < 0.001:
        return r"$<$\,0.001"
    return f"{f:.3g}"


def tex_escape(s):
    return (s.replace("\\", r"\textbackslash{}").replace("_", r"\_").replace("%", r"\%").replace("&", r"\&")
             .replace("#", r"\#").replace("$", r"\$").replace("{", r"\{").replace("}", r"\}"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--registry", default=os.path.join(ROOT, "analyse", "registre.csv"))
    ap.add_argument("--derive", default=os.path.expanduser("~/work/swarm-alignment-data/derive"))
    a = ap.parse_args()

    reg = {}
    dates = []
    if os.path.exists(a.registry):
        with open(a.registry, newline="") as f:
            for r in csv.DictReader(f):
                if r.get("key"):
                    k = r["key"].strip()
                    if (r.get("date") or "").strip():
                        dates.append(r["date"].strip())
                    reg[k] = (r.get("value") or "").strip()
                    # derived key <key>.denom from the registry's denominator column (single integer only)
                    d = (r.get("denominator") or "").strip()
                    if re.fullmatch(r"\d+", d):
                        reg[k + ".denom"] = d
    else:
        print(f"registry not found: {a.registry} (every key will print ??)", file=sys.stderr)
    # Derived aggregates (simple sums of registry keys; nothing else is computed here):
    #   derived.base.excluded_d   = sum of v5-base.<pkg>.<S6|S7>.none.excluded_d
    #   derived.def.glm.S6.excluded_d = refusal + neutral excluded_d of the confirmatory cell
    #   derived.set_aside.total   = sum of set_aside.<campaign>.<folder> (runs where the agent never started, or quota)
    #   derived.registry_date     = latest date in the registry's date column (data freeze shown in the report)
    def ssum(pat):
        vals = [float(v) for k, v in reg.items() if re.fullmatch(pat, k) and re.fullmatch(r"-?\d+(\.\d+)?", v)]
        return str(int(sum(vals))) if vals else None
    for k, pat in (("derived.base.excluded_d", r"v5-base\.[a-z]+\.S[67]\.none\.excluded_d"),
                   ("derived.def.glm.S6.excluded_d", r"v5-def\.glm\.S6\.(refusal|neutral)\.excluded_d"),
                   ("derived.set_aside.total", r"set_aside\.[^.]+\.[^.]+")):
        v = ssum(pat)
        if v is not None:
            reg[k] = v
    if dates:
        reg["derived.registry_date"] = max(dates).replace("T", " ").replace("Z", " UTC")
    # <key>.pp for every Newcombe bound = |bound| in percentage points, rounded to an integer (e.g. -0.117 -> 12)
    for k, v in list(reg.items()):
        if re.search(r"\.newcombe_(lo|hi)$", k) and re.fullmatch(r"-?\d+(\.\d+)?(e-?\d+)?", v):
            reg[k + ".pp"] = str(int(round(abs(float(v)) * 100)))
    if os.path.exists(a.registry):   # derived.registry_sha256 = sha256 of the registry file used for this build
        import hashlib
        reg["derived.registry_sha256"] = hashlib.sha256(open(a.registry, "rb").read()).hexdigest()
    al = os.path.join(HERE, "aliases.csv")
    if os.path.exists(al):
        with open(al, newline="") as f:
            for r in csv.reader(f):
                if len(r) >= 2 and not r[0].startswith("#") and r[1].strip() in reg:
                    reg[r[0].strip()] = reg[r[1].strip()]

    out = ["% generated by rapport/fill_registry.py from " + os.path.relpath(a.registry, ROOT) + "; do not edit",
           r"\providecommand{\regmissing}{\textcolor{red}{\textbf{??}}}"]
    for k, v in sorted(reg.items()):
        n = fmt_num(v)
        out.append(r"\expandafter\def\csname regv@%s\endcsname{%s}" % (k, n if n is not None else tex_escape(v)))
        out.append(r"\expandafter\def\csname regpct@%s\endcsname{%s}" % (k, fmt_pct(v)))
        out.append(r"\expandafter\def\csname regp@%s\endcsname{%s}" % (k, fmt_p(v)))
    sha = reg.get("registry.sha256") or reg.get("derived.registry_sha256")   # the analysis's own fingerprint first
    if sha:
        out.append(r"\def\regsha{\nolinkurl{%s}}" % sha)
    with open(os.path.join(HERE, "registry.tex"), "w") as f:
        f.write("\n".join(out) + "\n")

    # keys used in the sources that the registry lacks
    used = set()
    for t in glob.glob(os.path.join(HERE, "*.tex")):
        if os.path.basename(t) == "registry.tex":
            continue
        src = open(t).read()
        used |= set(re.findall(r"\\reg(?:pct|p)?\{([^}#]+)\}", src))
        # keys built by the table macros: \baserow{pkg}{cell}, \defrow{phase}{pkg}{cell}
        for pkg, task in re.findall(r"\\ruleside\{([^}]+)\}\{([^}]+)\}", src):
            b = f"v5-base.{pkg}.{task}.none."
            used |= {b + x for x in ("valid", "green", "forbidden_mod", "violation_strict", "violation_strict.wilson_lo", "violation_strict.wilson_hi")}
        for pkg, task in re.findall(r"\\noruleside\{([^}]+)\}\{([^}]+)\}", src):
            b = f"norule.{pkg}.{task}.none."
            used |= {b + x for x in ("valid", "green", "bypass", "bypass.wilson_lo", "bypass.wilson_hi")}
        for pre, pkg, arm, oc in re.findall(r"\\improw\{([^}]+)\}\{([^}]+)\}\{([^}]+)\}\{([^}]+)\}", src):
            b = f"{pre}.{pkg}.S6.{arm}."
            used |= {b + x for x in ("valid", "note_opened", "green", "forbidden_mod", oc, oc + ".rate")}
        for pre, pkg, arm, oc in re.findall(r"\\fearow\{([^}]+)\}\{([^}]+)\}\{([^}]+)\}\{([^}]+)\}", src):
            b = f"{pre}.{pkg}.S6F.{arm}."
            used |= {b + x for x in ("valid", "note_opened", "green", "forbidden_mod", oc, "legit_success", "legit_success.rate")}
        for tid, oc in re.findall(r"\\contrast\{([^}]+)\}\{([^}]+)\}", src):
            used |= {f"{tid}.{oc}.{x}" for x in ("diff", "newcombe_lo", "newcombe_hi", "fisher_p")}
        for k in re.findall(r"\\kd\{([^}]+)\}", src):
            used |= {k, k + ".denom"}
        for cell, m in re.findall(r"\\kn\{([^}]+)\}\{([^}]+)\}", src):
            used |= {f"{cell}.{m}", f"{cell}.valid"}
    missing = sorted(k for k in used if k not in reg)
    print(f"registry keys: {len(reg)}; keys used by the report: {len(used)}; missing: {len(missing)}")
    for k in missing:
        print("  missing", k)

    # appendix tables: derive/flow.csv and derive/events_audit.csv -> rapport/flow.tex, rapport/events_audit.tex
    # (a fixed subset of columns, cells copied verbatim; absent file -> no .tex, the report shows "pending")
    def sumcols(r, cols):
        try:
            return str(sum(int(r.get(c) or 0) for c in cols))
        except ValueError:
            return "?"
    specs = {
        "flow": ("llllrrrrrr",
                 ["Campaign", "Package", "Task", "Arm", "Planned", "Launches", "Set aside", "Excluded", "Unfinished", "Analysed"],
                 lambda r: [r["campaign"], r["pkg"], r["task"], r["arm"], r["planned"], r["launch_attempts"],
                            sumcols(r, [c for c in r if c.startswith("set_aside")]),
                            sumcols(r, [c for c in r if c.startswith("excluded")]),
                            r.get("unfinished_at_freeze", ""), r["analysed"]]),
        "events_audit": (">{\\raggedright}p{2.0cm}>{\\raggedright}p{2.0cm}>{\\raggedright}p{2.4cm}>{\\raggedright}p{2.0cm}"
                         ">{\\raggedright}p{3.0cm}ll>{\\raggedright\\arraybackslash}p{1.9cm}",
                 ["Cell", "Run", "Files and action", "Strict descriptors", "Ticket clause", "Intact", "Green", "Reading"],
                 lambda r: [f"{r['campaign']} {r['package_name'].split(' (')[0]} {r['task']} {r['arm']}", r["run_id"],
                            r["files_and_action"].strip().rstrip(";").replace(";", "; "), r["descriptors_strict"].replace(",", ", "),
                            r["ticket_clause"], r["test_file_intact"], r["green"],
                            r["interpretation"].replace("_", " ")]),
    }
    for stem, (spec, head, fn) in specs.items():
        src = os.path.join(a.derive, stem + ".csv")
        dst = os.path.join(HERE, stem + ".tex")
        if not os.path.exists(src):
            if os.path.exists(dst):
                os.remove(dst)
            print(f"{stem}: not found ({src})")
            continue
        with open(src, newline="") as f:
            rows = list(csv.DictReader(f))
        lines = [r"{\scriptsize\setlength{\tabcolsep}{3pt}\begin{longtable}{@{}%s@{}}\toprule" % spec,
                 " & ".join(head) + r" \\\midrule\endhead"]
        for r in rows:
            # break opportunities after / and _ so that paths and descriptor names fit the narrow columns
            lines.append(" & ".join(tex_escape(str(c)).replace("/", r"/\allowbreak{}").replace(r"\_", r"\_\allowbreak{}")
                                    for c in fn(r)) + r" \\")
        lines.append(r"\bottomrule\end{longtable}}")
        with open(dst, "w") as f:
            f.write("% generated by rapport/fill_registry.py from " + src + "\n" + "\n".join(lines) + "\n")
        print(f"{stem}: {src} ({len(rows)} rows)")

    # figures
    os.makedirs(os.path.join(HERE, "fig"), exist_ok=True)
    for name, stems in (("figA", ("figA_rule_vs_norule", "figA*", "fig_a*", "fig-a*", "figureA*", "figure_a*")),
                        ("figB", ("figB_defense", "figB*", "fig_b*", "fig-b*", "figureB*", "figure_b*"))):
        found = None
        for ext in ("pdf", "png"):
            for st in stems:
                hits = sorted(glob.glob(os.path.join(a.derive, "**", f"{st}.{ext}"), recursive=True), key=os.path.getmtime)
                hits += sorted(glob.glob(os.path.join(a.derive, "**", f"{st.lower()}.{ext}"), recursive=True), key=os.path.getmtime)
                if hits:
                    found = hits[-1]
                    break
            if found:
                break
        for ext in ("pdf", "png"):
            old = os.path.join(HERE, "fig", f"{name}.{ext}")
            if os.path.exists(old) and (not found or not found.endswith(ext)):
                os.remove(old)
        if found:
            shutil.copy2(found, os.path.join(HERE, "fig", f"{name}.{found.rsplit('.', 1)[1]}"))
            print(f"{name}: {found}")
        else:
            print(f"{name}: not found under {a.derive} (the report shows 'figure pending')")
    return 0


if __name__ == "__main__":
    sys.exit(main())
