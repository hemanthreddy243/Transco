#!/usr/bin/env python3
"""
Additional models for live tracking and bus scheduling
"""

from app import db
from datetime import datetime

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
    status = db.Column(db.String(20), default='moving')  # moving, stopped, delayed
    
    bus = db.relationship('Bus')

class BusRoute(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    estimated_duration = db.Column(db.Integer, nullable=False)  # minutes
    active = db.Column(db.Boolean, default=True)
    
    stops = db.relationship('BusRouteStop', backref='route', lazy=True)

class BusRouteStop(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    route_id = db.Column(db.Integer, db.ForeignKey('bus_route.id'), nullable=False)
    stop_id = db.Column(db.Integer, db.ForeignKey('bus_stop.id'), nullable=False)
    stop_order = db.Column(db.Integer, nullable=False)
    estimated_arrival = db.Column(db.Time, nullable=False)
    
    stop = db.relationship('BusStop')
