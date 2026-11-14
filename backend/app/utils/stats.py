"""Small dependency-free statistics helpers used across the engines."""
from __future__ import annotations

import math
from typing import Iterable, Sequence


def clean(values: Iterable[float | None]) -> list[float]:
    return [v for v in values if v is not None and not math.isnan(v)]


def mean(values: Iterable[float | None], default: float = 0.0) -> float:
    vals = clean(values)
    return sum(vals) / len(vals) if vals else default


def stdev(values: Iterable[float | None]) -> float:
    vals = clean(values)
    if len(vals) < 2:
        return 0.0
    m = sum(vals) / len(vals)
    return math.sqrt(sum((v - m) ** 2 for v in vals) / (len(vals) - 1))


def percentile(values: Iterable[float | None], q: float, default: float = 0.0) -> float:
    """Linear-interpolated percentile, q in [0, 100]."""
    vals = sorted(clean(values))
    if not vals:
        return default
    if len(vals) == 1:
        return vals[0]
    pos = (len(vals) - 1) * q / 100.0
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(vals) - 1)
    return vals[lo] + (vals[hi] - vals[lo]) * (pos - lo)


def normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def lerp_score(x: float, worst: float, best: float) -> float:
    """Map x onto 0..100 where `worst` scores 0 and `best` scores 100 (either may be larger)."""
    if best == worst:
        return 50.0
    return 100.0 * clamp((x - worst) / (best - worst))


def theil_sen(xs: Sequence[float], ys: Sequence[float | None]) -> dict:
    """Robust trend: Theil-Sen slope plus a Mann-Kendall two-sided p-value.

    Returned slope is per unit of x. Satellite records are short and noisy, so a robust
    estimator plus an explicit significance flag is safer than least squares.
    """
    pts = [(x, y) for x, y in zip(xs, ys) if y is not None and not math.isnan(y)]
    n = len(pts)
    if n < 4:
        return {"slope": 0.0, "p_value": 1.0, "significant": False, "n": n}
    slopes = []
    s = 0
    for i in range(n - 1):
        for j in range(i + 1, n):
            dx = pts[j][0] - pts[i][0]
            dy = pts[j][1] - pts[i][1]
            if dx != 0:
                slopes.append(dy / dx)
            s += (dy > 0) - (dy < 0)
    slopes.sort()
    slope = slopes[len(slopes) // 2] if slopes else 0.0
    var_s = n * (n - 1) * (2 * n + 5) / 18.0
    if s > 0:
        z = (s - 1) / math.sqrt(var_s)
    elif s < 0:
        z = (s + 1) / math.sqrt(var_s)
    else:
        z = 0.0
    p = 2.0 * (1.0 - normal_cdf(abs(z)))
    return {"slope": slope, "p_value": round(p, 4), "significant": p < 0.1, "n": n}


def pearson(xs: Sequence[float | None], ys: Sequence[float | None]) -> float | None:
    pts = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pts) < 3:
        return None
    mx = sum(p[0] for p in pts) / len(pts)
    my = sum(p[1] for p in pts) / len(pts)
    sxx = sum((p[0] - mx) ** 2 for p in pts)
    syy = sum((p[1] - my) ** 2 for p in pts)
    if sxx <= 0 or syy <= 0:
        return None
    return sum((p[0] - mx) * (p[1] - my) for p in pts) / math.sqrt(sxx * syy)


def r(x: float | None, digits: int = 2) -> float | None:
    """Round for JSON output, passing None through."""
    return None if x is None else round(float(x), digits)
