
from __future__ import annotations
from pathlib import Path
import yaml
import pandas as pd

def load_yaml(path: str | Path) -> dict:
    with open(path,"r",encoding="utf-8") as f:
        return yaml.safe_load(f)

def load_csv(path: str | Path) -> pd.DataFrame:
    return pd.read_csv(path)
