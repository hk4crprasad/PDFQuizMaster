from app import db
from flask_login import UserMixin
from datetime import datetime
from sqlalchemy.sql import func
import json

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    tests = db.relationship('UserTest', backref='user', lazy=True)

class PDF(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    filepath = db.Column(db.String(255), nullable=False)
    title = db.Column(db.String(255))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    tests = db.relationship('Test', backref='pdf', lazy=True)

class Test(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pdf_id = db.Column(db.Integer, db.ForeignKey('pdf.id'), nullable=False)
    questions = db.Column(db.Text, nullable=False)  # JSON string
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user_tests = db.relationship('UserTest', backref='test', lazy=True)
    
    def get_questions(self):
        return json.loads(self.questions)

class UserTest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    test_id = db.Column(db.Integer, db.ForeignKey('test.id'), nullable=False)
    user_answers = db.Column(db.Text)  # JSON string
    score = db.Column(db.Float)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    
    def get_answers(self):
        return json.loads(self.user_answers) if self.user_answers else {}
