#!/bin/bash
# Feature Verification Test Script
# Tests all migrated features from bangalore-safe-routes

echo "🧪 Testing Feature Migration..."
echo "================================"
echo ""

cd /Users/chiranth/Documents/dreamflow/women-safety-app

# 1. Check Python syntax
echo "1️⃣  Checking Python syntax..."
python3 -m py_compile app.py 2>&1
if [ $? -eq 0 ]; then
    echo "   ✅ app.py syntax valid"
else
    echo "   ❌ Syntax errors found"
    exit 1
fi
echo ""

# 2. Verify new functions exist
echo "2️⃣  Verifying route validation functions..."
grep -q "def validate_route_connectivity" app.py && echo "   ✅ validate_route_connectivity() found" || echo "   ❌ Missing"
grep -q "def check_route_main_road_coverage" app.py && echo "   ✅ check_route_main_road_coverage() found" || echo "   ❌ Missing"
grep -q "def detect_route_backtracking" app.py && echo "   ✅ detect_route_backtracking() found" || echo "   ❌ Missing"
echo ""

# 3. Verify ML integration
echo "3️⃣  Verifying ML integration..."
grep -q "if ML_AVAILABLE:" app.py && echo "   ✅ ML_AVAILABLE check found" || echo "   ❌ Missing"
grep -q "ml_predict(features)" app.py && echo "   ✅ ml_predict() call found" || echo "   ❌ Missing"
grep -q "ml_predictions_made" app.py && echo "   ✅ ML prediction tracking found" || echo "   ❌ Missing"
grep -q "log_route_sample" app.py && echo "   ✅ Route sample logging found" || echo "   ❌ Missing"
echo ""

# 4. Verify safety guardrails
echo "4️⃣  Verifying safety guardrails integration..."
grep -q "apply_safety_guardrails" app.py && echo "   ✅ apply_safety_guardrails() call found" || echo "   ❌ Missing"
grep -q "Phase 4: Safety Guardrails" app.py && echo "   ✅ Phase 4 logging found" || echo "   ❌ Missing"
grep -q "validated_routes" app.py && echo "   ✅ Route validation loop found" || echo "   ❌ Missing"
echo ""

# 5. Verify new API endpoints
echo "5️⃣  Verifying new API endpoints..."
grep -q "@app.route('/api/user-feedback-heatmap'" app.py && echo "   ✅ /api/user-feedback-heatmap found" || echo "   ❌ Missing"
grep -q "@app.route('/api/ml-model-info'" app.py && echo "   ✅ /api/ml-model-info found" || echo "   ❌ Missing"
grep -q "@app.route('/api/submit-unsafe-segments'" app.py && echo "   ✅ /api/submit-unsafe-segments found" || echo "   ❌ Missing"
echo ""

# 6. Verify enhanced rate-route
echo "6️⃣  Verifying enhanced /api/rate-route..."
grep -q "feedback_entry = {" app.py && echo "   ✅ Detailed feedback logging found" || echo "   ❌ Missing"
grep -q "extract_route_features" app.py && echo "   ✅ Feature extraction for ML found" || echo "   ❌ Missing"
echo ""

# 7. Check validation in route optimization
echo "7️⃣  Verifying validation checks in route optimization..."
grep -q "validate_route_connectivity(route_points" app.py && echo "   ✅ Connectivity check in routing found" || echo "   ❌ Missing"
grep -q "detect_route_backtracking(route_points" app.py && echo "   ✅ Backtracking check in routing found" || echo "   ❌ Missing"
grep -q "check_route_main_road_coverage(route_points" app.py && echo "   ✅ Main road coverage check found" || echo "   ❌ Missing"
echo ""

# 8. Verify enhanced composite scoring
echo "8️⃣  Verifying enhanced composite scoring..."
grep -q "preference_bonus += (main_road_pct / 100) \* 0.35" app.py && echo "   ✅ Enhanced main road bonus found" || echo "   ❌ Missing"
grep -q "if main_road_pct > 70:" app.py && echo "   ✅ Extra main road bonus found" || echo "   ❌ Missing"
echo ""

# 9. Check data files
echo "9️⃣  Checking required data files..."
[ -f "app/data/bangalore_crimes.csv" ] && echo "   ✅ bangalore_crimes.csv exists" || echo "   ⚠️  Missing"
[ -f "app/data/bangalore_lighting.csv" ] && echo "   ✅ bangalore_lighting.csv exists" || echo "   ⚠️  Missing"
[ -f "app/data/bangalore_population.csv" ] && echo "   ✅ bangalore_population.csv exists" || echo "   ⚠️  Missing"
[ -f "app/data/user_feedback.csv" ] && echo "   ✅ user_feedback.csv exists" || echo "   ⚠️  Missing (will be created)"
echo ""

# 10. Check ML files
echo "🔟 Checking ML infrastructure..."
[ -f "app/ml/feature_extraction.py" ] && echo "   ✅ feature_extraction.py exists" || echo "   ❌ Missing"
[ -f "app/ml/inference.py" ] && echo "   ✅ inference.py exists" || echo "   ❌ Missing"
[ -f "app/ml/collect_data.py" ] && echo "   ✅ collect_data.py exists" || echo "   ❌ Missing"
[ -f "app/ml/train.py" ] && echo "   ✅ train.py exists" || echo "   ❌ Missing"
echo ""

# 11. Check safety guardrails
echo "1️⃣1️⃣  Checking safety guardrails..."
[ -f "app/safety/guardrails.py" ] && echo "   ✅ guardrails.py exists" || echo "   ❌ Missing"
echo ""

# 12. Frontend verification
echo "1️⃣2️⃣  Verifying frontend features..."
grep -q "function startNavigation" app/templates/safe_routes.html && echo "   ✅ Navigation features present" || echo "   ⚠️  Check frontend"
grep -q "animateCarMovement" app/templates/safe_routes.html && echo "   ✅ Car animation present" || echo "   ⚠️  Check frontend"
echo ""

# Summary
echo "================================"
echo "✅ FEATURE MIGRATION VERIFICATION COMPLETE"
echo ""
echo "📝 Next Steps:"
echo "   1. Start the app: python app.py"
echo "   2. Test route optimization at /safe-routes"
echo "   3. Check console for ML status messages"
echo "   4. Test new API endpoints"
echo "   5. Verify user feedback collection"
echo ""
echo "📚 See FEATURE_MIGRATION_COMPLETE.md for detailed documentation"
echo ""
