/**
 * Real GPS Navigation Enhancement
 * Adds real-time GPS tracking and voice guidance to the web app
 * 
 * USAGE: Add this script after the existing navigation code in index.html
 * <script src="navigation-gps.js"></script>
 */

// Global state for GPS navigation
let gpsWatchId = null;
let isGPSMode = false;
let voiceEnabled = true;
let lastVoiceInstruction = '';

// Initialize Web Speech API for voice guidance
const speechSynth = window.speechSynthesis || null;

/**
 * Speak a navigation instruction
 */
function speakInstruction(text) {
    if (!voiceEnabled || !speechSynth || !text) return;

    // Cancel any ongoing speech
    speechSynth.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'en-US';
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    utterance.volume = 1.0;

    speechSynth.speak(utterance);
    console.log('🔊 Speaking:', text);
}

/**
 * Toggle GPS mode navigation
 */
function enableGPSMode(route) {
    if (!navigator.geolocation) {
        showStatus('❌ GPS not supported on this device', 'error');
        return false;
    }

    isGPSMode = true;
    const routePoints = route.route;
    const steps = route.steps || [];

    showStatus('🛰️ GPS Navigation Starting...', 'info');
    speakInstruction('Starting GPS navigation. Calculating your position.');

    // Watch user's real-time position
    gpsWatchId = navigator.geolocation.watchPosition(
        (position) => {
            if (!isNavigating) {
                disableGPSMode();
                return;
            }

            const userLat = position.coords.latitude;
            const userLon = position.coords.longitude;
            const accuracy = position.coords.accuracy;

            console.log(`📍 GPS Update: ${userLat.toFixed(6)}, ${userLon.toFixed(6)} (±${accuracy.toFixed(0)}m)`);

            // Update car marker with real position
            if (carMarker) {
                carMarker.setLatLng([userLat, userLon]);
                map.panTo([userLat, userLon], { animate: true, duration: 0.5 });
            }

            // Find closest point on route
            let nearestIdx = 0;
            let minDist = Infinity;

            routePoints.forEach((point, idx) => {
                const dist = haversine_distance_js(userLat, userLon, point[0], point[1]) * 1000; // to meters
                if (dist < minDist) {
                    minDist = dist;
                    nearestIdx = idx;
                }
            });

            // Update progress
            const progress = nearestIdx / routePoints.length;

            // Calculate which step we're on
            updateCurrentStep(route, progress);

            // Rotate car icon to face direction of travel
            if (nearestIdx < routePoints.length - 1) {
                const nextPoint = routePoints[nearestIdx + 1];
                const bearing = calculateBearing(userLat, userLon, nextPoint[0], nextPoint[1]);

                const carEl = carMarker.getElement();
                if (carEl) {
                    const carDiv = carEl.querySelector('div');
                    if (carDiv) {
                        carDiv.style.transform = `rotate(${bearing}deg)`;
                    }
                }
            }

            // Check if arrived at destination
            const destPoint = routePoints[routePoints.length - 1];
            const distToDestination = haversine_distance_js(userLat, userLon, destPoint[0], destPoint[1]) * 1000;

            if (distToDestination < 30) { // Within 30 meters
                showStatus('🎉 You have arrived!', 'success');
                speakInstruction('You have arrived at your destination');
                stopNavigation();
            }
        },
        (error) => {
            console.error('GPS Error:', error);

            let errorMsg = 'GPS error';
            switch (error.code) {
                case error.PERMISSION_DENIED:
                    errorMsg = 'GPS permission denied. Please enable location access.';
                    break;
                case error.POSITION_UNAVAILABLE:
                    errorMsg = 'GPS position unavailable. Check your device settings.';
                    break;
                case error.TIMEOUT:
                    errorMsg = 'GPS request timed out. Retrying...';
                    break;
            }

            showStatus(`⚠️ ${errorMsg}`, 'warning');
        },
        {
            enableHighAccuracy: true,
            maximumAge: 0,
            timeout: 5000
        }
    );

    return true;
}

/**
 * Disable GPS mode and stop tracking
 */
function disableGPSMode() {
    if (gpsWatchId) {
        navigator.geolocation.clearWatch(gpsWatchId);
        gpsWatchId = null;
    }

    isGPSMode = false;

    if (speechSynth) {
        speechSynth.cancel();
    }
}

