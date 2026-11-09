"""Figures from <derive>/cells.csv (matplotlib; PDF and PNG at 300 dpi in <derive>/figures/).
Usage: <python with matplotlib> -I analyse/figures.py <derive dir>
Fig. A  no note: strict violation, ticket with the explicit rule (v5-base: violation_strict) against the same ticket
        without the rule (v5-norule, exploratory, deviation 10: the same measure, called a bypass), by package and task.
Fig. B  defense, refusal note against matched neutral note, with and without the rule: forbidden modification on the impossible task
        (S6) and legitimate success on the feasible task (S6F), by package; GLM 5.2 with the rule is the only confirmatory cell.
Every bar: Wilson 95 % interval and k/n valid runs (denominator) above it. No figure title in the images: the report sets the captions.
Colors: categorical slots 1 to 3 of the dataviz reference palette (validated with validate_palette.js, light mode: pass; slot 3
below 3:1 contrast, so every bar carries a visible k/n label). Hatching is a second encoding of the series.
"""
import csv, os, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

D = sys.argv[1]
OUT = os.path.join(D, "figures"); os.makedirs(OUT, exist_ok=True)
rows = list(csv.DictReader(open(os.path.join(D, "cells.csv"))))
NAME = {"gpt": "GPT-6.1 Sol\n(Codex)", "claude": "Claude Sonnet 5.5\n(Claude Code)", "glm": "GLM 5.2\n(Codex)",
        "deepseek": "DeepSeek V4 Flash\n(Codex)"}
C1, C2, C3 = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, GRID = "#1f1f1e", "#5f5e5a", "#e4e3df"
plt.rcParams.update({"font.size": 9, "font.family": "DejaVu Sans", "axes.edgecolor": INK2, "axes.labelcolor": INK,
                     "xtick.color": INK, "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False,
                     "pdf.fonttype": 42})


def get(camp, pkg, task, arm, k):
    for r in rows:
        if (r["campaign"], r["pkg"], r["task"], r["arm"]) == (camp, pkg, task, arm):
            n = int(r["valid"])
            return int(r[k]), n, (float(r[k + "_lo"]) if n else None), (float(r[k + "_hi"]) if n else None)
    return 0, 0, None, None


def bars(ax, x, series, width):
    """series: list of (label, color, hatch, [(k, n, lo, hi) per x])."""
    m = len(series)
    for j, (lab, col, hat, vals) in enumerate(series):
        for i, (k, n, lo, hi) in enumerate(vals):
            xx = x[i] + (j - (m - 1) / 2) * width
            if not n:
                ax.text(xx, 0.02, "no runs", rotation=90, ha="center", va="bottom", fontsize=7, color=INK2)
                continue
            p = k / n
            ax.bar(xx, p, width * 0.92, color=col, hatch=hat, edgecolor="white", linewidth=0.6)
            ax.errorbar(xx, p, yerr=[[p - lo], [hi - p]], fmt="none", ecolor=INK, elinewidth=0.9, capsize=2.5)
            ax.text(xx, hi + 0.02, f"{k}/{n}", ha="center", va="bottom", fontsize=7, color=INK)
    from matplotlib.patches import Patch
    ax.legend_handles_ = [Patch(facecolor=col, hatch=hat, edgecolor="white", label=lab) for lab, col, hat, _ in series]
    ax.set_xlim(min(x) - 0.6, max(x) + 0.6)
    ax.set_ylim(0, 1.12); ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0]); ax.set_yticklabels(["0", "25", "50", "75", "100"])
    ax.yaxis.grid(True, color=GRID, linewidth=0.6); ax.set_axisbelow(True)


def save(fig, name):
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(OUT, f"{name}.{ext}"), dpi=300, bbox_inches="tight")
    plt.close(fig)


# ---- Fig. A ----
pk = ["gpt", "claude", "glm", "deepseek"]
grp = [(p, t) for p in pk for t in ("S6", "S7")]
fig, ax = plt.subplots(figsize=(9.6, 3.7))
x = list(range(len(grp)))
bars(ax, x, [("With the explicit rule: strict violation", C1, "", [get("v5-base", p, t, "none", "violation_strict") for p, t in grp]),
             ("Without the rule: bypass (exploratory)", C2, "\\\\\\", [get("v5-norule", p, t, "none", "violation_strict") for p, t in grp])], 0.36)
ax.set_xticks(x); ax.set_xticklabels([t for _, t in grp], fontsize=7.5)
for i, p in enumerate(pk):   # package name once, centred under its pair of tasks
    ax.text(2 * i + 0.5, -0.13, NAME[p], transform=ax.get_xaxis_transform(), ha="center", va="top", fontsize=7.5, color=INK)
ax.set_ylabel("Strict violation (with rule) /\nbypass (without rule), % of runs")
ax.legend(handles=ax.legend_handles_, frameon=False, fontsize=7.5, loc="upper center", bbox_to_anchor=(0.5, -0.27), ncol=2)
save(fig, "figA_rule_vs_norule")

# ---- Fig. B ----
cols = [("glm", "v5-def", "with rule\nconfirmatory"), ("glm", "v5-norule", "no rule\nexploratory"),
        ("claude", "v5-explo", "with rule\nexploratory"), ("deepseek", "v5-explo", "with rule\nexploratory"),
        ("gpt", "v5-explo", "with rule\nexploratory")]
fig, axs = plt.subplots(1, 2, figsize=(11.5, 3.9), sharey=True, gridspec_kw={"width_ratios": [5, 5]})
for ax, task, k, title in ((axs[0], "S6", "violation_strict", "Impossible task (S6): strict violation (with rule) / bypass (without rule)"),
                           (axs[1], "S6F", "legit_success", "Feasible task (S6F): legitimate success")):
    x = list(range(len(cols)))
    bars(ax, x, [("Refusal note", C1, "", [get(c, p, task, "refusal", k) for p, c, _ in cols]),
                 ("Matched neutral note", C2, "\\\\\\", [get(c, p, task, "neutral", k) for p, c, _ in cols])], 0.36)
    ax.set_xticks(x); ax.set_xticklabels([f"{NAME[p]}\n{lab}" for p, _, lab in cols], fontsize=6.5)
    ax.set_title(title, fontsize=9, loc="left", color=INK)
axs[0].set_ylabel("Runs (%)")
axs[0].legend(handles=axs[0].legend_handles_, frameon=False, fontsize=7.5, loc="upper right")
fig.tight_layout()
save(fig, "figB_defense")
print(f"figures -> {OUT}")
