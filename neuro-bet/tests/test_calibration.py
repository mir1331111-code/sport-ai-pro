import numpy as np
from model.calibration import PlattCalibrator


def test_calibration_trains_on_enough_data():
    rng = np.random.default_rng(42)
    n = 500
    p = rng.uniform(0.1, 0.9, size=(n, 3))
    p = p / p.sum(axis=1, keepdims=True)
    logits = np.log(p / (1 - p)).flatten()
    outcomes = (rng.uniform(size=(n, 3)) < p).astype(float).flatten()
    cal = PlattCalibrator()
    cal.fit(logits, outcomes)
    assert cal.trained


def test_calibration_skips_tiny_data():
    cal = PlattCalibrator()
    cal.fit(np.zeros(30), np.zeros(30))
    assert not cal.trained
