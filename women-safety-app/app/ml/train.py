import pandas as pd
import joblib
from pathlib import Path
from lightgbm import LGBMRegressor
import numpy as np


DATA_PATH = Path(__file__).parent / 'data' / 'training_data.csv'
FEEDBACK_PATH = Path(__file__).parent.parent / 'user_feedback.csv'
MODEL_PATH = Path(__file__).parent / 'models' / 'safety_model.pkl'


def load_feedback_data():
    """Load and process user feedback data"""
    if not FEEDBACK_PATH.exists():
        print("⚠️ No user feedback data found")
        return None
    
    try:
        feedback_df = pd.read_csv(FEEDBACK_PATH)
        if feedback_df.empty:
            return None
        
        print(f"📊 Loaded {len(feedback_df)} feedback entries")
        
        # Create synthetic training samples from unsafe segments
        # These are areas users felt unsafe, so we assign low safety scores
        unsafe_samples = []
        for _, row in feedback_df.iterrows():
            unsafe_samples.append({
                'latitude': row['latitude'],
                'longitude': row['longitude'],
                'crime_density': 8.0,  # High crime perception
                'lighting_score': 2.0,  # Poor lighting assumption
                'population_score': 3.0,
                'traffic_score': 3.0,
                'label': 2.0  # Low safety score
            })
        
        return pd.DataFrame(unsafe_samples)
    except Exception as e:
        print(f"⚠️ Error loading feedback: {e}")
        return None


if __name__ == '__main__':
    print("\n🤖 Starting ML Model Training...")
    print("="*60)
    
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Training data not found: {DATA_PATH}")
    
    df = pd.read_csv(DATA_PATH)
    print(f"📊 Loaded {len(df)} training samples from route logs")
    
    # Load and incorporate user feedback
    feedback_df = load_feedback_data()
    if feedback_df is not None:
        print(f"📊 Incorporating {len(feedback_df)} user feedback samples")
        # Give feedback data higher weight by duplicating
        feedback_df_weighted = pd.concat([feedback_df] * 3, ignore_index=True)
        df = pd.concat([df, feedback_df_weighted], ignore_index=True)
        print(f"✅ Combined dataset: {len(df)} total samples")
    
    if df.empty:
        raise ValueError("Training data is empty")
    
    if 'label' not in df.columns:
        raise ValueError("Missing target column: label")
    
    df = df.fillna(0)
    
    feature_cols = [col for col in df.columns if col != 'label']
    X = df[feature_cols].values
    y = df['label'].values
    
    print(f"\n🎯 Training model with {len(X)} samples and {len(feature_cols)} features")
    
    model = LGBMRegressor(
        objective='regression',
        num_leaves=31,
        learning_rate=0.05,
        n_estimators=200,
        verbose=-1
    )
    
    model.fit(X, y)
    
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    model_data = {
        'model': model,
        'feature_names': feature_cols
    }
    
    joblib.dump(model_data, MODEL_PATH)
    
    print(f"✅ Model trained and saved to {MODEL_PATH}")
    print("="*60 + "\n")

