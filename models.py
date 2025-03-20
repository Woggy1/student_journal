from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
import re
from datetime import datetime

db = SQLAlchemy()

class StudyMaterial(db.Model):
    __tablename__ = 'study_material'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    file_path = db.Column(db.String(300))
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    subject = db.relationship('Subject', backref=db.backref('materials', lazy=True))

class User(db.Model, UserMixin):
    __tablename__ = 'user'
    
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum('student', 'teacher'), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'))
    
    # Відносини
    group = db.relationship('Group', backref='students')
    grades = db.relationship('Grade', back_populates='student')  # Змінено на back_populates

class Group(db.Model):
    __tablename__ = 'group'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    
    # Відносини
    subjects = db.relationship('Subject', back_populates='group')

    @staticmethod
    def normalize_name(name):
        return name.strip().upper()

class Subject(db.Model):
    __tablename__ = 'subject'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'))
    
    __table_args__ = (
        db.UniqueConstraint('name', 'group_id', name='_name_group_uc'),
    )
    
    # Відносини
    teacher = db.relationship('User', backref='subjects_taught')
    group = db.relationship('Group', back_populates='subjects')
    grades = db.relationship('Grade', backref='subject', cascade='all, delete-orphan')

class Grade(db.Model):
    __tablename__ = 'grade'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    grade = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    date = db.Column(db.Date, nullable=False)
    
    # Відносини
    student = db.relationship('User', back_populates='grades')  # Змінено на back_populates

def is_valid_email(email):
    return re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", email)