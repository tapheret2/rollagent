from rollagent.engine import clamp01, weighted_mean

def test_clamp01():
    assert clamp01(1.5) == 1.0
    assert clamp01(-1) == 0.0

def test_weighted_mean():
    assert abs(weighted_mean([1, 3], [1, 1]) - 2.0) < 1e-12
