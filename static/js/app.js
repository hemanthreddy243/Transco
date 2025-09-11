// Smart Transportation System JavaScript

// Utility functions
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `alert alert-${type}`;
    notification.innerHTML = `<i class="fas fa-info-circle"></i> ${message}`;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 1000;
        animation: slideIn 0.3s ease;
    `;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Emergency button functionality
function handleEmergencyRequest() {
    const emergencyBtn = document.getElementById('emergency-btn');
    if (!emergencyBtn) return;
    
    emergencyBtn.addEventListener('click', function() {
        if (confirm('Are you sure you want to request emergency bus service?')) {
            requestEmergency();
        }
    });
}

// Real-time updates
class RealTimeUpdater {
    constructor() {
        this.updateInterval = null;
        this.isActive = false;
    }
    
    start() {
        if (this.isActive) return;
        this.isActive = true;
        this.updateInterval = setInterval(() => {
            this.updateBusLocations();
            this.updateEmergencyStatus();
        }, 30000); // Update every 30 seconds
    }
    
    stop() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.isActive = false;
        }
    }
    
    updateBusLocations() {
        // Fetch current bus locations
        fetch('/api/bus-locations')
            .then(response => response.json())
            .then(data => {
                updateBusMarkers(data.buses);
            })
            .catch(error => console.error('Error updating bus locations:', error));
    }
    
    updateEmergencyStatus() {
        // Check if emergency window is active
        fetch('/api/emergency-status')
            .then(response => response.json())
            .then(data => {
                updateEmergencyUI(data.is_active);
            })
            .catch(error => console.error('Error updating emergency status:', error));
    }
}

// GPS and mapping functionality
class GPSTracker {
    constructor() {
        this.watchId = null;
        this.currentLocation = null;
    }
    
    getCurrentLocation() {
        return new Promise((resolve, reject) => {
            if (!navigator.geolocation) {
                reject('Geolocation is not supported by this browser.');
                return;
            }
            
            navigator.geolocation.getCurrentPosition(
                (position) => {
                    this.currentLocation = {
                        latitude: position.coords.latitude,
                        longitude: position.coords.longitude
                    };
                    resolve(this.currentLocation);
                },
                (error) => {
                    reject(error.message);
                },
                { enableHighAccuracy: true, timeout: 5000, maximumAge: 0 }
            );
        });
    }
    
    startTracking() {
        if (!navigator.geolocation) {
            console.error('Geolocation is not supported');
            return;
        }
        
        this.watchId = navigator.geolocation.watchPosition(
            (position) => {
                this.currentLocation = {
                    latitude: position.coords.latitude,
                    longitude: position.coords.longitude
                };
                this.updateLocationDisplay();
            },
            (error) => {
                console.error('Error getting location:', error);
            },
            { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
        );
    }
    
    stopTracking() {
        if (this.watchId !== null) {
            navigator.geolocation.clearWatch(this.watchId);
            this.watchId = null;
        }
    }
    
    updateLocationDisplay() {
        const locationDisplay = document.getElementById('current-location');
        if (locationDisplay && this.currentLocation) {
            locationDisplay.textContent = 
                `Lat: ${this.currentLocation.latitude.toFixed(4)}, Lng: ${this.currentLocation.longitude.toFixed(4)}`;
        }
    }
}

// Voting functionality
class VotingSystem {
    constructor() {
        this.hasVotedToday = false;
    }
    
    async submitVote(needsBus) {
        try {
            const formData = new FormData();
            formData.append('needs_bus', needsBus ? 'yes' : 'no');
            
            const response = await fetch('/vote', {
                method: 'POST',
                body: formData
            });
            
            if (response.ok) {
                showNotification('Vote submitted successfully!', 'success');
                setTimeout(() => location.reload(), 1500);
            } else {
                throw new Error('Failed to submit vote');
            }
        } catch (error) {
            console.error('Error submitting vote:', error);
            showNotification('Error submitting vote. Please try again.', 'danger');
        }
    }
}

// Emergency system
class EmergencySystem {
    constructor() {
        this.isEmergencyActive = false;
        this.checkEmergencyStatus();
    }
    
    async checkEmergencyStatus() {
        try {
            const response = await fetch('/api/emergency-status');
            const data = await response.json();
            this.isEmergencyActive = data.is_active;
            this.updateEmergencyUI();
        } catch (error) {
            console.error('Error checking emergency status:', error);
        }
    }
    
    updateEmergencyUI() {
        const emergencySection = document.querySelector('.emergency-section');
        const emergencyBtn = document.getElementById('emergency-btn');
        
        if (emergencySection) {
            if (this.isEmergencyActive) {
                emergencySection.classList.add('emergency-active');
                if (emergencyBtn) emergencyBtn.disabled = false;
            } else {
                emergencySection.classList.remove('emergency-active');
                if (emergencyBtn) emergencyBtn.disabled = true;
            }
        }
    }
    
    async requestEmergency() {
        try {
            const response = await fetch('/emergency', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            const data = await response.json();
            
            if (response.ok) {
                showNotification(data.message, 'success');
                
                // Update UI with response
                const responseDiv = document.getElementById('emergency-response');
                if (responseDiv) {
                    responseDiv.innerHTML = `
                        <div class="alert alert-success">
                            <i class="fas fa-check-circle"></i> ${data.message}<br>
                            <strong>Nearby buses:</strong> ${data.nearby_buses}<br>
                            <strong>Estimated wait:</strong> ${data.estimated_wait}
                        </div>
                    `;
                }
            } else {
                throw new Error(data.error || 'Failed to request emergency service');
            }
        } catch (error) {
            console.error('Error requesting emergency:', error);
            showNotification(error.message, 'danger');
        }
    }
}

// Route optimization
class RouteOptimizer {
    async optimizeRoutes() {
        try {
            const response = await fetch('/api/optimize-routes', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            const data = await response.json();
            
            if (response.ok) {
                showNotification(`Routes optimized! ${data.routes} routes created, serving ${data.total_students_served} students.`, 'success');
                return data;
            } else {
                throw new Error('Failed to optimize routes');
            }
        } catch (error) {
            console.error('Error optimizing routes:', error);
            showNotification('Error optimizing routes', 'danger');
        }
    }
}

// Utility functions for distance calculation
function calculateDistance(lat1, lon1, lat2, lon2) {
    const R = 6371; // Earth's radius in km
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
              Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
              Math.sin(dLon/2) * Math.sin(dLon/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    return R * c;
}

// Form validation
function validateRegistrationForm() {
    const form = document.getElementById('registration-form');
    if (!form) return;
    
    form.addEventListener('submit', function(e) {
        const studentId = document.getElementById('student_id').value;
        const name = document.getElementById('name').value;
        const password = document.getElementById('password').value;
        const stopId = document.getElementById('stop_id').value;
        
        if (!studentId || !name || !password || !stopId) {
            e.preventDefault();
            showNotification('Please fill in all required fields', 'danger');
            return;
        }
        
        if (studentId.length < 3) {
            e.preventDefault();
            showNotification('Student ID must be at least 3 characters', 'danger');
            return;
        }
        
        if (password.length < 6) {
            e.preventDefault();
            showNotification('Password must be at least 6 characters', 'danger');
            return;
        }
    });
}

// Real-time clock
function updateClock() {
    const clockElements = document.querySelectorAll('.current-time');
    const now = new Date();
    const timeString = now.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: true
    });
    
    clockElements.forEach(element => {
        element.textContent = timeString;
    });
}

// Initialize application
document.addEventListener('DOMContentLoaded', function() {
    // Initialize components
    const gpsTracker = new GPSTracker();
    const votingSystem = new VotingSystem();
    const emergencySystem = new EmergencySystem();
    const routeOptimizer = new RouteOptimizer();
    const realTimeUpdater = new RealTimeUpdater();
    
    // Initialize form validation
    validateRegistrationForm();
    
    // Start real-time updates if on dashboard
    if (window.location.pathname.includes('/dashboard')) {
        realTimeUpdater.start();
        
        // Update clock every second
        setInterval(updateClock, 1000);
        updateClock();
    }
    
    // Add event listeners for voting buttons
    const voteButtons = document.querySelectorAll('.vote-btn');
    voteButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const needsBus = this.value === 'yes';
            votingSystem.submitVote(needsBus);
        });
    });
    
    // Add event listener for emergency button
    const emergencyBtn = document.getElementById('emergency-btn');
    if (emergencyBtn) {
        emergencyBtn.addEventListener('click', function() {
            if (confirm('Are you sure you want to request emergency bus service?')) {
                emergencySystem.requestEmergency();
            }
        });
    }
    
    // Add event listener for route optimization
    const optimizeBtn = document.getElementById('optimize-routes-btn');
    if (optimizeBtn) {
        optimizeBtn.addEventListener('click', function() {
            routeOptimizer.optimizeRoutes();
        });
    }
    
    // Add loading states for buttons
    const buttons = document.querySelectorAll('.btn');
    buttons.forEach(button => {
        button.addEventListener('click', function() {
            if (!this.disabled && this.type !== 'submit') {
                const originalText = this.innerHTML;
                this.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Loading...';
                this.disabled = true;
                
                setTimeout(() => {
                    this.innerHTML = originalText;
                    this.disabled = false;
                }, 2000);
            }
        });
    });
});

// CSS animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    
    @keyframes slideOut {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }
    
    .fade-in {
        animation: fadeIn 0.5s ease;
    }
    
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }
`;
document.head.appendChild(style);
