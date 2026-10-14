import copy

from forest_dieback.config import load_config
from forest_dieback.train import train


def test_train_on_synthetic(tmp_path):
    cfg = copy.deepcopy(load_config())
    cfg["train"]["epochs"] = 3
    cfg["paths"]["models"] = str(tmp_path)
    summary = train(cfg, synthetic=True, use_mlflow=False)
    assert (tmp_path / "tempcnn.pt").exists()
    assert summary["best_val_f1"] > 0.5
