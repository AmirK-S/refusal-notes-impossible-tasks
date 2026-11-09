"""Exact tests and intervals used by the pre-registered analysis (stdlib only, no scipy).

binom_sf_ge(k, n, p)      P(X >= k), X ~ Bin(n, p)
binom_test_greater(k, n)  one-sided exact binomial p-value, H0: p <= 0.5 (H1)
fisher_two_sided(a, b, c, d)  2x2 table [[a, b], [c, d]], two-sided exact p (sum of tables with prob <= observed)
mcnemar_exact(b, c)       exact two-sided McNemar on the discordant counts (b, c)
wilson(k, n)              Wilson score 95 % interval
newcombe(k1, n1, k2, n2)  Newcombe hybrid score 95 % interval for p1 - p2 (method 10)
clopper_pearson_upper(k, n)  one-sided 95 % upper bound
holm(pvals)               Holm adjusted p-values, same order as input
perm_test_two_sided(xs, ys, n_perm, seed)  exact (or Monte Carlo) permutation test on the difference of means
sign_test_exact(diffs)    exact two-sided sign test on non-zero paired differences
"""
from math import comb, sqrt, isclose
import random

Z = 1.959963984540054


def binom_pmf(k, n, p):
    return comb(n, k) * p ** k * (1 - p) ** (n - k)


def binom_sf_ge(k, n, p):
    return sum(binom_pmf(i, n, p) for i in range(max(k, 0), n + 1))


def binom_test_greater(k, n, p0=0.5):
    if n == 0:
        return 1.0
    return min(1.0, binom_sf_ge(k, n, p0))


def binom_test_two_sided(k, n, p0=0.5):
    if n == 0:
        return 1.0
    pk = binom_pmf(k, n, p0)
    return min(1.0, sum(binom_pmf(i, n, p0) for i in range(n + 1) if binom_pmf(i, n, p0) <= pk * (1 + 1e-7)))


def _hyper_pmf(x, n1, n2, m):
    # x successes in group 1 of size n1, m total successes, group 2 size n2
    return comb(n1, x) * comb(n2, m - x) / comb(n1 + n2, m)


def fisher_two_sided(a, b, c, d):
    """a = successes group 1, b = failures group 1, c = successes group 2, d = failures group 2."""
    n1, n2, m = a + b, c + d, a + c
    lo, hi = max(0, m - n2), min(n1, m)
    p_obs = _hyper_pmf(a, n1, n2, m)
    tot = 0.0
    for x in range(lo, hi + 1):
        px = _hyper_pmf(x, n1, n2, m)
        if px <= p_obs * (1 + 1e-7):
            tot += px
    return min(1.0, tot)


def mcnemar_exact(b, c):
    """b = pairs (yes on method 1, no on method 2), c = the reverse. Exact two-sided binomial on b of b + c."""
    return binom_test_two_sided(b, b + c, 0.5)


def sign_test_exact(diffs):
    pos = sum(1 for x in diffs if x > 0)
    neg = sum(1 for x in diffs if x < 0)
    return binom_test_two_sided(pos, pos + neg, 0.5), pos, neg


def wilson(k, n, z=Z):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, centre - half), min(1.0, centre + half))


def newcombe(k1, n1, k2, n2, z=Z):
    """95 % interval for p1 - p2, Newcombe (1998) method 10 (hybrid Wilson score)."""
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = wilson(k1, n1, z)
    l2, u2 = wilson(k2, n2, z)
    d = p1 - p2
    lo = d - sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2)
    hi = d + sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)
    return (lo, hi)


def clopper_pearson_upper(k, n, alpha=0.05):
    """One-sided upper bound: largest p with P(X <= k | p) >= alpha (bisection)."""
    if k >= n:
        return 1.0
    lo, hi = 0.0, 1.0
    for _ in range(100):
        mid = (lo + hi) / 2
        cdf = sum(binom_pmf(i, n, mid) for i in range(k + 1))
        if cdf > alpha:
            lo = mid
        else:
            hi = mid
    return lo


def holm(pvals):
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    adj = [0.0] * m
    run = 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (m - rank) * pvals[i]))
        adj[i] = run
    return adj


def perm_test_two_sided(xs, ys, n_perm=200000, seed=20261108):
    """Two-sided permutation test on mean(xs) - mean(ys). Exact enumeration when C(n, len(xs)) <= n_perm,
    Monte Carlo with a fixed seed otherwise (p = (1 + #extreme) / (1 + n_perm))."""
    from itertools import combinations
    allv = list(xs) + list(ys)
    n, k = len(allv), len(xs)
    if k == 0 or k == n:
        return 1.0
    obs = abs(sum(xs) / k - sum(ys) / (n - k))
    tot = sum(allv)
    if comb(n, k) <= n_perm:
        ext = cnt = 0
        for idx in combinations(range(n), k):
            s = sum(allv[i] for i in idx)
            d = abs(s / k - (tot - s) / (n - k))
            cnt += 1
            ext += d >= obs - 1e-12
        return ext / cnt
    rng = random.Random(seed)
    ext = 0
    for _ in range(n_perm):
        rng.shuffle(allv)
        s = sum(allv[:k])
        ext += abs(s / k - (tot - s) / (n - k)) >= obs - 1e-12
    return (1 + ext) / (1 + n_perm)


if __name__ == "__main__":
    # self-checks against known values
    assert isclose(fisher_two_sided(1, 9, 11, 3), 0.002759, rel_tol=1e-3)          # R fisher.test
    assert isclose(fisher_two_sided(0, 12, 6, 6), 0.01373, rel_tol=1e-3)           # V4 2.3: 0/12 vs 6/12, p = 0.014
    assert isclose(binom_test_greater(15, 20), 0.02069, rel_tol=1e-3)              # R binom.test(15,20,alt="greater")
    assert isclose(mcnemar_exact(1, 9), 0.02148, rel_tol=1e-3)                     # 2 * P(X<=1 | 10, .5)
    lo, hi = wilson(0, 40); assert lo == 0 and isclose(hi, 0.0876, rel_tol=1e-2)
    assert isclose(clopper_pearson_upper(0, 40), 0.0722, rel_tol=1e-2)             # V3 1.6: 7.2 %
    lo, hi = newcombe(56, 70, 48, 80)                                              # Newcombe 1998 example: 0.0524, 0.3339
    assert isclose(lo, 0.0524, abs_tol=2e-3) and isclose(hi, 0.3339, abs_tol=2e-3), (lo, hi)
    assert [round(x, 4) for x in holm([0.01, 0.04, 0.03, 0.005])] == [0.03, 0.06, 0.06, 0.02]
    print("stats.py self-checks passed")
