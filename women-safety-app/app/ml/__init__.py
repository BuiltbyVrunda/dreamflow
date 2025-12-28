"""
ML Module for Safe Routes
Provides machine learning-based safety scoring and predictions
"""

from .feature_extraction import extract_route_features
from .inference import predict_safety_score

__all__ = ['extract_route_features', 'predict_safety_score']
