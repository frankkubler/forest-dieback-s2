import torch

from forest_dieback.model import TempCNN, count_parameters


def test_tempcnn_output_shape():
    model = TempCNN(in_channels=3, seq_len=72).eval()
    out = model(torch.zeros(8, 72, 3))
    assert out.shape == (8,)


def test_tempcnn_is_frugal():
    assert count_parameters(TempCNN(in_channels=3, seq_len=72)) < 2_000_000
