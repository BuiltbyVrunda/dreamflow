from flask import Flask, jsonify, request
from flask_cors import CORS
import pandas as pd
import numpy as np
from datetime import datetime
import requests
import os
from pathlib import Path
from dotenv import load_dotenv
import geocoder
from math import radians, cos, sin, asin, sqrt, atan2
import hashlib
from sqlalchemy import text

load_dotenv()

import os
base_dir = os.path.dirname(os.path.abspath(__file__))
template_dir = os.path.join(base_dir, 'app', 'templates')
static_dir = os.path.join(base_dir, 'app', 'static')

app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
CORS(app)

# Load configuration from config.py
from config import Config
app.config.from_object(Config)

# Additional app configuration for database and sessions
app.config['SECRET_KEY'] = app.config.get('SECRET_KEY', 'your-secret-key-change-this-in-production-2024')
app.config['UPLOAD_FOLDER'] = app.config.get('UPLOAD_FOLDER', 'app/uploads/evidence')
app.config['MAX_CONTENT_LENGTH'] = app.config.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024)

# Database configuration
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'instance', 'women_safety.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
from app.models import db
from app.auth_models import User
db.init_app(app)

# Import ML and safety features
from app.safety.guardrails import apply_safety_guardrails
from app.ml.feature_extraction import extract_route_features
from app.ml.collect_data import log_route_sample

try:
    from app.ml.inference import predict_safety_score as ml_predict
    ML_AVAILABLE = True
except Exception:
    ML_AVAILABLE = False

# Create tables and run migrations
with app.app_context():
    db.create_all()
    # Lightweight migration: add new columns if missing (SQLite only)
    try:
        with db.engine.connect() as conn:
            # Migrate users table
            res = conn.execute(text("PRAGMA table_info(users);"))
            existing_cols = {row[1] for row in res}
            user_cols = {
                'username': 'VARCHAR(50)',
                'home_city_district': 'TEXT',
                'address': 'TEXT',
                'age_range': 'TEXT',
                'gender_presentation': 'TEXT',
                'allergies': 'TEXT',
                'chronic_conditions': 'TEXT',
                'disability': 'TEXT',
                'primary_contact_name': 'TEXT',
                'primary_contact_phone': 'TEXT',
                'secondary_contact': 'TEXT',
                'consent_share_with_police': 'INTEGER',
                'consent_share_photo_with_police': 'INTEGER',
                'data_retention': 'TEXT'
            }
            for col, typ in user_cols.items():
                if col not in existing_cols:
                    try:
                        conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} {typ};"))
                        conn.commit()
                    except Exception:
                        pass
            
            # Migrate incident_reports for additional_details
            res2 = conn.execute(text("PRAGMA table_info(incident_reports);"))
            existing_cols_ir = {row[1] for row in res2}
            if 'additional_details' not in existing_cols_ir:
                try:
                    conn.execute(text("ALTER TABLE incident_reports ADD COLUMN additional_details TEXT;"))
                    conn.commit()
                except Exception:
                    pass
            
            # Migrate community_posts for username system
            res3 = conn.execute(text("PRAGMA table_info(community_posts);"))
            existing_cols_cp = {row[1] for row in res3}
            community_cols = {
                'user_id': 'INTEGER',
                'username': 'VARCHAR(50)',
                'is_anonymous': 'INTEGER DEFAULT 1'
            }
            for col, typ in community_cols.items():
                if col not in existing_cols_cp:
                    try:
                        conn.execute(text(f"ALTER TABLE community_posts ADD COLUMN {col} {typ};"))
                        conn.commit()
                    except Exception:
                        pass
            
            # Migrate comments for username system
            res4 = conn.execute(text("PRAGMA table_info(comments);"))
            existing_cols_c = {row[1]: row[2] for row in res4}
            
            comment_cols = {
                'username': 'VARCHAR(50)',
                'is_anonymous': 'INTEGER DEFAULT 1'
            }
            for col, typ in comment_cols.items():
                if col not in existing_cols_c:
                    try:
                        conn.execute(text(f"ALTER TABLE comments ADD COLUMN {col} {typ};"))
                        conn.commit()
                    except Exception:
                        pass
            
            # Add user_id if it doesn't exist at all
            if 'user_id' not in existing_cols_c:
                try:
                    conn.execute(text("ALTER TABLE comments ADD COLUMN user_id INTEGER;"))
                    conn.commit()
                except Exception:
                    pass
    except Exception as e:
        print(f"Migration warning: {e}")
        pass

# Register blueprints
from app import routes
app.register_blueprint(routes.bp)

# Context processor to add today's date
@app.context_processor
def inject_today():
    return {'today': datetime.now().strftime('%Y-%m-%d')}

print("\n=== Initializing Safe Routes Backend ===")

try:
    print("Loading safety data...")
    import os
    base_dir = os.path.dirname(os.path.abspath(__file__))
    crime_data = pd.read_csv(os.path.join(base_dir, 'app', 'data', 'bangalore_crimes.csv'))
    lighting_data = pd.read_csv(os.path.join(base_dir, 'app', 'data', 'bangalore_lighting.csv'))
    population_data = pd.read_csv(os.path.join(base_dir, 'app', 'data', 'bangalore_population.csv'))
    print(f"✅ Loaded {len(crime_data)} crime records")
    print(f"✅ Loaded {len(lighting_data)} lighting points")
    print(f"✅ Loaded {len(population_data)} population points")
except Exception as e:
    print(f"❌ Error loading data: {e}")
    raise

