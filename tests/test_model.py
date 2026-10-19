import torch

from forest_dieback.model import TempCNN, count_parameters


def test_tempcnn_output_shape():
    model = TempCNN(in_channels=3, seq_len=72).eval()
    out = model(torch.zeros(8, 72, 3))
    assert out.shape == (8,)


def test_tempcnn_is_frugal():
    assert count_parameters(TempCNN(in_channels=3, seq_len=72)) < 300_000


def test_tempcnn_size_does_not_follow_the_series_length():
    """Le pooling détache la tête de la longueur : 7 ans ne coûtent pas plus qu'un."""
    court = count_parameters(TempCNN(in_channels=3, seq_len=37))
    long = count_parameters(TempCNN(in_channels=3, seq_len=259))
    assert court == long


def test_tempcnn_pool_shorter_than_series_is_honoured():
    petit = count_parameters(TempCNN(in_channels=3, seq_len=259, pool=4))
    grand = count_parameters(TempCNN(in_channels=3, seq_len=259, pool=16))
    assert petit < grand
    # une série plus courte que le pooling demandé ne doit pas faire échouer
    assert TempCNN(in_channels=3, seq_len=2, pool=8)(torch.zeros(4, 2, 3)).shape == (4,)
