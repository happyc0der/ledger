"""Self-calibration from the company's own outcomes. Isotonic regression (pool-adjacent-violators,
numpy only) fitted on (predicted p while open, real outcome later). Reported with a cross-validated
Brier score so the number is held-out, not fitted. Needs at least MIN_PAIRS pairs; otherwise the
raw probabilities are shown and labelled as unmeasured."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

MIN_PAIRS = 60


@dataclass
class Calibrator:
    blocks: list = field(default_factory=list)   # [(mean, count, x_lo, x_hi)] step function
    n: int = 0
    brier_raw: float | None = None
    brier_cv: float | None = None
    brier_base: float | None = None
    reliability: list = field(default_factory=list)

    def fitted(self) -> bool:
        return bool(self.blocks)

    def apply(self, p: float) -> float:
        if not self.blocks:
            return float(p)
        for m, _, lo, hi in self.blocks:
            if lo <= p <= hi:
                return float(m)
        below = [b for b in self.blocks if b[3] < p]
        above = [b for b in self.blocks if b[2] > p]
        if below and (not above or p - below[-1][3] <= above[0][2] - p):
            return float(below[-1][0])
        return float(above[0][0])

    def to_dict(self) -> dict:
        return {"n": self.n, "brier_raw": self.brier_raw, "brier_cv": self.brier_cv, "brier_base": self.brier_base,
                "reliability": self.reliability, "fitted": self.fitted()}


def _pav(x: np.ndarray, y: np.ndarray) -> list:
    o = np.argsort(x, kind="stable")
    xs, ys = x[o], y[o]
    blocks = [[float(ys[i]), 1, float(xs[i]), float(xs[i])] for i in range(len(ys))]
    i = 0
    while i < len(blocks) - 1:
        if blocks[i][0] > blocks[i + 1][0]:
            a, b = blocks[i], blocks[i + 1]
            m = (a[0] * a[1] + b[0] * b[1]) / (a[1] + b[1])
            blocks[i] = [m, a[1] + b[1], a[2], b[3]]
            del blocks[i + 1]
            i = max(i - 1, 0)
        else:
            i += 1
    return [tuple(b) for b in blocks]


def fit(p: np.ndarray, y: np.ndarray, folds: int = 5, seed: int = 0) -> Calibrator:
    p, y = np.asarray(p, float), np.asarray(y, float)
    c = Calibrator(n=int(len(p)))
    if len(p) < MIN_PAIRS:
        return c
    c.brier_raw = float(np.mean((p - y) ** 2))
    c.brier_base = float(np.mean((y.mean() - y) ** 2))
    idx = np.random.default_rng(seed).permutation(len(p))
    parts = np.array_split(idx, folds)
    cv = np.zeros_like(p)
    for k in range(folds):
        te = parts[k]
        tr = np.concatenate([parts[j] for j in range(folds) if j != k])
        tmp = Calibrator(blocks=_pav(p[tr], y[tr]))
        cv[te] = [tmp.apply(v) for v in p[te]]
    c.brier_cv = float(np.mean((cv - y) ** 2))
    c.blocks = _pav(p, y)
    edges = [0, .2, .4, .6, .8, 1.0]
    for a, b in zip(edges[:-1], edges[1:]):
        m = (cv > a) & (cv <= b) if a > 0 else (cv >= a) & (cv <= b)
        if m.sum():
            c.reliability.append({"bin": f"{a:.1f}–{b:.1f}", "n": int(m.sum()), "stated": round(float(cv[m].mean()), 2), "actual": round(float(y[m].mean()), 2)})
    return c


def pairs_from_history(snapshots: pd.DataFrame, outcomes: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """(p while open, outcome) pairs: the earliest stored prediction per deal that later closed.
    `outcomes` has opportunity_id + outcome ∈ {Won, Lost}."""
    s = snapshots.dropna(subset=["p"]).sort_values("run_id").drop_duplicates("opportunity_id", keep="first")
    o = outcomes.set_index("opportunity_id").outcome
    s = s[s.opportunity_id.isin(o.index)]
    return s.p.to_numpy(float), (o.loc[s.opportunity_id].to_numpy() == "Won").astype(float)
