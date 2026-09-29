import numpy as np

from ledger.calibrate import Calibrator, _pav, fit


def test_pav_is_monotone_and_pools_violators():
    b = _pav(np.array([0.1, 0.2, 0.3, 0.4]), np.array([0, 1, 0, 1]))
    means = [m for m, *_ in b]
    assert means == sorted(means) and len(b) < 4


def test_fit_needs_enough_pairs_and_improves_cv_brier():
    rng = np.random.default_rng(1)
    p = rng.uniform(0, 1, 300)
    y = (rng.uniform(0, 1, 300) < np.clip(p ** 2, 0, 1)).astype(float)  # systematically over-confident model
    c = fit(p, y)
    assert c.fitted() and c.brier_cv < c.brier_raw and c.brier_cv < c.brier_base
    assert not fit(p[:20], y[:20]).fitted()
    assert 0.0 <= Calibrator(blocks=c.blocks).apply(0.5) <= 1.0
