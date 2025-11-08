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

# Import admin blueprint
from admin_auth import admin_bp



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

# Dynamic Routing Algorithm with College as Center Point
class DynamicRouter:
    def __init__(self, college_location, demanding_stops, available_buses):
        self.college_location = college_location
        self.demanding_stops = demanding_stops  # List of (stop, student_count) tuples
        self.available_buses = available_buses
        self.bus_colors = [
            '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
            '#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9'
        ]
        
    def calculate_distance(self, point1, point2):
        """Calculate distance between two GPS coordinates"""
        return geodesic(point1, point2).kilometers
    
    def get_distance_from_college(self, stop):
        """Calculate distance from college to a stop"""
        stop_location = (stop.latitude, stop.longitude)
        college_point = (self.college_location['latitude'], self.college_location['longitude'])
        return self.calculate_distance(stop_location, college_point)
    
    def farthest_first_clustering(self):
        """Implement farthest-first clustering algorithm"""
        if not self.demanding_stops:
            return []
        
        # Sort stops by distance from college (farthest first)
        sorted_stops = sorted(self.demanding_stops, 
                            key=lambda x: self.get_distance_from_college(x[0]), 
                            reverse=True)
        
        clusters = []
        remaining_stops = sorted_stops.copy()
        
        for bus in self.available_buses:
            if not remaining_stops:
                break
                
            # Start with the farthest remaining stop
            cluster_stops = [remaining_stops[0]]
            remaining_stops.pop(0)
            current_capacity = cluster_stops[0][1]  # student count of first stop
            
            # Find nearest stops that fit within capacity
            # Use a better strategy: find nearest to college first, then nearest neighbors
            max_stops_per_bus = 3
            stops_added = 1
            
            while remaining_stops and stops_added < max_stops_per_bus and current_capacity < bus.capacity:
                # For the first additional stop, find nearest to college
                # For subsequent stops, find nearest to any stop in the cluster
                nearest_stop_idx = -1
                min_distance = float('inf')
                
                for i, (stop, student_count) in enumerate(remaining_stops):
                    # Check if adding this stop would exceed capacity
                    if current_capacity + student_count <= bus.capacity:
                        stop_location = (stop.latitude, stop.longitude)
                        
                        # Calculate distance to all stops in cluster and find minimum
                        min_cluster_distance = float('inf')
                        for cluster_stop, _ in cluster_stops:
                            cluster_location = (cluster_stop.latitude, cluster_stop.longitude)
                            distance = self.calculate_distance(stop_location, cluster_location)
                            min_cluster_distance = min(min_cluster_distance, distance)
                        
                        if min_cluster_distance < min_distance:
                            min_distance = min_cluster_distance
                            nearest_stop_idx = i
                
                if nearest_stop_idx != -1:
                    # Add the nearest stop to cluster
                    cluster_stops.append(remaining_stops[nearest_stop_idx])
                    current_capacity += remaining_stops[nearest_stop_idx][1]
                    remaining_stops.pop(nearest_stop_idx)
                    stops_added += 1
                else:
                    # No more stops fit in this bus
                    break
            
            # Only add cluster if it has stops
            if cluster_stops:
                clusters.append({
                    'bus': bus,
                    'stops': cluster_stops,
                    'total_students': current_capacity,
                    'color': self.bus_colors[len(clusters) % len(self.bus_colors)]
                })
        
        return clusters
    
    def optimize_route_within_cluster(self, cluster):
        """Optimize route order within a cluster using nearest neighbor"""
        stops = cluster['stops']
        if len(stops) <= 1:
            return stops, 0
        
        # Start from college
        current_location = (self.college_location['latitude'], self.college_location['longitude'])
        unvisited_stops = stops.copy()
        optimized_route = []
        total_distance = 0
        
        while unvisited_stops:
            # Find nearest unvisited stop
            nearest_stop_idx = -1
            min_distance = float('inf')
            
            for i, (stop, student_count) in enumerate(unvisited_stops):
                stop_location = (stop.latitude, stop.longitude)
                distance = self.calculate_distance(current_location, stop_location)
                
                if distance < min_distance:
                    min_distance = distance
                    nearest_stop_idx = i
            
            if nearest_stop_idx != -1:
                # Add to route
                optimized_route.append(unvisited_stops[nearest_stop_idx])
                total_distance += min_distance
                
                # Update current location
                stop = unvisited_stops[nearest_stop_idx][0]
                current_location = (stop.latitude, stop.longitude)
                unvisited_stops.pop(nearest_stop_idx)
        
        # Add distance from last stop back to college
        last_stop = optimized_route[-1][0]
        last_location = (last_stop.latitude, last_stop.longitude)
        college_point = (self.college_location['latitude'], self.college_location['longitude'])
        total_distance += self.calculate_distance(last_location, college_point)
        
        return optimized_route, total_distance
    
    def generate_optimal_routes(self):
        """Generate optimal routes with minimal total cost"""
        # Step 1: Farthest-first clustering
        clusters = self.farthest_first_clustering()
        
        # Step 2: Optimize route within each cluster
        optimized_routes = []
        total_cost = 0
        
        for cluster in clusters:
            optimized_route, route_distance = self.optimize_route_within_cluster(cluster)
            
            optimized_routes.append({
                'bus': cluster['bus'],
                'stops': optimized_route,
                'total_students': cluster['total_students'],
                'route_distance': route_distance,
                'color': cluster['color'],
                'capacity_utilization': (cluster['total_students'] / cluster['bus'].capacity) * 100
            })
            
            total_cost += route_distance
        
        return {
            'routes': optimized_routes,
            'total_cost': total_cost,
            'total_students_served': sum(route['total_students'] for route in optimized_routes),
            'total_buses_used': len(optimized_routes)
        }

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
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        student_id = request.form['student_id']
        name = request.form['name']
        password = request.form['password']
        stop_id = request.form['stop_id']
        
        # Check if student already exists
        existing_student = Student.query.filter_by(student_id=student_id).first()
        if existing_student:
            flash('Student ID already exists!')
            return render_template('register.html')
        
        # Get bus stop
        stop = BusStop.query.get(stop_id)
        if not stop:
            flash('Bus stop not found!')
            return render_template('register.html')
        
        # Create new student
        student = Student(
            student_id=student_id,
            name=name,
            password_hash=generate_password_hash(password),
            stop_id=stop.id
        )
        
        db.session.add(student)
        db.session.commit()
        
        flash('Registration successful! Please login.')
        return redirect(url_for('login'))
    
    # Get all bus stops for dropdown
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

