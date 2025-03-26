# -*- coding: utf-8 -*-
import pytest
import os
from datetime import datetime
from io import BytesIO
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, current_app, url_for
from flask_login import LoginManager, current_user
from models import db, User, Group, Subject, Grade, StudyMaterial
from routes import routes_app

# Фікстура для створення тестового додатку
@pytest.fixture(scope='module')
def app():
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = 'test_uploads'
    app.config['SECRET_KEY'] = 'super-secret-key'
    
    # Ініціалізація Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'routes.login'
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Реєстрація блюпринта
    app.register_blueprint(routes_app)
    
    # Ініціалізація бази даних
    db.init_app(app)
    
    with app.app_context():
        db.create_all()
    
    yield app
    
    # Очистка після тестів
    with app.app_context():
        db.drop_all()

@pytest.fixture(scope='module')
def client(app):
    return app.test_client()

@pytest.fixture(autouse=True)
def cleanup_db(app):
    with app.app_context():
        db.session.remove()
        db.drop_all()
        db.create_all()

# Тести моделей
def test_user_model(app):
    with app.app_context():
        group = Group(name="TEST GROUP")
        user = User(
            full_name="Test User",
            email="test@example.com",
            password_hash=generate_password_hash("password"),
            role="student",
            group=group
        )
        db.session.add_all([group, user])
        db.session.commit()
        
        # Перевірка нормалізації назви групи
        assert group.name == "TEST GROUP"
        assert User.query.filter_by(email="test@example.com").first() is not None

def test_subject_model(app):
    with app.app_context():
        teacher = User(
            full_name="Test Teacher",
            email="teacher@test.com",
            password_hash=generate_password_hash("testpass"),
            role="teacher"
        )
        group = Group(name="Group A")
        subject = Subject(
            name="Math",
            teacher=teacher,
            group=group
        )
        db.session.add_all([teacher, group, subject])
        db.session.commit()
        
        assert subject.teacher.role == "teacher"
        assert group.subjects[0].name == "Math"

# Тести роутів
def test_register_route(client, app):
    response = client.post(url_for('routes.register'), data={
        'full_name': 'John Doe',
        'email': 'john@test.com',
        'password': 'SecurePass123',
        'role': 'student',
        'group_name': 'New Group'
    }, follow_redirects=True)
    
    assert 'Реєстрація успішна'.encode('utf-8') in response.data
    with app.app_context():
        user = User.query.filter_by(email='john@test.com').first()
        assert user is not None
        assert user.group.name == "NEW GROUP"

def test_login_route(client, app):
    with app.app_context():
        group = Group(name="Test Group")
        user = User(
            full_name="Test User",
            email="test@login.com",
            password_hash=generate_password_hash("testpass"),
            role="student",
            group=group
        )
        db.session.add_all([group, user])
        db.session.commit()

    response = client.post(url_for('routes.login'), data={
        'email': 'test@login.com',
        'password': 'testpass'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert 'Мої оцінки' .encode('utf-8') in response.data

def test_add_grade_flow(client, app):
    with app.app_context():
        group = Group(name="Grade Test Group")
        teacher = User(
            full_name="Student",
            email="math@teacher.com",
            password_hash=generate_password_hash("teach123"),
            role="teacher"
        )
        student = User(
            full_name="Student",
            email="student@test.com",
            password_hash=generate_password_hash("pass"),
            role="student",
            group=group
        )
        subject = Subject(
            name="Algebra",
            teacher=teacher,
            group=group
        )
        db.session.add_all([group, teacher, student, subject])
        db.session.commit()

    # Логін викладача
    client.post(url_for('routes.login'), data={
        'email': 'math@teacher.com',
        'password': 'teach123'
    }, follow_redirects=True)

    # Додавання оцінки
    response = client.post(url_for('routes.add_grade'), data={
        'student_id': 1,
        'subject_id': 1,
        'grade': '10',
        'date': datetime.now().date().isoformat(),
        'comment': 'Good work'
    }, follow_redirects=True)
    
    assert 'Оцінка додана'.encode('utf-8') in response.data
    with app.app_context():
        grade = Grade.query.first()
        assert grade.grade == 10
        assert grade.student.full_name == "Student"

def test_file_upload(client, app):
    with app.app_context():
        teacher = User(
            full_name="Upload Teacher",
            email="upload@test.com",
            password_hash=generate_password_hash("upload123"),
            role="teacher"
        )
        group = Group(name="Science")
        subject = Subject(name="Physics", teacher=teacher, group=group)
        db.session.add_all([teacher, group, subject])
        db.session.commit()

    # Логін викладача
    client.post(url_for('routes.login'), data={
        'email': 'upload@test.com',
        'password': 'upload123'
    }, follow_redirects=True)

    # Завантаження файлу
    test_file = (BytesIO(b'Test content'), 'test.pdf')
    response = client.post(
        url_for('routes.add_material', subject_id=1),
        data={
            'title': 'Quantum Physics',
            'description': 'Advanced material',
            'file': test_file
        },
        follow_redirects=True,
        content_type='multipart/form-data'
    )
    
    assert 'Матеріал успішно додано'.encode('utf-8') in response.data
    with app.app_context():
        material = StudyMaterial.query.first()
        assert material is not None

def test_invalid_email_registration(client):
    response = client.post(url_for('routes.register'), data={
        'full_name': 'Invalid Email',
        'email': 'invalid-email',
        'password': 'pass123',
        'role': 'student',
        'group_name': 'Group'
    }, follow_redirects=True)
    
    assert 'Невірний формат email'.encode('utf-8') in response.data

def test_unauthorized_access(client, app):
    with app.app_context():
        student = User(
            full_name="Student",
            email="student@access.com",
            password_hash=generate_password_hash("pass"),
            role="student"
        )
        db.session.add(student)
        db.session.commit()

    # Логін студента
    client.post(url_for('routes.login'), data={
        'email': 'student@access.com',
        'password': 'pass'
    }, follow_redirects=True)

    # Спроба доступу до сторінки викладача
    response = client.get(url_for('routes.add_subject'), follow_redirects=True)
    assert 'Доступ заборонено'.encode('utf-8') in response.data

def test_delete_subject_cascade(client, app):
    with app.app_context():
        teacher = User(
            full_name="Delete Teacher",
            email="delete@test.com",
            password_hash=generate_password_hash("delete123"),
            role="teacher"
        )
        group = Group(name="Lab Group")
        subject = Subject(name="Chemistry", teacher=teacher, group=group)
        student = User(
            full_name="Lab Student",
            email="lab@student.com",
            password_hash=generate_password_hash("pass"),
            role="student",
            group=group
        )
        grade = Grade(
            student=student,
            subject=subject,
            grade=9,
            date=datetime.now().date()
        )
        db.session.add_all([teacher, group, subject, student, grade])
        db.session.commit()

    # Логін викладача
    client.post(url_for('routes.login'), data={
        'email': 'delete@test.com',
        'password': 'delete123'
    }, follow_redirects=True)

    # Видалення предмету
    response = client.post(
        url_for('routes.delete_subject', subject_id=1),
        follow_redirects=True
    )
    
    assert 'видалено'.encode('utf-8') in response.data
    with app.app_context():
        assert Subject.query.count() == 0
        assert Grade.query.count() == 0
