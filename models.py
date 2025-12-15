from flask_sqlalchemy import SQLAlchemy
import re
from datetime import datetime

db = SQLAlchemy()

def is_valid_email(email):
    """Validate email format using regex."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False, unique=True)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password = db.Column(db.String(120), nullable=False)
    # (Note: passwords stored in plaintext currently — consider hashing)
    
    def __repr__(self):
        return f'<User {self.username}>'

class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    email = db.Column(db.String(120), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('tickets', lazy=True))
    # payment and QR code fields removed to restore original model
    
    def __repr__(self):
        return f'<Ticket {self.id} - {self.name}>'
