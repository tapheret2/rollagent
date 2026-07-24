
from rollagent.mathutil import argmax, softmax

def test_softmax_sums_to_one():
    s = softmax([1.0, 2.0, 3.0])
    assert abs(sum(s) - 1.0) < 1e-9

def test_argmax():
    assert argmax([0.1, 0.9, 0.2]) == 1