/**
 * Update the current navigation step based on progress
 */
function updateCurrentStep(route, progress) {
    const steps = route.steps || [];
    if (!steps.length) return;

    // Calculate which step we're on
    let cumulativeDist = 0;
    const totalDist = route.distance_km;

    for (let i = 0; i < steps.length; i++) {
        const stepDist = (steps[i].distance || 0) / 1000; // Convert to km
        cumulativeDist += stepDist;

        const stepProgress = cumulativeDist / totalDist;

        if (progress <= stepProgress) {
            // This is the current step
            if (i !== currentStepIndex) {
                currentStepIndex = i;

                // Update UI
                document.querySelectorAll('.direction-step').forEach((el, idx) => {
                    el.classList.toggle('current-step', idx === i);
                });

                // Get instruction
                const instruction = steps[i].instruction ||
                    steps[i].maneuver?.instruction ||
                    'Continue straight';

                // Get distance to next maneuver
                const distanceToStep = (stepProgress - progress) * route.distance_km * 1000; // meters
                const distanceText = distanceToStep > 1000
                    ? `in ${(distanceToStep / 1000).toFixed(1)} km`
                    : `in ${Math.round(distanceToStep)} meters`;

                // Speak new instruction
                if (instruction !== lastVoiceInstruction) {
                    const fullInstruction = `${instruction} ${distanceText}`;
                    speakInstruction(fullInstruction);
                    lastVoiceInstruction = instruction;
                    showStatus(`🧭 ${instruction}`, 'info');
                }

                // Scroll to current step
                const stepEl = document.querySelectorAll('.direction-step')[i];
                if (stepEl) {
                    stepEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                }
            }
            break;
        }
    }
}

/**
 * Override the original stopNavigation to include GPS cleanup
 */
const originalStopNavigation = window.stopNavigation;
window.stopNavigation = function () {
    disableGPSMode();
    if (originalStopNavigation) {
        originalStopNavigation();
    }
};

/**
 * Add GPS mode toggle button to the navigation UI
 */
function addGPSModeToggle() {
    // Find the directions panel
    const directionsPanel = document.getElementById('directionsPanel');
    if (!directionsPanel) return;

    // Create GPS toggle button
    const toggleBtn = document.createElement('button');
    toggleBtn.id = 'gpsToggle';
    toggleBtn.className = 'btn-primary';
    toggleBtn.style.cssText = 'margin: 10px; width: calc(100% - 20px);';
    toggleBtn.innerHTML = isGPSMode
        ? '🛰️ Real GPS: ON'
        : '🎮 Simulation Mode';

    toggleBtn.onclick = function () {
        if (isNavigating && currentRoutes[selectedRouteIndex]) {
            const route = currentRoutes[selectedRouteIndex];

            if (!isGPSMode) {
                if (enableGPSMode(route)) {
                    toggleBtn.innerHTML = '🛰️ Real GPS: ON';
                    toggleBtn.style.background = '#10b981';
                }
            } else {
                disableGPSMode();
                toggleBtn.innerHTML = '🎮 Simulation Mode';
                toggleBtn.style.background = '';
            }
        }
    };

    // Add voice toggle button
    const voiceBtn = document.createElement('button');
    voiceBtn.id = 'voiceToggle';
    voiceBtn.className = 'btn-secondary';
    voiceBtn.style.cssText = 'margin: 10px; width: calc(100% - 20px);';
    voiceBtn.innerHTML = voiceEnabled ? '🔊 Voice: ON' : '🔇 Voice: OFF';

    voiceBtn.onclick = function () {
        voiceEnabled = !voiceEnabled;
        voiceBtn.innerHTML = voiceEnabled ? '🔊 Voice: ON' : '🔇 Voice: OFF';

        if (!voiceEnabled && speechSynth) {
            speechSynth.cancel();
        }
    };

    // Insert buttons at the top of directions list
    const directionsList = document.getElementById('directionsList');
    if (directionsList && !document.getElementById('gpsToggle')) {
        directionsPanel.insertBefore(voiceBtn, directionsList);
        directionsPanel.insertBefore(toggleBtn, directionsList);
    }
}

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', addGPSModeToggle);
} else {
    // DOM already loaded
    setTimeout(addGPSModeToggle, 1000);
}

console.log('✅ GPS Navigation module loaded');
