import os
import pandas as pd
from pathlib import Path


DATA_FILE = Path(__file__).parent / 'data' / 'training_data.csv'


def log_route_sample(features: dict, label: float):
    try:
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        row = {**features, 'safety_score': label}
        df = pd.DataFrame([row])
        
        if DATA_FILE.exists():
            existing = pd.read_csv(DATA_FILE, nrows=0)
            df = df.reindex(columns=existing.columns, fill_value=0)
            df.to_csv(DATA_FILE, mode='a', header=False, index=False)
        else:
            df.to_csv(DATA_FILE, mode='w', header=True, index=False)
    except Exception:
        pass