def get_bus_schedule_data():
    """Get bus schedule data for today"""
    today = datetime.now().date()
    
    # Get all route assignments for today
    route_assignments = RouteAssignment.query.filter_by(
        route_date=today
    ).all()
    
    schedule_data = []
    for assignment in route_assignments:
        # Get bus details
        bus = Bus.query.get(assignment.bus_id)
        if bus:
            # Get stop details
            stop = BusStop.query.get(assignment.stop_id)
            if stop:
                # Get students at this stop
                students_at_stop = Student.query.filter_by(stop_id=stop.id, is_active=True).all()
                
                schedule_data.append({
                    'route_id': f'route_{bus.id}_{stop.id}',
                    'route_name': f'Bus {bus.bus_number} - {stop.name}',
                    'bus_id': bus.id,
                    'bus_number': bus.bus_number,
                    'driver_name': bus.driver_name,
                    'stops': [{
                        'stop_id': stop.id,
                        'stop_name': stop.name,
                        'stop_address': stop.address,
                        'arrival_time': assignment.estimated_time,
                        'student_count': len(students_at_stop)
                    }],
                    'total_students': len(students_at_stop)
                })
    
    return schedule_data

def is_emergency_window_active():
    """Check if emergency window is currently active"""
    now = datetime.now()
    # Emergency window is active from 6:00 AM to 8:00 AM and 3:00 PM to 5:00 PM
    morning_start = now.replace(hour=6, minute=0, second=0, microsecond=0)
    morning_end = now.replace(hour=8, minute=0, second=0, microsecond=0)
    afternoon_start = now.replace(hour=15, minute=0, second=0, microsecond=0)
    afternoon_end = now.replace(hour=17, minute=0, second=0, microsecond=0)
    
    return (morning_start <= now <= morning_end) or (afternoon_start <= now <= afternoon_end)

