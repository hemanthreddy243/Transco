#!/usr/bin/env python3
"""
Admin authentication and data import system
Provides secure admin login and data management
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import csv
import io

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Admin credentials (hardcoded for demo - use environment variables in production)
ADMIN_CREDENTIALS = {
    'username': 'admin',
    'password': 'admin123'  # In production, use: generate_password_hash('admin123')
}

def admin_required(f):
    """Decorator to require admin authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session:
            flash('Please login as admin to access this page.')
            return redirect(url_for('admin.admin_login'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if username == ADMIN_CREDENTIALS['username'] and password == ADMIN_CREDENTIALS['password']:
            session['admin_logged_in'] = True
            session['admin_username'] = username
            flash('Admin login successful!')
            return redirect(url_for('admin.admin_dashboard'))
        else:
            flash('Invalid admin credentials!')
    
    return render_template('admin_login.html')

@admin_bp.route('/logout')
def admin_logout():
    """Admin logout"""
    session.pop('admin_logged_in', None)
    session.pop('admin_username', None)
    flash('Admin logged out successfully!')
    return redirect(url_for('admin.admin_login'))

@admin_bp.route('/dashboard')
@admin_required
def admin_dashboard():
    """Protected admin dashboard"""
    from app import DailyVote, Student, BusStop, EmergencyRequest, Bus
    
    today = datetime.now().date()
    
    # Get today's votes
    votes = current_app.db.session.query(DailyVote, Student, BusStop).join(
        Student, DailyVote.student_id == Student.id
    ).join(
        BusStop, Student.stop_id == BusStop.id
    ).filter(DailyVote.vote_date == today).all()
    
    # Get emergency requests
    emergency_requests = current_app.db.session.query(EmergencyRequest, Student, BusStop).join(
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

@admin_bp.route('/import/students', methods=['GET', 'POST'])
@admin_required
def import_students():
    """Import students from CSV"""
    from app import Student, BusStop
    
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
                        existing = current_app.db.session.query(Student).filter_by(student_id=row['student_id']).first()
                        if existing:
                            continue
                        
                        # Get bus stop ID
                        stop = current_app.db.session.query(BusStop).filter_by(name=row['stop_name']).first()
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
                        current_app.db.session.add(student)
                        imported_count += 1
                    
                    except Exception as e:
                        flash(f'Error importing row: {str(e)}')
                
                current_app.db.session.commit()
                flash(f'Successfully imported {imported_count} students!')
                
            except Exception as e:
                flash(f'Error importing file: {str(e)}')
        else:
            flash('Please upload a CSV file')
    
    return render_template('import_students.html')

@admin_bp.route('/import/stops', methods=['GET', 'POST'])
@admin_required
def import_stops():
    """Import bus stops from CSV"""
    from app import BusStop
    
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
                        # Check if stop already exists
                        existing = current_app.db.session.query(BusStop).filter_by(name=row['name']).first()
                        if existing:
                            continue
                        
                        stop = BusStop(
                            name=row['name'],
                            latitude=float(row['latitude']),
                            longitude=float(row['longitude']),
                            address=row.get('address', '')
                        )
                        current_app.db.session.add(stop)
                        imported_count += 1
                    
                    except Exception as e:
                        flash(f'Error importing row: {str(e)}')
                
                current_app.db.session.commit()
                flash(f'Successfully imported {imported_count} bus stops!')
                
            except Exception as e:
                flash(f'Error importing file: {str(e)}')
        else:
            flash('Please upload a CSV file')
    
    return render_template('import_stops.html')
