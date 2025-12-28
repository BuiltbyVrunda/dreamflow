#!/bin/bash
# ML Module Setup Script
# This script will enable ML for the women-safety-app routing system

set -e  # Exit on error

echo "🤖 Starting ML Module Setup..."
echo "================================"
echo ""

# Step 1: Install dependencies
echo "📦 Step 1/3: Installing ML dependencies..."
pip install lightgbm>=4.1.0 scikit-learn>=1.3.2 matplotlib>=3.8.0 --quiet
echo "✅ Dependencies installed"
echo ""

# Step 2: Generate training data
echo "📊 Step 2/3: Generating synthetic training data..."
cd /Users/chiranth/Documents/dreamflow/women-safety-app
python3 -c "
import pandas as pd
import numpy as np
from pathlib import Path
import os

# Create directories
data_dir = Path('app/ml/data')
data_dir.mkdir(parents=True, exist_ok=True)

# Generate synthetic training data (5000 samples)
print('Generating 5000 training samples...')
np.random.seed(42)

samples = []
for i in range(5000):
    # Random route features
    distance_km = np.random.uniform(1, 20)
    duration_min = distance_km * np.random.uniform(3, 8)
    main_road_pct = np.random.uniform(0, 100)
    
    # Safety features
    crime_density = np.random.exponential(2)
    lighting_score = np.random.uniform(0, 10)
    population_score = np.random.uniform(0, 10)
    
    # Temporal features
    hour = np.random.randint(0, 24)
    day_of_week = np.random.randint(0, 7)
    is_night = 1 if hour < 6 or hour >= 22 else 0
    is_weekend = 1 if day_of_week >= 5 else 0
    
    # Calculate label (safety score 0-100)
    # Higher lighting, population, main roads = safer
    # Higher crime = less safe
    # Night time reduces safety
    base_score = 70
    crime_penalty = min(40, crime_density * 5)
    lighting_bonus = lighting_score * 2
    population_bonus = population_score * 1.5
    main_road_bonus = main_road_pct * 0.1
    night_penalty = 15 if is_night else 0
    
    safety_score = base_score - crime_penalty + lighting_bonus + population_bonus + main_road_bonus - night_penalty
    safety_score = np.clip(safety_score, 0, 100)
    
    samples.append({
        'distance_km': distance_km,
        'duration_min': duration_min,
        'main_road_percentage': main_road_pct,
        'crime_density': crime_density,
        'max_crime_exposure': crime_density * 1.2,
        'lighting_score': lighting_score,
        'population_score': population_score,
        'traffic_score': np.random.uniform(0, 10),
        'crime_hotspot_percentage': np.random.uniform(0, 50),
        'hour_of_day': hour,
        'day_of_week': day_of_week,
        'is_weekend': is_weekend,
        'is_night': is_night,
        'is_rush_hour': 1 if (7 <= hour <= 10) or (17 <= hour <= 20) else 0,
        'speed_kmh': distance_km / (duration_min / 60) if duration_min > 0 else 0,
        'crime_per_km': crime_density / distance_km if distance_km > 0 else 0,
        'lighting_per_km': lighting_score * distance_km,
        'crime_to_lighting_ratio': crime_density / (lighting_score + 1),
        'crime_to_population_ratio': crime_density / (population_score + 1),
        'night_crime_risk': crime_density * 1.5 if is_night else 0,
        'night_lighting_deficit': (10 - lighting_score) if is_night else 0,
        'label': safety_score
    })

df = pd.DataFrame(samples)
output_file = data_dir / 'training_data.csv'
df.to_csv(output_file, index=False)
print(f'✅ Generated {len(df)} training samples')
print(f'✅ Saved to {output_file}')
"
echo "✅ Training data generated"
echo ""

# Step 3: Train model
echo "🎯 Step 3/3: Training LightGBM model..."
python3 app/ml/train.py
echo ""

# Verify
echo "================================"
echo "✅ ML Module Setup Complete!"
echo ""
echo "To verify ML is working, start your app and run:"
echo "  curl -k https://localhost:5000/api/ml-model-info"
echo ""
