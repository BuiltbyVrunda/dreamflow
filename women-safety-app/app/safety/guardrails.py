"""
Safety Guardrails
Hard constraints and safety checks for route validation
"""

import pandas as pd
import numpy as np
from datetime import datetime, time
from math import radians, cos, sin, asin, sqrt

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate haversine distance between two points in km"""
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    return 6371 * c

def check_crime_hotspots(route_coords, crime_data, threshold_distance=0.5, max_crimes=20):
    """
    Check if route passes through high-crime areas
    
    Args:
        route_coords: List of (lat, lon) tuples
        crime_data: DataFrame with crime records
        threshold_distance: Distance in km to consider "nearby" crimes
        max_crimes: Maximum allowed crimes within threshold (relaxed to 20)
    
    Returns:
        (is_safe, crime_count, warnings)
    """
    warnings = []
    max_crime_count = 0
    hotspot_locations = []
    
    for lat, lon in route_coords:
        # Count nearby crimes
        nearby_crimes = crime_data[
            (abs(crime_data['Latitude'] - lat) < threshold_distance / 111) &
            (abs(crime_data['Longitude'] - lon) < threshold_distance / 111)
        ]
        
        crime_count = len(nearby_crimes)
        
        if crime_count > max_crime_count:
            max_crime_count = crime_count
        
        if crime_count > max_crimes:
            hotspot_locations.append((lat, lon, crime_count))
    
    is_safe = max_crime_count <= max_crimes
    
    if not is_safe:
        warnings.append(
            f"Route passes through {len(hotspot_locations)} crime hotspot(s) "
            f"(max {max_crime_count} crimes within {threshold_distance}km)"
        )
    
    return is_safe, max_crime_count, warnings

def check_lighting_coverage(route_coords, lighting_data, min_lights_per_segment=2):
    """
    Check if route has adequate lighting
    
    Args:
        route_coords: List of (lat, lon) tuples
        lighting_data: DataFrame with lighting points
        min_lights_per_segment: Minimum lights required per route segment
    
    Returns:
        (is_safe, avg_lights, warnings)
    """
    warnings = []
    light_counts = []
    poorly_lit_segments = 0
    
    for lat, lon in route_coords:
        # Count nearby lights (smaller radius for stricter check)
        nearby_lights = lighting_data[
            (abs(lighting_data['Latitude'] - lat) < 0.005) &
            (abs(lighting_data['Longitude'] - lon) < 0.005)
        ]
        
        light_count = len(nearby_lights)
        light_counts.append(light_count)
        
        if light_count < min_lights_per_segment:
            poorly_lit_segments += 1
    
    avg_lights = np.mean(light_counts) if light_counts else 0
    poorly_lit_pct = (poorly_lit_segments / len(route_coords) * 100) if route_coords else 0
    
    is_safe = poorly_lit_pct < 30  # Less than 30% of route poorly lit
    
    if not is_safe:
        warnings.append(
            f"Route has inadequate lighting: {poorly_lit_pct:.1f}% of segments "
            f"have fewer than {min_lights_per_segment} lights"
        )
    
    return is_safe, avg_lights, warnings

def check_isolated_areas(route_coords, population_data, min_population=50):
    """
    Check if route passes through isolated/unpopulated areas
    
    Args:
        route_coords: List of (lat, lon) tuples
        population_data: DataFrame with population density
        min_population: Minimum population threshold
    
    Returns:
        (is_safe, avg_population, warnings)
    """
    warnings = []
    population_scores = []
    isolated_segments = 0
    
    for lat, lon in route_coords:
        # Check nearby population
        nearby_pop = population_data[
            (abs(population_data['Latitude'] - lat) < 0.005) &
            (abs(population_data['Longitude'] - lon) < 0.005)
        ]
        
        if len(nearby_pop) > 0:
            pop_score = nearby_pop['population'].mean()
        else:
            pop_score = 0
        
        population_scores.append(pop_score)
        
        if pop_score < min_population:
            isolated_segments += 1
    
    avg_population = np.mean(population_scores) if population_scores else 0
    isolated_pct = (isolated_segments / len(route_coords) * 100) if route_coords else 0
    
    is_safe = isolated_pct < 75  # Less than 75% isolated (very relaxed)
    
    if not is_safe:
        warnings.append(
            f"Route passes through isolated areas: {isolated_pct:.1f}% of segments "
            f"have population < {min_population}"
        )
    
    return is_safe, avg_population, warnings

def check_time_based_safety(current_time, route_duration_seconds):
    """
    Check time-based safety factors
    
    Args:
        current_time: datetime object
        route_duration_seconds: Estimated route duration
    
    Returns:
        (is_safe, time_factor, warnings)
    """
    warnings = []
    hour = current_time.hour
    
    # Check if travel occurs during dangerous hours
    is_late_night = 23 <= hour or hour < 5
    is_early_morning = 5 <= hour < 7
    
    time_factor = 1.0
    is_safe = True
    
    if is_late_night:
        time_factor = 0.5  # 50% penalty for late night
        warnings.append("Travel during late night hours (11 PM - 5 AM) significantly increases risk")
        is_safe = False
    elif is_early_morning:
        time_factor = 0.8  # 20% penalty for early morning
        warnings.append("Travel during early morning hours (5 AM - 7 AM) moderately increases risk")
    
    # Check if route extends into dangerous hours
    end_time = current_time.timestamp() + route_duration_seconds
    end_hour = datetime.fromtimestamp(end_time).hour
    
    if not is_late_night and (23 <= end_hour or end_hour < 5):
        warnings.append("Route extends into late night hours")
        time_factor *= 0.8
    
    return is_safe, time_factor, warnings

def apply_safety_guardrails(route_data, safety_score, current_time=None, 
                            crime_data=None, lighting_data=None, population_data=None):
    """
    Apply comprehensive safety guardrails to a route
    
    Args:
        route_data: Route information dict with steps
        safety_score: Initial safety score (0-100)
        current_time: datetime object for time-based checks
        crime_data, lighting_data, population_data: Safety datasets
    
    Returns:
        (is_valid, adjusted_score, warnings_list)
    """
    if current_time is None:
        current_time = datetime.now()
    
    warnings = []
    is_valid = True
    adjusted_score = safety_score
    
    # Extract route coordinates
    route_coords = []
    steps = route_data.get('steps', [])
    for step in steps:
        if 'start_location' in step:
            route_coords.append((
                step['start_location']['lat'],
                step['start_location']['lng']
            ))
        if 'end_location' in step:
            route_coords.append((
                step['end_location']['lat'],
                step['end_location']['lng']
            ))
    
    # Time-based safety check
    route_duration = route_data.get('duration', 0)
    time_safe, time_factor, time_warnings = check_time_based_safety(
        current_time, route_duration
    )
    warnings.extend(time_warnings)
    adjusted_score *= time_factor
    
    # Only fail validation for very late night (not early morning)
    if not time_safe and current_time.hour >= 0 and current_time.hour < 3:
        is_valid = False
    
    # Crime hotspot check (if data available)
    if crime_data is not None and len(route_coords) > 0:
        crime_safe, crime_count, crime_warnings = check_crime_hotspots(
            route_coords, crime_data
        )
        warnings.extend(crime_warnings)
        
        if not crime_safe:
            # Don't fail validation, just apply penalty
            adjusted_score *= 0.7  # 30% penalty for crime hotspots
    
    # Lighting check (if data available)
    if lighting_data is not None and len(route_coords) > 0:
        lighting_safe, avg_lights, lighting_warnings = check_lighting_coverage(
            route_coords, lighting_data
        )
        warnings.extend(lighting_warnings)
        
        if not lighting_safe and (current_time.hour < 6 or current_time.hour >= 20):
            # Don't fail validation, just apply penalty even if dark AND poorly lit
            adjusted_score *= 0.8  # 20% penalty for poor lighting
    
    # Isolation check (if data available)
    if population_data is not None and len(route_coords) > 0:
        isolation_safe, avg_pop, isolation_warnings = check_isolated_areas(
            route_coords, population_data
        )
        warnings.extend(isolation_warnings)
        
        if not isolation_safe:
            # Don't fail validation, but apply penalty
            adjusted_score *= 0.8  # 20% penalty for isolation
    
    # Ensure score stays in valid range
    adjusted_score = np.clip(adjusted_score, 0, 100)
    
    return is_valid, adjusted_score, warnings

def validate_route_safety(route_data, crime_data, lighting_data, 
                         population_data, current_time=None):
    """
    Simplified route safety validation
    
    Returns:
        (is_safe, safety_metrics)
    """
    _, adjusted_score, warnings = apply_safety_guardrails(
        route_data, 50,  # Start with neutral score
        current_time, crime_data, lighting_data, population_data
    )
    
    is_safe = len(warnings) == 0 and adjusted_score >= 40
    
    metrics = {
        'adjusted_score': adjusted_score,
        'warnings': warnings,
        'is_safe': is_safe
    }
    
    return is_safe, metrics
