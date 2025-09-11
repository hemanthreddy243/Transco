#!/usr/bin/env python3
"""
Debug script to fix login issues
Creates sample users and tests login functionality
"""

from app import app, db, Student, BusStop
from werkzeug.security import generate_password_hash

def debug_login():
    with app.app_context():
        print('=== DEBUGGING LOGIN ISSUES ===')
        
        # Check if database has users
        student_count = Student.query.count()
        print(f'Total students: {student_count}')
        
        # Create sample bus stops if none exist
        stops = BusStop.query.all()
        if not stops:
            print('Creating sample bus stops...')
            sample_stops = [
                BusStop(name="Central Park", latitude=12.9716, longitude=77.5946, address="Central Park, Bangalore"),
                BusStop(name="Tech Park", latitude=12.9698, longitude=77.5986, address="Tech Park Main Gate"),
                BusStop(name="Metro Station", latitude=12.9750, longitude=77.5900, address="Bangalore Metro")
            ]
            for stop in sample_stops:
                db.session.add(stop)
            db.session.commit()
            stops = BusStop.query.all()
        
        # Create sample student
        if student_count == 0:
            print('Creating sample student...')
            sample_student = Student(
                student_id="STU001",
                name="Test Student",
                password_hash=generate_password_hash("password123"),
                stop_id=stops[0].id
            )
            db.session.add(sample_student)
            db.session.commit()
            print('Sample student created: STU001 / password123')
        
        # Show all students
        students = Student.query.all()
        print('\nAvailable students:')
        for student in students:
            print(f'  {student.student_id} - {student.name}')
        
        # Show all bus stops
        stops = BusStop.query.all()
        print('\nAvailable bus stops:')
        for stop in stops:
            print(f'  {stop.name}')

if __name__ == "__main__":
    debug_login()
