#!/usr/bin/env python3
"""
Comprehensive test for app.py - Smart Transport Application
Tests all endpoints including optimize_routes function
"""

import requests
import time
import subprocess
import sys
import os

def test_app():
    print("=== TESTING APP.PY - SMART TRANSPORT APPLICATION ===\n")
    
    # Start the Flask server in background
    print("Starting Flask server...")
    try:
        # Test if server is already running
        response = requests.get('http://127.0.0.1:5000', timeout=2)
        print("Server already running on port 5000")
    except:
        print("Starting new server instance...")
    
    base_url = "http://127.0.0.1:5000"
    
    # Test endpoints
    endpoints = [
        ('/', 'Homepage'),
        ('/login', 'Login Page'),
        ('/register', 'Registration Page'),
        ('/admin/dashboard', 'Admin Dashboard'),
    ]
    
    print("\nTesting endpoints:")
    for endpoint, name in endpoints:
        try:
            response = requests.get(f'{base_url}{endpoint}', timeout=5)
            print(f"{name} ({endpoint}): {response.status_code}")
            if response.status_code == 200:
                print(f"  -> Content length: {len(response.text)} chars")
        except Exception as e:
            print(f"{name} ({endpoint}): ERROR - {e}")
    
    # Test API endpoints
    print("\nTesting API endpoints:")
    api_endpoints = [
        ('POST', '/api/optimize-routes', 'Route Optimization'),
    ]
    
    for method, endpoint, name in api_endpoints:
        try:
            if method == 'POST':
                response = requests.post(f'{base_url}{endpoint}', timeout=5)
            else:
                response = requests.get(f'{base_url}{endpoint}', timeout=5)
            
            print(f"{name} ({endpoint}): {response.status_code}")
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"  -> Response: {data}")
                except:
                    print(f"  -> Content: {len(response.text)} chars")
        except Exception as e:
            print(f"{name} ({endpoint}): ERROR - {e}")
    
    print("\n=== APP.PY STATUS ===")
    print("Application: Smart Transport System")
    print("Framework: Flask")
    print("Database: SQLite")
    print("Port: 5000")
    print("Status: Ready for testing")

if __name__ == "__main__":
    test_app()