def validate_coordinates(lat, lon):
    BANGALORE_BOUNDS = {
        'min_lat': 12.704192, 'max_lat': 13.173706,
        'min_lon': 77.269876, 'max_lon': 77.850066
    }
    try:
        lat, lon = float(lat), float(lon)
        return (BANGALORE_BOUNDS['min_lat'] <= lat <= BANGALORE_BOUNDS['max_lat'] and
                BANGALORE_BOUNDS['min_lon'] <= lon <= BANGALORE_BOUNDS['max_lon'])
    except:
        return False

def haversine_distance(lat1, lon1, lat2, lon2):
    try:
        lat1, lon1, lat2, lon2 = map(radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        return c * 6371
    except Exception as e:
        print(f"❌ Error calculating distance: {e}")
        return float('inf')

def calculate_route_hash(route):
    if not route or len(route) < 2:
        return None
    sample_indices = [0, len(route)//4, len(route)//2, 3*len(route)//4, len(route)-1]
    sample_points = [route[i] for i in sample_indices if i < len(route)]
    hash_string = ''.join([f"{lat:.4f},{lon:.4f}" for lat, lon in sample_points])
    return hashlib.md5(hash_string.encode()).hexdigest()

def calculate_crime_exposure(lat, lon, radius=0.003):
    try:
        nearby_crimes = crime_data[
            (abs(crime_data['Latitude'] - lat) < radius) &
            (abs(crime_data['Longitude'] - lon) < radius)
        ]
        return len(nearby_crimes)
    except Exception as e:
        print(f"❌ Error calculating crime: {e}")
        return 0

def calculate_lighting_score(lat, lon, radius=0.005):
    try:
        nearby_lighting = lighting_data[
            (abs(lighting_data['Latitude'] - lat) < radius) &
            (abs(lighting_data['Longitude'] - lon) < radius)
        ]
        return nearby_lighting['lighting_score'].mean() if len(nearby_lighting) > 0 else 5.0
    except:
        return 5.0

def calculate_population_score(lat, lon, radius=0.005):
    try:
        nearby_pop = population_data[
            (abs(population_data['Latitude'] - lat) < radius) &
            (abs(population_data['Longitude'] - lon) < radius)
        ]
        if len(nearby_pop) > 0:
            return (
                nearby_pop['population_density'].mean() / 1000,
                nearby_pop['traffic_level'].mean() / 10,
                nearby_pop['is_main_road'].mean() > 0.5
            )
        return 5.0, 5.0, False
    except:
        return 5.0, 5.0, False

def validate_route_connectivity(route_points, max_gap_km=0.5):
    """
    Validate that route points are properly connected without large gaps
    Returns True if route is continuous, False if there are disconnected segments
    """
    if len(route_points) < 2:
        return False
    
    for i in range(len(route_points) - 1):
        current_point = route_points[i]
        next_point = route_points[i + 1]
        
        gap_distance = haversine_distance(
            current_point[0], current_point[1],
            next_point[0], next_point[1]
        )
        
        if gap_distance > max_gap_km:
            return False
    
    return True

def check_route_main_road_coverage(route_points, min_coverage=0.4):
    """
    Check if route has sufficient main road coverage
    Returns (has_coverage, main_road_percentage)
    """
    if len(route_points) < 2:
        return False, 0.0
    
    main_road_count = 0
    sample_points = min(len(route_points), 20)
    step = len(route_points) // sample_points
    
    for i in range(0, len(route_points), max(1, step)):
        if i >= len(route_points):
            break
        lat, lon = route_points[i]
        _, _, is_main = calculate_population_score(lat, lon, radius=0.003)
        if is_main:
            main_road_count += 1
    
    total_sampled = min(sample_points, len(route_points))
    coverage = main_road_count / total_sampled if total_sampled > 0 else 0
    
    return coverage >= min_coverage, coverage * 100

def detect_route_backtracking(route_points, start_lat, start_lon, end_lat, end_lon):
    """
    Detect if route has unnecessary back-tracking or detours
    Returns True if route is efficient, False if it has detours
    """
    if len(route_points) < 5:
        return True
    
    # Calculate direct distance from start to end
    direct_distance = haversine_distance(start_lat, start_lon, end_lat, end_lon)
    
    if direct_distance < 0.1:  # Very short route
        return True
    
    # Calculate actual route distance
    actual_distance = 0
    for i in range(len(route_points) - 1):
        actual_distance += haversine_distance(
            route_points[i][0], route_points[i][1],
            route_points[i + 1][0], route_points[i + 1][1]
        )
    
    # Stricter ratio: route should be max 1.3x direct distance
    detour_ratio = actual_distance / direct_distance
    if detour_ratio > 1.3:
        return False
    
    # Check for back-tracking: measure progress toward destination
    sample_size = min(20, len(route_points))
    step = max(1, len(route_points) // sample_size)
    
    backtrack_count = 0
    stagnant_count = 0
    
    for i in range(0, len(route_points) - step, step):
        if i + step >= len(route_points):
            break
            
        current_point = route_points[i]
        next_point = route_points[i + step]
        
        # Distance from current point to destination
        current_to_dest = haversine_distance(
            current_point[0], current_point[1],
            end_lat, end_lon
        )
        
        # Distance from next point to destination  
        next_to_dest = haversine_distance(
            next_point[0], next_point[1],
            end_lat, end_lon
        )
        
        # Calculate progress (negative = moving away)
        progress = current_to_dest - next_to_dest
        
        # If moving away from destination
        if progress < 0:
            backtrack_count += 1
        # If barely making progress (stagnant)
        elif progress < 0.01:
            stagnant_count += 1
    
    total_segments = len(range(0, len(route_points) - step, step))
    
    # Reject if more than 20% of segments move away from destination
    if backtrack_count > (total_segments * 0.2):
        return False
    
    # Reject if more than 40% of segments are stagnant or backtracking
    if (backtrack_count + stagnant_count) > (total_segments * 0.4):
        return False
    
    # Additional check: measure maximum deviation from direct line
    max_deviation = 0
    for point in route_points[::max(1, len(route_points) // 10)]:
        # Calculate perpendicular distance from point to direct line
        # Using simplified cross-track distance
        lat, lon = point
        
        # Distance from point to start
        d_start = haversine_distance(start_lat, start_lon, lat, lon)
        # Distance from point to end
        d_end = haversine_distance(lat, lon, end_lat, end_lon)
        
        # If point is much further from both start and end than direct distance
        # it's likely a detour
        if d_start > direct_distance * 0.7 and d_end > direct_distance * 0.7:
            max_deviation = max(max_deviation, min(d_start, d_end))
    
    # If maximum deviation is more than 30% of direct distance, reject
    if max_deviation > direct_distance * 0.3:
        return False
    
    return True

def calculate_route_safety_comprehensive(route, preferences=None):
    if not route or len(route) < 2:
        return None
    
    if preferences is None:
        preferences = {}
    
    try:
        sample_rate = max(1, len(route) // 50)
        sampled_route = route[::sample_rate]
        
        total_crime = 0
        max_crime_at_point = 0
        crime_hotspot_count = 0
        total_lighting = 0
        total_population = 0
        total_traffic = 0
        main_road_count = 0
        
        for lat, lon in sampled_route:
            crime_count = calculate_crime_exposure(lat, lon, radius=0.003)
            total_crime += crime_count
            max_crime_at_point = max(max_crime_at_point, crime_count)
            if crime_count > 3:
                crime_hotspot_count += 1
            
            light_score = calculate_lighting_score(lat, lon, radius=0.005)
            total_lighting += light_score
            
            pop_score, traffic_score, is_main_road = calculate_population_score(lat, lon, radius=0.005)
            total_population += pop_score
            total_traffic += traffic_score
            if is_main_road:
                main_road_count += 1
        
        n_points = len(sampled_route)
        
        avg_crime = total_crime / n_points
        avg_lighting = total_lighting / n_points
        avg_population = total_population / n_points
        avg_traffic = total_traffic / n_points
        main_road_pct = (main_road_count / n_points) * 100
        crime_hotspot_pct = (crime_hotspot_count / n_points) * 100
        
        base_crime_penalty = min(40, avg_crime ** 1.2 * 5)
        max_crime_penalty = min(40, max_crime_at_point ** 1.4 * 7)
        hotspot_penalty = min(30, crime_hotspot_pct * 0.5)
        
        total_crime_penalty = base_crime_penalty + max_crime_penalty + hotspot_penalty
        
        base_safety_score = max(0, 100 - total_crime_penalty)
        
        lighting_multiplier = 1.0 + (avg_lighting / 10) * (2.5 if preferences.get('prefer_well_lit') else 0.8)
        population_multiplier = 1.0 + (avg_population / 10) * (2.0 if preferences.get('prefer_populated') else 0.6)
        traffic_multiplier = 1.0 + (avg_traffic / 10) * (1.5 if preferences.get('prefer_populated') else 0.4)
        main_road_multiplier = 1.0 + (main_road_pct / 100) * (2.5 if preferences.get('prefer_main_roads') else 0.7)
        
        total_multiplier = (lighting_multiplier + population_multiplier + traffic_multiplier + main_road_multiplier) / 4
        
        final_safety_score = min(100, base_safety_score * total_multiplier)
        
        crime_density_score = 100 - min(100, avg_crime * 10)
        
        return {
            'safety_score': round(final_safety_score, 2),
            'crime_density': round(avg_crime, 2),
            'max_crime_exposure': round(max_crime_at_point, 2),
            'crime_hotspot_percentage': round(crime_hotspot_pct, 2),
            'lighting_score': round(avg_lighting, 2),
            'population_score': round(avg_population, 2),
            'traffic_score': round(avg_traffic, 2),
            'main_road_percentage': round(main_road_pct, 2),
            'crime_density_score': round(crime_density_score, 2)
        }
        
    except Exception as e:
        print(f"❌ Error calculating safety: {e}")
        return None

def get_route_from_osrm(start_lat, start_lon, end_lat, end_lon, waypoint=None):
    try:
        if not all(validate_coordinates(x, y) for x, y in [(start_lat, start_lon), (end_lat, end_lon)]):
            return None
        
        if waypoint:
            url = f"http://router.project-osrm.org/route/v1/driving/{start_lon},{start_lat};{waypoint['lon']},{waypoint['lat']};{end_lon},{end_lat}"
        else:
            url = f"http://router.project-osrm.org/route/v1/driving/{start_lon},{start_lat};{end_lon},{end_lat}"
        
        params = {
            'overview': 'full',
            'geometries': 'geojson',
            'alternatives': 'true',
            'steps': 'true'
        }
        
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if data['code'] != 'Ok':
            return None
        
        routes = []
        for route_data in data.get('routes', []):
            if 'geometry' not in route_data:
                continue
            
            coordinates = route_data['geometry']['coordinates']
            if not coordinates or len(coordinates) < 2:
                continue
            
            route = [[coord[1], coord[0]] for coord in coordinates]
            
            start_dist = haversine_distance(start_lat, start_lon, route[0][0], route[0][1])
            end_dist = haversine_distance(end_lat, end_lon, route[-1][0], route[-1][1])
            
            if start_dist > 0.2 or end_dist > 0.2:
                continue
            
            # Extract turn-by-turn instructions from OSRM
            steps = []
            if 'legs' in route_data:
                step_number = 1
                for leg in route_data['legs']:
                    if 'steps' in leg:
                        for step in leg['steps']:
                            if 'maneuver' in step:
                                instruction = step['maneuver'].get('instruction', step.get('name', 'Continue'))
                                distance = step.get('distance', 0)
                                steps.append({
                                    'number': step_number,
                                    'instruction': instruction,
                                    'distance': round(distance, 1),
                                    'distance_text': f"{distance:.0f}m" if distance < 1000 else f"{distance/1000:.1f}km"
                                })
                                step_number += 1
            
            routes.append({
                'route': route,
                'distance_km': route_data['distance'] / 1000,
                'duration_min': route_data['duration'] / 60,
                'waypoint': waypoint,
                'steps': steps
            })
        
        return routes
        
    except Exception as e:
        print(f"❌ OSRM error: {e}")
        return None

def calculate_composite_score(route, preferences):
    safety_weight = preferences.get('safety_weight', 0.7)
    distance_weight = preferences.get('distance_weight', 0.3)
    
    safety_score = route.get('safety_score', 50)
    distance_km = route.get('distance_km', 10)
    crime_density = route.get('crime_density', 5)
    max_crime = route.get('max_crime_exposure', 5)
    
    normalized_safety = safety_score / 100
    normalized_distance = max(0, 1 - (distance_km / 30))
    
    crime_penalty = (crime_density * 0.3 + max_crime * 0.7) / 20
    crime_penalty = min(1, crime_penalty)
    
    safety_component = normalized_safety * (1 - crime_penalty * 0.5)
    
    preference_bonus = 0
    if preferences.get('prefer_main_roads'):
        main_road_pct = route.get('main_road_percentage', 0)
        # Strong bonus for main roads when preference is enabled
        preference_bonus += (main_road_pct / 100) * 0.35
        # Extra bonus for high main road coverage
        if main_road_pct > 70:
            preference_bonus += 0.15
    
    if preferences.get('prefer_well_lit'):
        lighting_score = route.get('lighting_score', 5)
        preference_bonus += (lighting_score / 10) * 0.15
    
    if preferences.get('prefer_populated'):
        population_score = route.get('population_score', 5)
        preference_bonus += (population_score / 10) * 0.15
    
    composite_score = (safety_component * safety_weight + 
                      normalized_distance * distance_weight + 
                      preference_bonus)
    
    return composite_score

@app.route('/api/optimize-route', methods=['POST'])
def optimize_route():
    print("\n" + "="*60)
    print("=== OPTIMIZED ROUTE CALCULATION ===")
    print("="*60)
    
    try:
        data = request.json or {}
        if not all(k in data for k in ('start_lat', 'start_lon', 'end_lat', 'end_lon')):
            return jsonify({'success': False, 'error': 'Missing coordinates'}), 400

        try:
            start_lat = float(data.get('start_lat'))
            start_lon = float(data.get('start_lon'))
            end_lat = float(data.get('end_lat'))
            end_lon = float(data.get('end_lon'))
        except (TypeError, ValueError):
            return jsonify({'success': False, 'error': 'Invalid coordinates'}), 400

        preferences = {
            'prefer_main_roads': bool(data.get('prefer_main_roads', False)),
            'prefer_well_lit': bool(data.get('prefer_well_lit', False)),
            'prefer_populated': bool(data.get('prefer_populated', False)),
            'safety_weight': float(data.get('safety_weight', 0.7)),
            'distance_weight': float(data.get('distance_weight', 0.3))
        }
        
        print(f"\nRequest:")
        print(f"  Start: ({start_lat:.5f}, {start_lon:.5f})")
        print(f"  End: ({end_lat:.5f}, {end_lon:.5f})")
        print(f"  Safety weight: {preferences['safety_weight']:.2f}")
        print(f"  Distance weight: {preferences['distance_weight']:.2f}")
        print(f"  Main roads: {preferences['prefer_main_roads']}")
        print(f"  Well lit: {preferences['prefer_well_lit']}")
        print(f"  Populated: {preferences['prefer_populated']}")
        
        if not all(validate_coordinates(x, y) for x, y in [(start_lat, start_lon), (end_lat, end_lon)]):
            return jsonify({'success': False, 'error': 'Coordinates outside Bangalore'}), 400
        
        all_routes = []
        route_hashes = set()
        
        print("\n--- Phase 1: Direct Routes ---")
        direct_routes = get_route_from_osrm(start_lat, start_lon, end_lat, end_lon, waypoint=None)
        
        if direct_routes:
            print(f"OSRM returned {len(direct_routes)} direct alternatives")
            for idx, route_data in enumerate(direct_routes):
                route_points = route_data['route']
                
                if not validate_route_connectivity(route_points, max_gap_km=0.5):
                    print(f"❌ Direct route {idx+1}: Rejected - disconnected segments")
                    continue
                
                if not detect_route_backtracking(route_points, start_lat, start_lon, end_lat, end_lon):
                    print(f"❌ Direct route {idx+1}: Rejected - unnecessary detour/back-tracking")
                    continue
                
                route_hash = calculate_route_hash(route_points)
                if route_hash and route_hash not in route_hashes:
                    safety = calculate_route_safety_comprehensive(route_points, preferences)
                    if safety:
                        has_main, main_pct = check_route_main_road_coverage(route_points)
                        
                        # Filter by main road preference if enabled
                        if preferences.get('prefer_main_roads') and main_pct < 40:
                            print(f"⏭️  Direct route {idx+1}: Skipped - {main_pct:.0f}% main roads (need 40%+)")
                            continue
                        
                        route_data.update(safety)
                        route_data['source'] = f'direct_{idx+1}'
                        route_data['type'] = 'direct'
                        all_routes.append(route_data)
                        route_hashes.add(route_hash)
                        
                        main_status = f"main roads: {main_pct:.0f}%" if has_main else f"local roads: {main_pct:.0f}%"
                        print(f"✅ Direct route {idx+1}: {route_data['distance_km']:.2f}km, safety={safety['safety_score']:.1f}, {main_status}")
        
        print("\n--- Phase 2: Strategic Waypoint Exploration ---")
        
        base_distance = haversine_distance(start_lat, start_lon, end_lat, end_lon)
        
        lat_diff = end_lat - start_lat
        lon_diff = end_lon - start_lon
        
        perp_lat = -lon_diff
        perp_lon = lat_diff
        perp_magnitude = sqrt(perp_lat**2 + perp_lon**2)
        
        if perp_magnitude > 0:
            perp_lat /= perp_magnitude
            perp_lon /= perp_magnitude
        
        positions = [0.25, 0.5, 0.75]
        offset_distances_km = [0.5, 1.2, 2.5]
        offsets = [d / 111.0 for d in offset_distances_km]
        directions = [1, -1]
        
        waypoint_count = 0
        max_waypoints = 25
        
        for position in positions:
            if waypoint_count >= max_waypoints:
                break
                
            for offset in offsets:
                if waypoint_count >= max_waypoints:
                    break
                    
                for direction in directions:
                    if waypoint_count >= max_waypoints:
                        break
                    
                    mid_lat = start_lat + lat_diff * position
                    mid_lon = start_lon + lon_diff * position
                    
                    wp_lat = mid_lat + perp_lat * offset * direction
                    wp_lon = mid_lon + perp_lon * offset * direction
                    
                    if not validate_coordinates(wp_lat, wp_lon):
                        continue
                    
                    wp_dist = (haversine_distance(start_lat, start_lon, wp_lat, wp_lon) + 
                              haversine_distance(wp_lat, wp_lon, end_lat, end_lon))
                    detour_ratio = wp_dist / base_distance if base_distance > 0 else 999
                    
                    if detour_ratio > 1.8:
                        continue
                    
                    waypoint_routes = get_route_from_osrm(start_lat, start_lon, end_lat, end_lon, 
                                                          waypoint={'lat': wp_lat, 'lon': wp_lon})
                    
                    if waypoint_routes:
                        for route_data in waypoint_routes:
                            route_points = route_data['route']
                            
                            if not validate_route_connectivity(route_points, max_gap_km=0.5):
                                continue
                            
                            if not detect_route_backtracking(route_points, start_lat, start_lon, end_lat, end_lon):
                                continue
                            
                            route_hash = calculate_route_hash(route_points)
                            
                            if route_hash and route_hash not in route_hashes:
                                safety = calculate_route_safety_comprehensive(route_points, preferences)
                                if safety:
                                    # Filter by main road preference if enabled
                                    if preferences.get('prefer_main_roads'):
                                        main_road_pct = safety.get('main_road_percentage', 0)
                                        if main_road_pct < 40:
                                            continue  # Skip routes with less than 40% main roads
                                    
                                    route_data.update(safety)
                                    route_data['source'] = f'waypoint_{waypoint_count}'
                                    route_data['type'] = 'waypoint'
                                    
                                    all_routes.append(route_data)
                                    route_hashes.add(route_hash)
                                    waypoint_count += 1
                                    
                                    if waypoint_count >= max_waypoints:
                                        break
        
        print(f"Waypoint routes added: {waypoint_count}")
        print(f"\nTotal routes collected: {len(all_routes)}")
        
        if len(all_routes) == 0:
            return jsonify({'success': False, 'error': 'No valid routes found'}), 404
        
        print("\n--- Phase 3: Preference-Based Scoring ---")
        
        current_time = datetime.now()
        ml_predictions_made = 0
        
        for route in all_routes:
            route['composite_score'] = calculate_composite_score(route, preferences)
            
            if ML_AVAILABLE:
                try:
                    safety_metrics = {
                        'crime_density': route.get('crime_density', 0),
                        'max_crime_exposure': route.get('max_crime_exposure', 0),
                        'lighting_score': route.get('lighting_score', 0),
                        'population_score': route.get('population_score', 0),
                        'traffic_score': route.get('traffic_score', 0),
                        'crime_hotspot_percentage': route.get('crime_hotspot_percentage', 0)
                    }
                    
                    features = extract_route_features(route, safety_metrics, current_time)
                    ml_score = ml_predict(features)
                    
                    rule_based_score = route['safety_score']
                    route['safety_score'] = 0.75 * rule_based_score + 0.25 * ml_score
                    route['ml_score'] = ml_score
                    route['rule_score'] = rule_based_score
                    
                    ml_predictions_made += 1
                    print(f"  ✅ ML Model prediction - Rule: {rule_based_score:.2f}, ML: {ml_score:.2f}, Combined: {route['safety_score']:.2f}")
                    
                    log_route_sample(features, rule_based_score)
                except Exception as e:
                    print(f"  ⚠️ ML prediction failed: {e}")
                    pass
        
        if ML_AVAILABLE:
            print(f"\n🤖 ML Model Status: ACTIVE - Made {ml_predictions_made}/{len(all_routes)} predictions")
        else:
            print(f"\n⚠️ ML Model Status: DISABLED - Using rule-based scoring only")
        
        all_routes.sort(key=lambda x: x['composite_score'], reverse=True)
        
        print("\n--- Phase 4: Safety Guardrails ---")
        
        validated_routes = []
        
        for idx, route in enumerate(all_routes):
            # Apply safety guardrails
            is_valid, adjusted_score, warnings = apply_safety_guardrails(
                {'steps': route.get('route', []), 'duration': route.get('duration_min', 0) * 60},
                route['safety_score'],
                current_time,
                crime_data,
                lighting_data,
                population_data
            )
            
            if not is_valid:
                print(f"❌ Route {idx+1} rejected by guardrails: {warnings}")
                continue  # Skip this route
            
            # Update score with guardrail adjustments
            route['safety_score'] = adjusted_score
            route['guardrail_warnings'] = warnings
            
            if warnings:
                print(f"⚠️  Route {idx+1} has warnings: {warnings}")
            
            validated_routes.append(route)
            
            # Stop if we have enough good routes
            if len(validated_routes) >= 20:
                break
        
        if len(validated_routes) == 0:
            return jsonify({'success': False, 'error': 'No routes passed safety validation'}), 404
        
        print(f"Validated routes: {len(validated_routes)}")
        
        final_routes = validated_routes[:7]
        print(f"Final routes to display: {len(final_routes)}")
        
        for idx, route in enumerate(final_routes):
            route['rank'] = idx + 1
            route['is_recommended'] = (idx == 0)
            
            if idx == 0:
                category = 'best'
                emoji = '⭐'
                description = 'Best match for your preferences'
            elif route['crime_density'] <= 1.5 and route['max_crime_exposure'] <= 3:
                category = 'safest'
                emoji = '🛡️'
                description = 'Safest route (avoids crime hotspots)'
            elif route['distance_km'] <= min(r['distance_km'] for r in final_routes) * 1.05:
                category = 'fastest'
                emoji = '⚡'
                description = 'Shortest distance'
            elif route['main_road_percentage'] >= 70:
                category = 'main_roads'
                emoji = '🛣️'
                description = 'Uses main roads'
            else:
                category = 'balanced'
                emoji = '⚖️'
                description = 'Well-balanced option'
            
            route['category'] = category
            route['emoji'] = emoji
            route['description'] = description
            
            route['distance_display'] = f"{route['distance_km']:.2f} km"
            route['duration_display'] = f"{int(route['duration_min'])} min"
            route['safety_display'] = f"{route['safety_score']:.0f}/100"
            
            reasons = []
            
            if route.get('crime_density', 5) <= 1:
                reasons.append("Very low crime area")
            elif route.get('crime_density', 5) <= 2:
                reasons.append("Low crime density")
            elif route.get('crime_density', 5) > 4:
                reasons.append(f"⚠️ Crime density: {route['crime_density']:.1f}")
            
            if route.get('max_crime_exposure', 0) <= 2:
                reasons.append("No crime hotspots")
            elif route.get('max_crime_exposure', 0) <= 5:
                reasons.append("Minimal crime exposure")
            else:
                reasons.append(f"⚠️ Max crime exposure: {route['max_crime_exposure']:.0f}")
            
            if route.get('main_road_percentage', 0) > 70:
                reasons.append(f"{route['main_road_percentage']:.0f}% main roads")
            if route.get('lighting_score', 0) > 7.5:
                reasons.append("Well-lit area")
            if route.get('population_score', 0) > 6:
                reasons.append("Populated area")
            
            route['reasons'] = reasons
            
            if route.get('max_crime_exposure', 0) > 8 or route.get('crime_density', 0) > 5:
                route['warning'] = "⚠️ High crime exposure"
            elif route.get('max_crime_exposure', 0) > 5 or route.get('crime_density', 0) > 3:
                route['warning'] = "⚠️ Moderate crime exposure"
            else:
                route['warning'] = None
            
            route.pop('waypoint', None)
            route.pop('composite_score', None)
        
        print("\n" + "="*60)
        print(f"✅ Optimization complete: {len(final_routes)} routes")
        print(f"Top route: Safety={final_routes[0]['safety_score']:.1f}, Distance={final_routes[0]['distance_km']:.2f}km, Crime={final_routes[0]['crime_density']:.1f}")
        print("="*60 + "\n")
        
        return jsonify({
            'success': True,
            'routes': final_routes,
            'total_analyzed': len(all_routes),
            'message': f'Found {len(final_routes)} optimized routes'
        })
        
    except Exception as e:
        print(f"\n❌ Error in route optimization: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/search-place', methods=['GET'])
def search_place():
    q = request.args.get('q')
    if not q:
        return jsonify({'success': False, 'error': 'No query provided'}), 400

    try:
        url = 'https://nominatim.openstreetmap.org/search'
        params = {
            'q': q + ', Bangalore, India',
            'format': 'jsonv2',
            'addressdetails': 1,
            'limit': 6,
            'accept-language': 'en'
        }
        headers = {'User-Agent': 'safe-routes-app/1.0'}
        resp = requests.get(url, params=params, headers=headers, timeout=5)
        data = resp.json()

        results = []
        for item in data:
            try:
                lat = float(item.get('lat', 0))
                lon = float(item.get('lon', 0))
                if validate_coordinates(lat, lon):
                    results.append({
                        'display_name': item.get('display_name'),
                        'lat': lat,
                        'lon': lon,
                        'type': item.get('type')
                    })
            except:
                continue

        return jsonify({'success': True, 'results': results})
    except Exception as e:
        print(f"❌ Search error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/reverse-geocode', methods=['GET'])
def reverse_geocode():
    try:
        lat = request.args.get('lat')
        lon = request.args.get('lon')
        
        if not lat or not lon or not validate_coordinates(lat, lon):
            return jsonify({'success': False, 'error': 'Invalid coordinates'}), 400

        url = 'https://nominatim.openstreetmap.org/reverse'
        params = {
            'lat': lat,
            'lon': lon,
            'format': 'jsonv2',
            'accept-language': 'en'
        }
        headers = {'User-Agent': 'safe-routes-app/1.0'}
        resp = requests.get(url, params=params, headers=headers, timeout=5)
        data = resp.json()
        
        return jsonify({
            'success': True,
            'address': data.get('display_name')
        })
    except Exception as e:
        print(f"❌ Reverse geocoding error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/crime-heatmap', methods=['GET'])
def get_crime_heatmap():
    heatmap_data = crime_data[['Latitude', 'Longitude']].values.tolist()
    return jsonify({
        'success': True,
        'data': heatmap_data,
        'total_crimes': len(crime_data)
    })

@app.route('/api/lighting-heatmap', methods=['GET'])
def get_lighting_heatmap():
    try:
        if 'lighting_score' in lighting_data.columns:
            points = lighting_data[['Latitude', 'Longitude', 'lighting_score']].values.tolist()
        else:
            points = lighting_data[['Latitude', 'Longitude']].assign(lighting_score=5.0).values.tolist()
        return jsonify({
            'success': True,
            'data': points,
            'total_locations': len(points)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/population-heatmap', methods=['GET'])
def get_population_heatmap():
    try:
        if 'population_density' in population_data.columns:
            points = population_data[['Latitude', 'Longitude', 'population_density']].values.tolist()
        else:
            points = population_data[['Latitude', 'Longitude']].assign(population_density=1.0).values.tolist()
        return jsonify({
            'success': True,
            'data': points,
            'total_locations': len(points)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/user-feedback-heatmap', methods=['GET'])
def get_user_feedback_heatmap():
    """Return heatmap data from user_feedback.csv"""
    try:
        feedback_file = os.path.join(base_dir, 'app', 'data', 'user_feedback.csv')
        if not os.path.exists(feedback_file):
            return jsonify({
                'success': True,
                'data': [],
                'total_reports': 0
            })
        
        feedback_df = pd.read_csv(feedback_file)
        
        if len(feedback_df) == 0:
            return jsonify({
                'success': True,
                'data': [],
                'total_reports': 0
            })
        
        # Format: [lat, lon, intensity]
        points = feedback_df[['latitude', 'longitude']].copy()
        points['intensity'] = 1.0  # Each report has equal weight
        
        heatmap_data = points.values.tolist()
        
        return jsonify({
            'success': True,
            'data': heatmap_data,
            'total_reports': len(feedback_df)
        })
    except Exception as e:
        print(f"Error loading user feedback heatmap: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/ml-model-info', methods=['GET'])
def get_ml_model_info():
    """Return ML model status and information"""
    try:
        if not ML_AVAILABLE:
            return jsonify({
                'success': True,
                'ml_enabled': False,
                'message': 'ML model is not available. Using rule-based scoring only.'
            })
        
        # Check if model file exists
        model_path = Path(os.path.join(base_dir, 'app', 'ml', 'models', 'safety_model.pkl'))
        
        # Try to get model info safely
        try:
            from app.ml.inference import _model_data, _model
            has_model_data = True
        except:
            has_model_data = False
        
        info = {
            'success': True,
            'ml_enabled': True,
            'model_exists': model_path.exists(),
            'model_path': str(model_path),
            'model_size_kb': round(model_path.stat().st_size / 1024, 2) if model_path.exists() else 0,
            'scoring_weight': '75% rule-based + 25% ML',
        }
        
        if has_model_data:
            info['feature_names'] = _model_data.get('feature_names', [])
            info['num_features'] = len(_model_data.get('feature_names', []))
            info['model_type'] = str(type(_model).__name__)
            info['training_samples'] = _model_data.get('num_samples', 'Unknown')
            info['model_accuracy'] = _model_data.get('accuracy', 'Unknown')
        
        # Check training data
        training_data_path = Path(os.path.join(base_dir, 'app', 'ml', 'data', 'training_data.csv'))
        if training_data_path.exists():
            training_df = pd.read_csv(training_data_path)
            info['training_data_samples'] = len(training_df)
        else:
            info['training_data_samples'] = 0
        
        # Check route logs
        route_logs_path = Path(os.path.join(base_dir, 'app', 'ml', 'data', 'route_logs'))
        if route_logs_path.exists():
            log_files = list(route_logs_path.glob('*.csv'))
            info['route_logs_count'] = len(log_files)
        else:
            info['route_logs_count'] = 0
        
        return jsonify(info)
    except Exception as e:
        print(f"Error in ml-model-info: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'ml_enabled': ML_AVAILABLE
        }), 500

@app.route('/api/health', methods=['GET'])

def health_check():
    return jsonify({
        'success': True,
        'message': 'Backend is running',
        'crimes_loaded': len(crime_data),
        'lighting_points': len(lighting_data),
        'population_points': len(population_data)
    })

@app.route('/api/rate-route', methods=['POST'])
def rate_route():
    try:
        data = request.json or {}
        rating = data.get('rating')
        feedback_text = data.get('feedback', '')
        route_id = data.get('route_id', '')
        route_data = data.get('route_data', {})
        
        if rating is None:
            return jsonify({'success': False, 'error': 'Rating required'}), 400
        
        feedback_entry = {
            'timestamp': datetime.now().isoformat(),
            'route_id': route_id,
            'rating': rating,
            'feedback': feedback_text,
            'distance_km': route_data.get('distance_km', 0),
            'duration_min': route_data.get('duration_min', 0),
            'safety_score': route_data.get('safety_score', 0),
            'crime_density': route_data.get('crime_density', 0),
            'lighting_score': route_data.get('lighting_score', 0)
        }
        
        feedback_file = Path(os.path.join(base_dir, 'logs', 'feedback.csv'))
        feedback_file.parent.mkdir(parents=True, exist_ok=True)
        
        df_feedback = pd.DataFrame([feedback_entry])
        
        if feedback_file.exists():
            df_feedback.to_csv(feedback_file, mode='a', header=False, index=False)
        else:
            df_feedback.to_csv(feedback_file, mode='w', header=True, index=False)
        
        if rating >= 4 and route_data:
            try:
                safety_metrics = {
                    'crime_density': route_data.get('crime_density', 0),
                    'max_crime_exposure': route_data.get('max_crime_exposure', 0),
                    'lighting_score': route_data.get('lighting_score', 0),
                    'population_score': route_data.get('population_score', 0),
                    'traffic_score': route_data.get('traffic_score', 0),
                    'crime_hotspot_percentage': route_data.get('crime_hotspot_percentage', 0)
                }
                
                features = extract_route_features(route_data, safety_metrics, datetime.now())
                label = route_data.get('safety_score', 0) * (rating / 5.0)
                log_route_sample(features, label)
            except Exception:
                pass
        
        return jsonify({'success': True, 'message': 'Rating recorded'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/submit-unsafe-segments', methods=['POST'])
def submit_unsafe_segments():
    try:
        data = request.json
        route_id = data.get('route_id')
        rating = data.get('rating')
        unsafe_segments = data.get('unsafe_segments', [])
        route_data = data.get('route_data', {})
        
        print(f"\n📝 Received unsafe segment feedback:")
        print(f"  Route ID: {route_id}")
        print(f"  Rating: {rating} stars")
        print(f"  Unsafe segments: {len(unsafe_segments)}")
        
        # Save to CSV
        import csv
        import uuid
        
        user_session = str(uuid.uuid4())[:8]
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        feedback_file = os.path.join(base_dir, 'app', 'data', 'user_feedback.csv')
        
        # Create file with headers if it doesn't exist
        if not os.path.exists(feedback_file):
            with open(feedback_file, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['timestamp', 'latitude', 'longitude', 'route_id', 'rating', 'feedback_type', 'session_id'])
        
        with open(feedback_file, 'a', newline='') as csvfile:
            writer = csv.writer(csvfile)
            for segment in unsafe_segments:
                writer.writerow([
                    timestamp,
                    segment['lat'],
                    segment['lon'],
                    route_id,
                    rating,
                    'unsafe_segment',
                    user_session
                ])
        
        print(f"  ✅ Saved {len(unsafe_segments)} feedback points to user_feedback.csv")
        
        # Check if we should retrain the model
        feedback_count = sum(1 for line in open(feedback_file)) - 1  # excluding header
        print(f"  Total feedback entries: {feedback_count}")
        
        if feedback_count >= 50 and feedback_count % 50 == 0:
            print(f"  🤖 Triggering ML model retraining...")
            try:
                import subprocess
                subprocess.Popen(['python', os.path.join(base_dir, 'app', 'ml', 'train.py')], cwd=base_dir)
                print(f"  ✅ Model retraining started in background")
            except Exception as e:
                print(f"  ⚠️ Could not start retraining: {e}")
        
        return jsonify({
            'success': True,
            'message': f'Recorded {len(unsafe_segments)} unsafe segments',
            'feedback_count': feedback_count
        })
    except Exception as e:
        print(f"❌ Error saving feedback: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Note: Main routes (/, /login, /signup, /safe-routes, etc.) are handled by the blueprint

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 Women's Safety App - FULL APPLICATION (HTTPS)")
    print("="*60)
    print(f"📊 Crime data: {len(crime_data)} records")
    print(f"💡 Lighting data: {len(lighting_data)} points")
    print(f"👥 Population data: {len(population_data)} points")
    print("\nFeatures Available:")
    print("✅ User Authentication (Login/Signup)")
    print("✅ Incident Reporting")
    print("✅ Safe Routes with crime analysis")
    print("✅ Community Support")
    print("✅ SOS Center")
    print("✅ Emergency Contacts")
    print("✅ Fake Call Feature")
    print("="*60)
    print("🔒 Running on HTTPS with self-signed certificate")
    print("⚠️  Accept the security warning in your browser")
    print("="*60 + "\n")
    
    # Use HTTPS with self-signed certificate
    import os
    cert_file = os.path.join(os.path.dirname(__file__), 'cert.pem')
    key_file = os.path.join(os.path.dirname(__file__), 'key.pem')
    
    if os.path.exists(cert_file) and os.path.exists(key_file):
        app.run(debug=True, host='0.0.0.0', port=5443, ssl_context=(cert_file, key_file))
    else:
        print("⚠️  SSL certificates not found! Run: python generate_cert.py")
        print("    Falling back to HTTP on port 5000...")
        app.run(debug=True, host='0.0.0.0', port=5000)