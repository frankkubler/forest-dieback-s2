import numpy as np

from forest_dieback.metrics import binary_metrics, detection_delay


def test_binary_metrics():
    m = binary_metrics([1, 1, 0, 0], [1, 0, 1, 0])
    assert m == {"precision": 0.5, "recall": 0.5, "f1": 0.5}


def test_detection_delay_ignores_missed():
    ref = np.array(["2023-06-01", "2023-07-01", "NaT"], dtype="datetime64[D]")
    pred = np.array(["2023-06-11", "NaT", "2023-08-01"], dtype="datetime64[D]")
    assert detection_delay(ref, pred) == 10
