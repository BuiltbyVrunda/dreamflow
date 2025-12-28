from datetime import datetime
import numpy as np


def extract_route_features(route: dict, safety_metrics: dict, current_time: datetime) -> dict:
    features = {}
    
    features['distance_km'] = float(route.get('distance_km', 0))
    features['duration_min'] = float(route.get('duration_min', 0))
    features['main_road_percentage'] = float(route.get('main_road_percentage', 0))
    
    features['crime_density'] = float(safety_metrics.get('crime_density', 0))
    features['max_crime_exposure'] = float(safety_metrics.get('max_crime_exposure', 0))
    features['lighting_score'] = float(safety_metrics.get('lighting_score', 0))
    features['population_score'] = float(safety_metrics.get('population_score', 0))
    features['traffic_score'] = float(safety_metrics.get('traffic_score', 0))
    features['crime_hotspot_percentage'] = float(safety_metrics.get('crime_hotspot_percentage', 0))
    
    features['hour_of_day'] = current_time.hour
    features['day_of_week'] = current_time.weekday()
    features['is_weekend'] = 1 if current_time.weekday() >= 5 else 0
    features['is_night'] = 1 if current_time.hour < 6 or current_time.hour >= 22 else 0
    features['is_rush_hour'] = 1 if (7 <= current_time.hour <= 10) or (17 <= current_time.hour <= 20) else 0
    
    features['speed_kmh'] = features['distance_km'] / (features['duration_min'] / 60) if features['duration_min'] > 0 else 0
    features['crime_per_km'] = features['crime_density'] / features['distance_km'] if features['distance_km'] > 0 else 0
    features['lighting_per_km'] = features['lighting_score'] * features['distance_km']
    features['crime_to_lighting_ratio'] = features['crime_density'] / (features['lighting_score'] + 1)
    features['crime_to_population_ratio'] = features['crime_density'] / (features['population_score'] + 1)
    
    features['night_crime_risk'] = features['crime_density'] * 1.5 if features['is_night'] else 0
    features['night_lighting_deficit'] = (10 - features['lighting_score']) if features['is_night'] else 0
    
    return features
