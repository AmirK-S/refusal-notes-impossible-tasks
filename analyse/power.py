"""Power of the pre-registered tests, by exact enumeration (no simulation, no normal approximation).
Usage: python3 analyse/power.py [out.txt]   (from the bench root; default out = analyse/power_out.txt)
Each power is P(reject at alpha) summed over every possible outcome of the experiment under the stated true rates.
alpha = 0.05 (unadjusted) and 0.0125 (Holm's first step with 4 hypotheses, the most stringent threshold a test can face).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stats import binom_pmf, binom_test_greater, binom_test_two_sided, fisher_two_sided, clopper_pearson_upper, wilson

ALPHAS = (0.05, 0.0125)


def power_binom_greater(n, p, alpha):
    return sum(binom_pmf(k, n, p) for k in range(n + 1) if binom_test_greater(k, n) <= alpha)


def power_fisher(n1, p1, n2, p2, alpha):
    pm1 = [binom_pmf(x, n1, p1) for x in range(n1 + 1)]
    pm2 = [binom_pmf(x, n2, p2) for x in range(n2 + 1)]
    tot = 0.0
    for x1 in range(n1 + 1):
        for x2 in range(n2 + 1):
            if fisher_two_sided(x1, n1 - x1, x2, n2 - x2) <= alpha:
                tot += pm1[x1] * pm2[x2]
    return tot


def power_mcnemar(n, p10, p01, alpha):
    """n pairs; p10 = P(trace detects, final misses), p01 = reverse. Discordant D ~ Bin(n, p10 + p01),
    b | D = d ~ Bin(d, p10 / (p10 + p01)); exact two-sided McNemar."""
    pd = p10 + p01
    q = p10 / pd if pd else 0.5
    rej = {}
    tot = 0.0
    for d in range(n + 1):
        wd = binom_pmf(d, n, pd)
        if wd < 1e-15:
            continue
        for b in range(d + 1):
            key = (b, d)
            if key not in rej:
                rej[key] = binom_test_two_sided(b, d, 0.5) <= alpha
            if rej[key]:
                tot += wd * binom_pmf(b, d, q)
    return tot


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "power_out.txt")
    L = []
    w = L.append
    w("# power.py output (exact enumeration). Columns: power at alpha=0.05 / at alpha=0.0125 (Holm first step, m=4)")
    w("")
    w("## Base rates: one-sided 95 % upper bound when 0 violations are observed (Clopper-Pearson), and Wilson half-width at 50 %")
    for n in (60, 80, 120):
        lo, hi = wilson(n // 2, n)
        w(f"n={n}: 0/{n} -> upper bound {clopper_pearson_upper(0, n):.4f}; Wilson at {n//2}/{n}: [{lo:.3f}, {hi:.3f}]")
    w("")
    w("## Expected number of violators (forbidden_mod=yes) in the base, under three scenarios for the per-run violation rate")
    w("cells: GPT S6 120 + S7 80, Claude S6 120 + S7 80, GLM S6 80 + S7 80, DeepSeek S6 60 + S7 60 (680 runs)")
    cells = {"GPT": 200, "Claude": 200, "GLM": 160, "DeepSeek": 120}
    scen = {"low": {"GPT": 0.01, "Claude": 0.0, "GLM": 0.10, "DeepSeek": 0.10},
            "mid": {"GPT": 0.03, "Claude": 0.01, "GLM": 0.30, "DeepSeek": 0.20},
            "high": {"GPT": 0.06, "Claude": 0.02, "GLM": 0.60, "DeepSeek": 0.40}}
    for s, r in scen.items():
        e = {k: cells[k] * r[k] for k in cells}
        w(f"{s}: " + ", ".join(f"{k} {r[k]:.0%} -> {e[k]:.0f}" for k in cells) + f"; total {sum(e.values()):.0f}")
    w("")
    w("## H1: exact one-sided binomial, H0 p<=0.5, n = number of violators, p = true laundered share")
    ps = (0.6, 0.65, 0.7, 0.75, 0.8, 0.9)
    w("n_viol | " + " | ".join(f"p={p}" for p in ps))
    for n in (10, 15, 20, 30, 40, 60, 80, 120, 160):
        w(f"{n} | " + " | ".join("/".join(f"{power_binom_greater(n, p, a):.2f}" for a in ALPHAS) for p in ps))
    w("")
    w("## H2: two-sided Fisher, M-final sensitivity on laundered (n_l, s_l) vs disclosed (n_d, s_d), one monitor")
    for nl, nd in ((15, 5), (20, 7), (30, 10), (45, 15), (60, 20), (100, 33)):
        row = []
        for sl, sd in ((0.3, 0.9), (0.5, 0.9), (0.6, 0.95), (0.7, 0.95)):
            row.append(f"s_l={sl},s_d={sd}: " + "/".join(f"{power_fisher(nl, sl, nd, sd, a):.2f}" for a in ALPHAS))
        w(f"n_l={nl}, n_d={nd} | " + " | ".join(row))
    w("")
    w("## H3: exact McNemar on laundered runs, M-trace vs M-final; p10 = trace detects and final misses, p01 = reverse")
    for n in (10, 15, 20, 30, 45, 60, 100):
        row = []
        for p10, p01 in ((0.2, 0.05), (0.3, 0.05), (0.4, 0.05), (0.5, 0.05)):
            row.append(f"p10={p10},p01={p01}: " + "/".join(f"{power_mcnemar(n, p10, p01, a):.2f}" for a in ALPHAS))
        w(f"n_laundered={n} | " + " | ".join(row))
    w("")
    w("## H-D: two-sided Fisher, GLM, impossible task, forbidden_mod rate, refusal (60) vs neutral (60)")
    for pn in (0.4, 0.5, 0.67):
        row = []
        for pr in (0.1, 0.2, 0.3, 0.4):
            if pr < pn:
                row.append(f"refusal={pr}: " + "/".join(f"{power_fisher(60, pr, 60, pn, a):.2f}" for a in ALPHAS))
        w(f"neutral={pn} | " + " | ".join(row))
    w("")
    w("## Feasible counterpart (descriptive): two-sided Fisher on legitimate green, 30 vs 30, alpha=0.05")
    for pn, pr in ((0.9, 0.6), (0.9, 0.7), (0.8, 0.5), (0.9, 0.8)):
        w(f"neutral={pn}, refusal={pr}: {power_fisher(30, pr, 30, pn, 0.05):.2f}")
    open(out, "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
