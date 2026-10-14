from forest_dieback.export import benchmark_onnx, export_onnx
from forest_dieback.model import TempCNN


def test_onnx_export_and_benchmark(tmp_path):
    model = TempCNN(in_channels=3, seq_len=36).eval()
    path = export_onnx(model, 36, 3, tmp_path / "m.onnx")
    report = benchmark_onnx(path, 36, 3, batch=64, n_batches=2)
    assert report["onnx_size_mb"] > 0
    assert report["seconds_per_100km2"] > 0