@app.route('/api/emergency-status')
def emergency_status():
    """API endpoint to check if emergency window is active"""
    emergency_active = is_emergency_window_active()
    return jsonify({
        'is_active': emergency_active,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/dashboard')
@login_required
def dashboard():
    today = datetime.now().date()
    
    # Get today's vote for current user
    today_vote = DailyVote.query.filter_by(
        student_id=current_user.id,
        vote_date=today
    ).first()
    
    # Check if emergency window is active
    emergency_active = is_emergency_window_active()
    
    # Get bus schedule for today
    bus_schedule = get_bus_schedule_data()
    
    # Get recent emergency requests for current user
    recent_emergencies = EmergencyRequest.query.filter_by(
        student_id=current_user.id
    ).order_by(EmergencyRequest.request_time.desc()).limit(3).all()
    
    return render_template('dashboard.html',
                         current_user=current_user,
                         today_vote=today_vote,
                         emergency_active=emergency_active,
                         user_stop=current_user.stop,
                         now=datetime.now(),
                         bus_schedule=bus_schedule,
                         bus_location=None,
                         recent_emergencies=recent_emergencies)

@app.route('/bus-routes')
@login_required
def bus_routes():
    """Display all bus routes for students"""
    today = datetime.now().date()
    
    # Get all route assignments for today
    route_assignments = db.session.query(RouteAssignment).filter(
        RouteAssignment.route_date == today
    ).order_by(RouteAssignment.bus_id, RouteAssignment.stop_order).all()
    
    # Group by bus and create route structure
    routes = {}
    for assignment in route_assignments:
        bus_id = assignment.bus_id
        if bus_id not in routes:
            bus = assignment.bus
            routes[bus_id] = {
                'bus_number': bus.bus_number,
                'driver_name': bus.driver_name or 'TBD',
                'capacity': bus.capacity,
                'is_active': bus.is_active,
                'stop_assignments': [],
                'assigned_students': []
            }
        
        routes[bus_id]['stop_assignments'].append(assignment)
    
    # Get students for each route
    total_students = 0
    for bus_id, route in routes.items():
        # Get students who voted YES and are assigned to stops on this route
        stop_ids = [sa.stop_id for sa in route['stop_assignments']]
        
        students_on_route = db.session.query(Student).join(DailyVote).filter(
            Student.stop_id.in_(stop_ids),
            DailyVote.vote_date == today,
            DailyVote.needs_bus == True
        ).all()
        
        route['assigned_students'] = students_on_route
        total_students += len(students_on_route)
    
    # Convert to list for template
    routes_list = list(routes.values())
    
    return render_template('bus_routes.html',
                         routes=routes_list,
                         total_students=total_students,
                         last_updated=datetime.now())

@app.route('/route-map')
@login_required
def route_map():
    """Display interactive route optimization map"""
    return render_template('route_map.html')

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
        'departure_time': schedule.departure_time.strftime('%I:%M %p'),  # 12-hour format
        'arrival_time': schedule.arrival_time.strftime('%I:%M %p'),      # 12-hour format
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
        # Return school location as default (Vignan Institute of Technology, Hyderabad)
        return jsonify({
            'latitude': 17.4065,
            'longitude': 78.4772,
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
        latitude=data.get('latitude', 17.4065),
        longitude=data.get('longitude', 78.4772),
        speed=data.get('speed', 0.0),
        status=data.get('status', 'moving')
    )
    db.session.add(location)
    db.session.commit()
    
    return jsonify({'message': 'Location updated successfully'})

@app.route('/api/bus-locations')
def get_bus_locations():
    """Get current bus locations for real-time tracking"""
    # Get the most recent location for each bus
    subquery = db.session.query(
        BusLocation.bus_id,
        db.func.max(BusLocation.timestamp).label('max_timestamp')
    ).group_by(BusLocation.bus_id).subquery()
    
    locations = db.session.query(BusLocation).join(
        subquery,
        db.and_(
            BusLocation.bus_id == subquery.c.bus_id,
            BusLocation.timestamp == subquery.c.max_timestamp
        )
    ).all()
    
    if not locations:
        # Return default locations for demo
        available_buses = Bus.query.filter_by(is_active=True).all()
        locations = []
        for i, bus in enumerate(available_buses):
            # Create demo locations around college
            locations.append({
                'bus_id': bus.id,
                'bus_number': bus.bus_number,
                'latitude': 17.4065 + (i * 0.01),
                'longitude': 78.4772 + (i * 0.01),
                'status': 'moving',
                'speed': 20.0,
                'timestamp': datetime.now().strftime('%I:%M %p')
            })
        return jsonify(locations)
    
    # Format real locations
    result = []
    for location in locations:
        bus = Bus.query.get(location.bus_id)
        result.append({
            'bus_id': location.bus_id,
            'bus_number': bus.bus_number if bus else 'Unknown',
            'latitude': location.latitude,
            'longitude': location.longitude,
            'status': location.status,
            'speed': location.speed,
            'timestamp': location.timestamp.strftime('%I:%M %p')
        })
    
    return jsonify(result)

@app.route('/api/optimize-routes', methods=['POST'])
def optimize_routes():
    """Dynamic route optimization using farthest-first clustering"""
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
    
    # Vignan Institute of Technology, Deshmuki, Hyderabad coordinates
    college_location = {'latitude': 17.4065, 'longitude': 78.4772}
    
    # Get available buses
    available_buses = Bus.query.filter_by(is_active=True).all()
    
    if not demanding_stops:
        return jsonify({
            'message': 'No students need bus service today',
            'routes': [],
            'total_cost': 0,
            'total_students_served': 0,
            'total_buses_used': 0
        })
    
    # Initialize dynamic router
    router = DynamicRouter(college_location, demanding_stops, available_buses)
    
    # Generate optimal routes
    result = router.generate_optimal_routes()
    
    # Format response for frontend
    formatted_routes = []
    for route in result['routes']:
        formatted_route = {
            'bus_number': route['bus'].bus_number,
            'driver_name': route['bus'].driver_name or 'TBD',
            'capacity': route['bus'].capacity,
            'color': route['color'],
            'total_students': route['total_students'],
            'route_distance': round(route['route_distance'], 2),
            'capacity_utilization': round(route['capacity_utilization'], 1),
            'stops': []
        }
        
        # Add stop information
        for stop, student_count in route['stops']:
            formatted_route['stops'].append({
                'id': stop.id,
                'name': stop.name,
                'latitude': stop.latitude,
                'longitude': stop.longitude,
                'address': stop.address,
                'student_count': student_count
            })
        
        formatted_routes.append(formatted_route)
    
    return jsonify({
        'routes': formatted_routes,
        'total_cost': round(result['total_cost'], 2),
        'total_students_served': result['total_students_served'],
        'total_buses_used': result['total_buses_used'],
        'college_location': college_location,
        'algorithm_used': 'Dynamic Farthest-First Clustering with Nearest Neighbor Optimization',
        'optimization_timestamp': datetime.now().isoformat()
    })

@app.route('/api/simulate-votes', methods=['POST'])
def simulate_votes():
    """Simulate votes for all students for testing purposes"""
    today = datetime.now().date()
    
    # Get all students
    students = Student.query.all()
    
    if not students:
        return jsonify({'message': 'No students found in database', 'votes_created': 0})
    
    # Delete existing votes for today to avoid duplicates
    DailyVote.query.filter_by(vote_date=today).delete()
    
    # Create votes for all students (all need bus)
    votes_created = 0
    for student in students:
        vote = DailyVote(
            student_id=student.id,
            vote_date=today,
            needs_bus=True
        )
        db.session.add(vote)
        votes_created += 1
    
    db.session.commit()
    
    return jsonify({
        'message': f'Successfully simulated votes for {votes_created} students',
        'votes_created': votes_created,
        'date': today.strftime('%Y-%m-%d'),
        'all_need_bus': True
    })

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        # Create sample bus stops if none exist
        if BusStop.query.count() == 0:
            # Create sample bus stops at different locations around Hyderabad
            sample_stops = [
                BusStop(name="Central Park Stop", latitude=17.4065, longitude=78.4772, address="Central Park, Hyderabad"),
                BusStop(name="Tech Park Gate", latitude=17.4156, longitude=78.4856, address="HITEC City Main Gate"),
                BusStop(name="Metro Station", latitude=17.3987, longitude=78.4689, address="Ameerpet Metro Station"),
                BusStop(name="Shopping Mall", latitude=17.4325, longitude=78.4923, address="Inorbit Mall, Madhapur"),
                BusStop(name="Residential Complex", latitude=17.3856, longitude=78.4567, address="Green Valley Apartments, Banjara Hills"),
                BusStop(name="School Area", latitude=17.4234, longitude=78.4789, address="Jubilee Hills School Zone"),
                BusStop(name="Hospital Area", latitude=17.3923, longitude=78.4890, address="Apollo Hospital, Jubilee Hills"),
                BusStop(name="Office Complex", latitude=17.4456, longitude=78.5012, address="Cyber Towers, HITEC City"),
                BusStop(name="University Gate", latitude=17.3789, longitude=78.4456, address="Osmania University Gate"),
                BusStop(name="Market Area", latitude=17.4123, longitude=78.4678, address="Koti Market, Abids")
            ]
            
            for stop in sample_stops:
                db.session.add(stop)
            
            # Create sample buses with capacity of 10 for testing
            sample_buses = [
                Bus(bus_number="KA01-1234", capacity=10, driver_name="Rajesh Kumar"),
                Bus(bus_number="KA01-5678", capacity=10, driver_name="Suresh Reddy"),
                Bus(bus_number="KA01-9012", capacity=10, driver_name="Mahesh Singh"),
                Bus(bus_number="KA01-3456", capacity=10, driver_name="Anita Sharma"),
                Bus(bus_number="KA01-7890", capacity=10, driver_name="Prakash Patel")
            ]
            
            for bus in sample_buses:
                db.session.add(bus)
            
            db.session.commit()
            
            # Create sample students assigned to different stops (3 students per stop for testing)
            sample_students = [
                # Stop 1 - Central Park
                Student(name="Alice Johnson", email="alice@example.com", phone="1234567890", stop_id=1),
                Student(name="Bob Smith", email="bob@example.com", phone="2345678901", stop_id=1),
                Student(name="Charlie Brown", email="charlie@example.com", phone="3456789012", stop_id=1),
                
                # Stop 2 - Tech Park Gate
                Student(name="Diana Prince", email="diana@example.com", phone="4567890123", stop_id=2),
                Student(name="Eve Wilson", email="eve@example.com", phone="5678901234", stop_id=2),
                Student(name="Frank Miller", email="frank@example.com", phone="6789012345", stop_id=2),
                
                # Stop 3 - Metro Station
                Student(name="Grace Lee", email="grace@example.com", phone="7890123456", stop_id=3),
                Student(name="Henry Davis", email="henry@example.com", phone="8901234567", stop_id=3),
                Student(name="Ivy Chen", email="ivy@example.com", phone="9012345678", stop_id=3),
                
                # Stop 4 - Shopping Mall
                Student(name="Jack Taylor", email="jack@example.com", phone="0123456789", stop_id=4),
                Student(name="Karen White", email="karen@example.com", phone="1122334455", stop_id=4),
                Student(name="Leo Garcia", email="leo@example.com", phone="2233445566", stop_id=4),
                
                # Stop 5 - Residential Complex
                Student(name="Maya Patel", email="maya@example.com", phone="3344556677", stop_id=5),
                Student(name="Noah Kim", email="noah@example.com", phone="4455667788", stop_id=5),
                Student(name="Olivia Brown", email="olivia@example.com", phone="5566778899", stop_id=5),
                
                # Stop 6 - School Area
                Student(name="Peter Jones", email="peter@example.com", phone="6677889900", stop_id=6),
                Student(name="Quinn Adams", email="quinn@example.com", phone="7788990011", stop_id=6),
                Student(name="Ruby Singh", email="ruby@example.com", phone="8899001122", stop_id=6),
                
                # Stop 7 - Hospital Area
                Student(name="Sam Wilson", email="sam@example.com", phone="9900112233", stop_id=7),
                Student(name="Tina Martinez", email="tina@example.com", phone="0011223344", stop_id=7),
                Student(name="Uma Sharma", email="uma@example.com", phone="1122334455", stop_id=7),
                
                # Stop 8 - Office Complex
                Student(name="Victor Lee", email="victor@example.com", phone="2233445566", stop_id=8),
                Student(name="Wendy Chen", email="wendy@example.com", phone="3344556677", stop_id=8),
                Student(name="Xavier Kumar", email="xavier@example.com", phone="4455667788", stop_id=8),
                
                # Stop 9 - University Gate
                Student(name="Yuki Tanaka", email="yuki@example.com", phone="5566778899", stop_id=9),
                Student(name="Zara Ahmed", email="zara@example.com", phone="6677889900", stop_id=9),
                Student(name="Alex Rodriguez", email="alex@example.com", phone="7788990011", stop_id=9),
                
                # Stop 10 - Market Area
                Student(name="Bella Thompson", email="bella@example.com", phone="8899001122", stop_id=10),
                Student(name="Carlos Mendez", email="carlos@example.com", phone="9900112233", stop_id=10),
                Student(name="Diana Ross", email="diana.ross@example.com", phone="0011223344", stop_id=10)
            ]
            
            for student in sample_students:
                db.session.add(student)
            
            db.session.commit()
            
            # Create sample votes for today (all students need bus)
            today = datetime.now().date()
            for student in sample_students:
                vote = DailyVote(
                    student_id=student.id,
                    vote_date=today,
                    needs_bus=True
                )
                db.session.add(vote)
            
            db.session.commit()
            print("Sample data created with students and votes!")
    
    # Register admin blueprint
    app.register_blueprint(admin_bp)
    
    app.run(debug=True, host='0.0.0.0', port=5000)
