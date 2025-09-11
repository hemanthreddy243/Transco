from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
from geopy.distance import geodesic
import heapq
import math
import csv
import io



app = Flask(__name__)
app.config['SECRET_KEY'] = 'smart-transport-hackfinity-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///smart_transport.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Database Models
class Student(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    stop_id = db.Column(db.Integer, db.ForeignKey('bus_stop.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    stop = db.relationship('BusStop', backref='students')
    votes = db.relationship('DailyVote', backref='student', lazy=True)
    emergency_requests = db.relationship('EmergencyRequest', backref='student', lazy=True)

class BusStop(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    address = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Bus(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bus_number = db.Column(db.String(20), unique=True, nullable=False)
    capacity = db.Column(db.Integer, nullable=False, default=50)
    current_latitude = db.Column(db.Float)
    current_longitude = db.Column(db.Float)
    is_active = db.Column(db.Boolean, default=True)
    driver_name = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class DailyVote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    vote_date = db.Column(db.Date, nullable=False)
    needs_bus = db.Column(db.Boolean, nullable=False)
    voted_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('student_id', 'vote_date', name='unique_daily_vote'),)

class EmergencyRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    stop_id = db.Column(db.Integer, db.ForeignKey('bus_stop.id'), nullable=False)
    request_time = db.Column(db.DateTime, default=datetime.utcnow)
    is_resolved = db.Column(db.Boolean, default=False)
    assigned_bus_id = db.Column(db.Integer, db.ForeignKey('bus.id'))
    
    stop = db.relationship('BusStop')
    assigned_bus = db.relationship('Bus')

class RouteAssignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bus_id = db.Column(db.Integer, db.ForeignKey('bus.id'), nullable=False)
    stop_id = db.Column(db.Integer, db.ForeignKey('bus_stop.id'), nullable=False)
    route_date = db.Column(db.Date, nullable=False)
    stop_order = db.Column(db.Integer, nullable=False)
    estimated_time = db.Column(db.Time)
    
    bus = db.relationship('Bus')
    stop = db.relationship('BusStop')

class BusSchedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    route_name = db.Column(db.String(100), nullable=False)
    departure_time = db.Column(db.Time, nullable=False)
    arrival_time = db.Column(db.Time, nullable=False)
    bus_number = db.Column(db.String(20), nullable=False)
    driver_name = db.Column(db.String(100), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class BusLocation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bus_id = db.Column(db.Integer, db.ForeignKey('bus.id'), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    speed = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='moving')
    
    bus = db.relationship('Bus')

@login_manager.user_loader
def load_user(user_id):
    return Student.query.get(int(user_id))

# Route optimization using Dijkstra's algorithm
class RouteOptimizer:
    def __init__(self, stops, school_location):
        self.stops = stops
        self.school_location = school_location
        
    def calculate_distance(self, point1, point2):
        """Calculate distance between two GPS coordinates"""
        return geodesic(point1, point2).kilometers
    
    def dijkstra_shortest_path(self, start_stop, target_stops):
        """Find shortest path visiting all target stops"""
        # Create distance matrix
        all_points = [start_stop] + target_stops + [self.school_location]
        n = len(all_points)
        distances = {}
        
        for i in range(n):
            for j in range(n):
                if i != j:
                    point1 = (all_points[i]['latitude'], all_points[i]['longitude'])
                    point2 = (all_points[j]['latitude'], all_points[j]['longitude'])
                    distances[(i, j)] = self.calculate_distance(point1, point2)
        
        # Simple greedy approach for TSP (can be improved with dynamic programming)
        visited = [0]  # Start from first stop
        current = 0
        total_distance = 0
        
        while len(visited) < n - 1:  # Exclude school from intermediate visits
            min_dist = float('inf')
            next_stop = -1
            
            for i in range(1, n - 1):  # Exclude start and school
                if i not in visited:
                    if distances.get((current, i), float('inf')) < min_dist:
                        min_dist = distances[(current, i)]
                        next_stop = i
            
            if next_stop != -1:
                visited.append(next_stop)
                total_distance += min_dist
                current = next_stop
        
        # Add distance to school
        total_distance += distances.get((current, n - 1), 0)
        visited.append(n - 1)
        
        return visited, total_distance

# Utility functions
def is_emergency_window_active():
    """Check if emergency button is active (7:00-7:30 AM)"""
    now = datetime.now()
    start_time = now.replace(hour=7, minute=0, second=0, microsecond=0)
    end_time = now.replace(hour=7, minute=30, second=0, microsecond=0)
    return start_time <= now <= end_time

def find_nearby_buses(stop_location, max_distance_km=5):
    """Find buses within specified distance of a stop"""
    nearby_buses = []
    buses = Bus.query.filter_by(is_active=True).all()
    
    for bus in buses:
        if bus.current_latitude and bus.current_longitude:
            bus_location = (bus.current_latitude, bus.current_longitude)
            distance = geodesic(stop_location, bus_location).kilometers
            
            if distance <= max_distance_km:
                nearby_buses.append({
                    'bus': bus,
                    'distance': distance
                })
    
    return sorted(nearby_buses, key=lambda x: x['distance'])

# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        student_id = request.form['student_id']
        name = request.form['name']
        password = request.form['password']
        stop_id = request.form['stop_id']
        
        # Check if student already exists
        if Student.query.filter_by(student_id=student_id).first():
            flash('Student ID already exists!')
            return redirect(url_for('register'))
        
        # Create new student
        student = Student(
            student_id=student_id,
            name=name,
            password_hash=generate_password_hash(password),
            stop_id=stop_id
        )
        
        db.session.add(student)
        db.session.commit()
        
        flash('Registration successful!')
        return redirect(url_for('login'))
    
    stops = BusStop.query.all()
    return render_template('register.html', stops=stops)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        student_id = request.form['student_id']
        password = request.form['password']
        
        student = Student.query.filter_by(student_id=student_id).first()
        
        if student and check_password_hash(student.password_hash, password):
            login_user(student)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid student ID or password!')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    today = datetime.now().date()
    now = datetime.now()
    
    # Get today's vote
    today_vote = DailyVote.query.filter_by(
        student_id=current_user.id,
        vote_date=today
    ).first()
    
    # Check if emergency window is active (7:00 AM - 7:30 AM)
    emergency_active = False
    current_time = now.time()
    if current_time >= datetime.strptime("07:00", "%H:%M").time() and \
       current_time <= datetime.strptime("07:30", "%H:%M").time():
        emergency_active = True
    
    # Get user's bus stop
    user_stop = BusStop.query.get(current_user.stop_id)
    
    # Get bus schedule for today
    bus_schedule = BusSchedule.query.filter_by(is_active=True).first()
    
    # Get live bus location
    bus_location = BusLocation.query.order_by(BusLocation.timestamp.desc()).first()
    
    return render_template('dashboard.html',
                         current_user=current_user,
                         today_vote=today_vote,
                         emergency_active=emergency_active,
                         user_stop=user_stop,
                         now=now,
                         bus_schedule=bus_schedule,
                         bus_location=bus_location)

@app.route('/vote', methods=['POST'])
@login_required
def vote():
    needs_bus = request.form.get('needs_bus') == 'yes'
    today = datetime.now().date()
    
    # Check if already voted today
    existing_vote = DailyVote.query.filter_by(
        student_id=current_user.id,
        vote_date=today
    ).first()
    
    if existing_vote:
        existing_vote.needs_bus = needs_bus
        existing_vote.voted_at = datetime.utcnow()
    else:
        vote = DailyVote(
            student_id=current_user.id,
            vote_date=today,
            needs_bus=needs_bus
        )
        db.session.add(vote)
    
    db.session.commit()
    flash('Vote recorded successfully!')
    return redirect(url_for('dashboard'))

@app.route('/emergency', methods=['POST'])
@login_required
def emergency_request():
    if not is_emergency_window_active():
        return jsonify({'error': 'Emergency window is not active'}), 400
    
    # Create emergency request
    emergency = EmergencyRequest(
        student_id=current_user.id,
        stop_id=current_user.stop_id
    )
    
    db.session.add(emergency)
    db.session.commit()
    
    # Find nearby buses
    stop_location = (current_user.stop.latitude, current_user.stop.longitude)
    nearby_buses = find_nearby_buses(stop_location)
    
    response_data = {
        'message': 'Emergency request submitted successfully!',
        'nearby_buses': len(nearby_buses),
        'estimated_wait': '5-15 minutes' if nearby_buses else '15-30 minutes'
    }
    
    return jsonify(response_data)

# Admin authentication routes
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Admin credentials (hardcoded for demo)
        if username == 'admin' and password == 'admin123':
            session['admin_logged_in'] = True
            session['admin_username'] = username
            flash('Admin login successful!')
            return redirect(url_for('admin_dashboard_secure'))
        else:
            flash('Invalid admin credentials!')
    
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    """Admin logout"""
    session.pop('admin_logged_in', None)
    session.pop('admin_username', None)
    flash('Admin logged out successfully!')
    return redirect(url_for('admin_login'))

@app.route('/admin/dashboard')
def admin_dashboard_secure():
    """Public admin dashboard - no login required"""
    today = datetime.now().date()
    
    # Get today's votes
    votes = db.session.query(DailyVote, Student, BusStop).join(
        Student, DailyVote.student_id == Student.id
    ).join(
        BusStop, Student.stop_id == BusStop.id
    ).filter(DailyVote.vote_date == today).all()
    
    # Get emergency requests
    emergency_requests = db.session.query(EmergencyRequest, Student, BusStop).join(
        Student, EmergencyRequest.student_id == Student.id
    ).join(
        BusStop, EmergencyRequest.stop_id == BusStop.id
    ).filter(
        EmergencyRequest.request_time >= datetime.now() - timedelta(hours=1)
    ).all()
    
    # Calculate bus requirements by stop
    stop_demands = {}
    for vote, student, stop in votes:
        if vote.needs_bus:
            if stop.id not in stop_demands:
                stop_demands[stop.id] = {
                    'stop': stop,
                    'count': 0,
                    'students': []
                }
            stop_demands[stop.id]['count'] += 1
            stop_demands[stop.id]['students'].append(student)
    
    return render_template('admin_dashboard_secure.html',
                         votes=votes,
                         emergency_requests=emergency_requests,
                         stop_demands=stop_demands)

@app.route('/admin/import/students', methods=['GET', 'POST'])
def import_students():
    """Import students from CSV - admin only"""
    if 'admin_logged_in' not in session:
        flash('Please login as admin to access this page.')
        return redirect(url_for('admin_login'))
    
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected')
            return redirect(request.url)
        
        if file and file.filename.endswith('.csv'):
            try:
                stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
                csv_reader = csv.DictReader(stream)
                
                imported_count = 0
                for row in csv_reader:
                    try:
                        # Check if student already exists
                        existing = Student.query.filter_by(student_id=row['student_id']).first()
                        if existing:
                            continue
                        
                        # Get bus stop ID
                        stop = BusStop.query.filter_by(name=row['stop_name']).first()
                        if not stop:
                            flash(f"Bus stop '{row['stop_name']}' not found")
                            continue
                        
                        # Create student
                        student = Student(
                            student_id=row['student_id'],
                            name=row['name'],
                            password_hash=generate_password_hash(row['password']),
                            stop_id=stop.id
                        )
                        db.session.add(student)
                        imported_count += 1
                    
                    except Exception as e:
                        flash(f'Error importing row: {str(e)}')
                
                db.session.commit()
                flash(f'Successfully imported {imported_count} students!')
                
            except Exception as e:
                flash(f'Error importing file: {str(e)}')
        else:
            flash('Please upload a CSV file')
    
    return render_template('import_students.html')

@app.route('/admin/import/stops', methods=['GET', 'POST'])
def import_stops():
    """Import bus stops from CSV - public access"""
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected')
            return redirect(request.url)
        
        if file and file.filename.endswith('.csv'):
            try:
                stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
                csv_reader = csv.DictReader(stream)
                
                imported_count = 0
                for row in csv_reader:
                    try:
                        existing = BusStop.query.filter_by(name=row['name']).first()
                        if existing:
                            continue
                        
                        stop = BusStop(
                            name=row['name'],
                            latitude=float(row['latitude']),
                            longitude=float(row['longitude']),
                            address=row.get('address', '')
                        )
                        db.session.add(stop)
                        imported_count += 1
                    
                    except Exception as e:
                        flash(f'Error importing row: {str(e)}')
                
                db.session.commit()
                flash(f'Successfully imported {imported_count} bus stops!')
                
            except Exception as e:
                flash(f'Error importing file: {str(e)}')
        else:
            flash('Please upload a CSV file')
    
    return render_template('import_stops.html')

@app.route('/api/bus-schedule')
def get_bus_schedule():
    """Get today's bus schedule"""
    today = datetime.now().date()
    
    # Create sample schedule if none exists
    schedule = BusSchedule.query.filter_by(is_active=True).first()
    if not schedule:
        sample_schedule = BusSchedule(
            route_name="Morning Route",
            departure_time=datetime.strptime("07:30", "%H:%M").time(),
            arrival_time=datetime.strptime("08:15", "%H:%M").time(),
            bus_number="BUS-001",
            driver_name="John Smith"
        )
        db.session.add(sample_schedule)
        db.session.commit()
        schedule = sample_schedule
    
    return jsonify({
        'route_name': schedule.route_name,
        'departure_time': schedule.departure_time.strftime('%I:%M %p'),
        'arrival_time': schedule.arrival_time.strftime('%I:%M %p'),
        'bus_number': schedule.bus_number,
        'driver_name': schedule.driver_name,
        'countdown_minutes': 0
    })

@app.route('/api/live-location')
def get_live_location():
    """Get live bus location"""
    location = BusLocation.query.order_by(BusLocation.timestamp.desc()).first()
    
    if location:
        return jsonify({
            'latitude': location.latitude,
            'longitude': location.longitude,
            'status': location.status,
            'speed': location.speed,
            'timestamp': location.timestamp.strftime('%I:%M %p')
        })
    else:
        # Return school location as default
        return jsonify({
            'latitude': 12.9716,
            'longitude': 77.5946,
            'status': 'at_school',
            'speed': 0.0,
            'timestamp': datetime.now().strftime('%I:%M %p')
        })

@app.route('/api/update-location', methods=['POST'])
def update_location():
    """Update bus location (for demo purposes)"""
    data = request.json
    
    # Create or update bus location
    bus_id = data.get('bus_id', 1)
    location = BusLocation(
        bus_id=bus_id,
        latitude=data.get('latitude', 12.9716),
        longitude=data.get('longitude', 77.5946),
        speed=data.get('speed', 0.0),
        status=data.get('status', 'moving')
    )
    db.session.add(location)
    db.session.commit()
    
    return jsonify({'message': 'Location updated successfully'})

@app.route('/api/optimize-routes', methods=['POST'])
def optimize_routes():
    today = datetime.now().date()
    
    # Get all stops with students who voted yes
    demanding_stops = db.session.query(BusStop, db.func.count(DailyVote.id).label('student_count')).join(
        Student, BusStop.id == Student.stop_id
    ).join(
        DailyVote, Student.id == DailyVote.student_id
    ).filter(
        DailyVote.vote_date == today,
        DailyVote.needs_bus == True
    ).group_by(BusStop.id).all()
    
    # School location (example coordinates)
    school_location = {'latitude': 12.9716, 'longitude': 77.5946}  # Bangalore example
    
    routes = []
    available_buses = Bus.query.filter_by(is_active=True).all()
    
    for i, bus in enumerate(available_buses):
        if i < len(demanding_stops):
            # Simple allocation - can be improved with better algorithms
            stops_for_bus = demanding_stops[i:i+3]  # Max 3 stops per bus
            
            optimizer = RouteOptimizer([s[0].__dict__ for s in stops_for_bus], school_location)
            # Simplified route calculation
            route_stops = [s[0] for s in stops_for_bus]
            
            routes.append({
                'bus': bus,
                'stops': route_stops,
                'total_students': sum(s[1] for s in stops_for_bus)
            })
    
    return jsonify({
        'routes': len(routes),
        'total_students_served': sum(r['total_students'] for r in routes)
    })

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        # Create sample bus stops if none exist
        if BusStop.query.count() == 0:
            sample_stops = [
                BusStop(name="Central Park Stop", latitude=12.9716, longitude=77.5946, address="Central Park, Bangalore"),
                BusStop(name="Tech Park Gate", latitude=12.9698, longitude=77.5986, address="Tech Park Main Gate"),
                BusStop(name="Metro Station", latitude=12.9750, longitude=77.5900, address="Bangalore Metro Station"),
                BusStop(name="Shopping Mall", latitude=12.9680, longitude=77.6000, address="Phoenix Mall Stop"),
                BusStop(name="Residential Complex", latitude=12.9800, longitude=77.5850, address="Green Valley Apartments")
            ]
            
            for stop in sample_stops:
                db.session.add(stop)
            
            # Create sample buses
            sample_buses = [
                Bus(bus_number="KA01-1234", capacity=50, driver_name="Rajesh Kumar"),
                Bus(bus_number="KA01-5678", capacity=45, driver_name="Suresh Reddy"),
                Bus(bus_number="KA01-9012", capacity=40, driver_name="Mahesh Singh")
            ]
            
            for bus in sample_buses:
                db.session.add(bus)
            
            db.session.commit()
            print("Sample data created!")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
