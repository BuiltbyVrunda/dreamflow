
# ============ SAFE ROUTES - ROUTING LOGIC ============
# Imported from bangalore-safe-routes

import pandas as pd
import numpy as np
import hashlib
import geocoder
from math import radians, cos, sin, asin, sqrt, atan2
from pathlib import Path
from app.safety.guardrails import apply_safety_guardrails
from app.ml.feature_extraction import extract_route_features
from app.ml.collect_data import log_route_sample

# Try to import ML inference
try:
    from app.ml.inference import predict_safety_score as ml_predict
    ML_AVAILABLE = True
except Exception:
    ML_AVAILABLE = False

# Load safety data
print("\\n=== Loading Safe Routes Data ===")
try:
    crime_data = pd.read_csv('app/data/bangalore_crimes.csv')
    lighting_data = pd.read_csv('app/data/bangalore_lighting.csv')
    population_data = pd.read_csv('app/data/bangalore_population.csv')
    print(f"✅ Loaded {len(crime_data)} crime records")
    print(f"✅ Loaded {len(lighting_data)} lighting points")
    print(f"✅ Loaded {len(population_data)} population points")
except Exception as e:
    print(f"❌ Error loading routing data: {e}")
    # Initialize empty dataframes as fallback
    crime_data = pd.DataFrame(columns=['Latitude', 'Longitude'])
    lighting_data = pd.DataFrame(columns=['Latitude', 'Longitude', 'lighting_score'])
    population_data = pd.DataFrame(columns=['Latitude', 'Longitude', 'population_density', 'traffic_level', 'is_main_road'])
