import joblib
import numpy as np
from pathlib import Path


MODEL_PATH = Path(__file__).parent / 'models' / 'safety_model.pkl'

_model_data = None
_model = None
_feature_names = []

if MODEL_PATH.exists():
    try:
        _model_data = joblib.load(MODEL_PATH)
        _model = _model_data['model']
        _feature_names = _model_data['feature_names']
    except Exception as e:
        print(f"Warning: Could not load ML model: {e}")
        _model = None
else:
    print(f"Warning: ML model not found at {MODEL_PATH}. ML features will be disabled. Run ml/train.py to train the model.")


def predict_safety_score(features: dict) -> float:
    if _model is None:
        # Fallback: return a score based on simple heuristics
        crime_score = max(0, 100 - features.get('crime_density', 0) * 10)
        lighting_score = features.get('lighting_score', 5) * 10
        return float(np.clip((crime_score + lighting_score) / 2, 0, 100))
    
    feature_vector = np.array([features.get(name, 0.0) for name in _feature_names])
    prediction = _model.predict([feature_vector])[0]
    return float(np.clip(prediction, 0, 100))
