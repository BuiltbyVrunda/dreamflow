# Machine Learning Layer - Safe Routes

## Overview
This ML module provides intelligent safety scoring and validation for route recommendations using machine learning and rule-based guardrails.

## Directory Structure

```
ml/
├── __init__.py              # Module initialization
├── feature_extraction.py    # Extract ML features from routes
├── inference.py             # ML model predictions
├── collect_data.py          # Generate training data
├── train.py                 # Train LightGBM model
├── models/                  # Trained model artifacts
│   └── safety_model.pkl     # Trained model (generated)
├── data/                    # Training data
│   ├── training_data.csv    # Generated training set
│   └── route_logs/          # Production route logs
└── notebooks/               # Analysis notebooks
    └── model_analysis.ipynb # Model analysis (optional)

safety/
├── __init__.py              # Module initialization
└── guardrails.py            # Hard safety constraints

logs/
├── route_requests.log       # All route requests
└── ml_predictions.log       # ML predictions
```

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Generate Training Data

```bash
cd ml
python collect_data.py
```

This generates 5,000 synthetic training samples based on existing crime, lighting, and population data.

### 3. Train the Model

```bash
python train.py
```

This trains a LightGBM model and saves it to `models/safety_model.pkl`.

### 4. Integration

The ML layer is automatically integrated into the Flask app:
- Safety guardrails are applied to all routes in the `/api/optimize-route` endpoint
- Routes failing safety checks are filtered out
- Warnings are attached to routes with potential issues

## Features

### Feature Extraction (`feature_extraction.py`)

Extracts 20+ features from routes:
- **Route features**: distance, duration, number of steps
- **Temporal features**: hour of day, day of week, weekend, night time, rush hour
- **Crime features**: average crime density, max crime exposure, hotspot count
- **Lighting features**: lighting density, poorly lit segments
- **Population features**: population density, isolated segments
- **Derived features**: crime-to-lighting ratio, night-specific risks

### ML Inference (`inference.py`)

- Loads trained LightGBM model
- Predicts safety scores (0-100) for routes
- Provides feature importance analysis
- Falls back gracefully if model not trained

### Safety Guardrails (`safety/guardrails.py`)

Hard constraints that filter unsafe routes:
- **Crime hotspots**: Rejects routes through high-crime areas
- **Lighting coverage**: Validates adequate lighting (especially at night)
- **Isolation**: Checks for unpopulated/isolated areas
- **Time-based**: Flags late-night travel risks

## Model Training

### Synthetic Data Generation

The `collect_data.py` script generates realistic training data:
- Random route generation within Bangalore bounds
- Feature extraction for each route
- Ground truth safety scoring based on heuristics
- Temporal variation (different times of day/week)

### Model Architecture

- **Algorithm**: LightGBM (Gradient Boosting Decision Trees)
- **Objective**: Regression (safety score 0-100)
- **Features**: 20+ engineered features
- **Training**: 70% train, 15% validation, 15% test split
- **Early stopping**: Prevents overfitting

### Model Performance

After training, you'll see:
- RMSE: Root Mean Squared Error
- MAE: Mean Absolute Error
- R²: Coefficient of determination
- Feature importance ranking

## Usage Examples

### In Your Code

```python
from ml import predict_safety_score
from safety import apply_safety_guardrails

# Predict safety score
score = predict_safety_score(
    route_data, crime_data, lighting_data, 
    population_data, current_time
)

# Apply guardrails
is_valid, adjusted_score, warnings = apply_safety_guardrails(
    route_data, safety_score, current_time,
    crime_data, lighting_data, population_data
)

if not is_valid:
    print(f"Route rejected: {warnings}")
```

### API Integration

The guardrails are automatically applied in `app.py`:

```python
@app.route('/api/optimize-route', methods=['POST'])
def optimize_route():
    # ... route generation ...
    
    for route in all_routes:
        is_valid, adjusted_score, warnings = apply_safety_guardrails(
            route['route'], route['safety_score'], 
            datetime.now(), crime_data, lighting_data, population_data
        )
        
        if not is_valid:
            continue  # Skip unsafe routes
        
        route['safety_score'] = adjusted_score
        route['guardrail_warnings'] = warnings
```

## Production Logging

### Route Request Logging

Log all route requests for future model retraining:

```python
import json
import logging

logging.basicConfig(filename='logs/route_requests.log')
logger = logging.getLogger('routes')

logger.info(json.dumps({
    'timestamp': datetime.now().isoformat(),
    'start': [start_lat, start_lon],
    'end': [end_lat, end_lon],
    'route_selected': selected_route_id,
    'user_rating': user_rating  # If available
}))
```

## Model Retraining

As you collect more production data:

1. **Collect logs**: Aggregate route requests and user feedback
2. **Update training data**: Add production routes to `data/training_data.csv`
3. **Retrain model**: Run `python train.py` with updated data
4. **Evaluate**: Check model performance on new data
5. **Deploy**: Replace `models/safety_model.pkl`

## Configuration

### Guardrail Thresholds

Edit `safety/guardrails.py` to adjust safety thresholds:

```python
# Crime hotspot threshold
max_crimes = 10  # Max crimes within 0.5km

# Lighting threshold
min_lights_per_segment = 2

# Population threshold
min_population = 50

# Isolation percentage threshold
isolated_pct_threshold = 40  # 40% of route
```

### Model Parameters

Edit `ml/train.py` to tune model hyperparameters:

```python
params = {
    'objective': 'regression',
    'num_leaves': 31,
    'learning_rate': 0.05,
    'feature_fraction': 0.9,
    # ... more parameters
}
```

## Monitoring

### Check Model Status

```python
from ml.inference import get_predictor

predictor = get_predictor()
if predictor.is_trained:
    print("✅ Model loaded and ready")
    importance = predictor.get_feature_importance()
    print("Top features:", list(importance.keys())[:5])
else:
    print("⚠️  No model available - train first")
```

### Guardrail Statistics

Track guardrail rejections in production:
- Routes rejected due to crime hotspots
- Routes flagged for poor lighting
- Late-night travel warnings
- Isolation warnings

## Future Enhancements

- [ ] User feedback integration for model improvement
- [ ] Online learning from production data
- [ ] A/B testing different model versions
- [ ] Real-time model updates
- [ ] Advanced features (weather, events, traffic)
- [ ] Deep learning models (LSTM for temporal patterns)
- [ ] Ensemble methods (combine multiple models)

## Troubleshooting

### Model Not Loading

```
⚠️ No trained model found at ml/models/safety_model.pkl
Run ml/train.py to train a model
```

**Solution**: Run `python ml/train.py`

### Training Data Missing

```
FileNotFoundError: Training data not found at ml/data/training_data.csv
```

**Solution**: Run `python ml/collect_data.py` first

### Import Errors

```
ImportError: cannot import name 'apply_safety_guardrails'
```

**Solution**: Ensure you're running from the project root directory

## Dependencies

- `lightgbm>=4.1.0`: Gradient boosting framework
- `scikit-learn>=1.3.2`: ML utilities and metrics
- `pandas>=2.2.0`: Data manipulation
- `numpy>=1.26.0`: Numerical computations
- `matplotlib>=3.8.0`: Visualization (training plots)

## License

Part of the Bangalore Safe Routes project.
