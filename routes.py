from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Subject, Grade, Group, is_valid_email, StudyMaterial  # Додано Group
from datetime import datetime
from werkzeug.utils import secure_filename
import os
from datetime import datetime, timedelta
from uuid import uuid4
from sqlalchemy import func

routes_app = Blueprint('routes', __name__)

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt', 'pptx'}


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in {'pdf', 'docx', 'txt', 'pptx'}

@routes_app.route('/')
def home():
    return render_template('base.html')

@routes_app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form.get('full_name')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')
        group_name = request.form.get('group_name') if role == 'student' else None

        if not is_valid_email(email):
            flash('Невірний формат email', 'error')
            return redirect(url_for('routes.register'))
        
        if ' ' not in full_name.strip():
            flash("Введіть повне ім'я", 'error')
            return redirect(url_for('routes.register'))

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Цей email вже зареєстровано!', 'error')
            return redirect(url_for('routes.register'))

        group = None
        if role == 'student':
            if not group_name:
                flash("Введіть назву групи", 'error')
                return redirect(url_for('routes.register'))
            
            normalized_name = Group.normalize_name(group_name)
            group = Group.query.filter_by(name=normalized_name).first()
            
            if not group:
                group = Group(name=normalized_name)
                db.session.add(group)
                db.session.commit()

        new_user = User(
            full_name=full_name,
            email=email,
            password_hash=generate_password_hash(password),
            role=role,
            group_id=group.id if role == 'student' else None
        )
        db.session.add(new_user)
        db.session.commit()
        flash('Реєстрація успішна! Увійдіть.', 'success')
        return redirect(url_for('routes.login'))
    
    return render_template('register.html')

@routes_app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('routes.dashboard'))
        else:
            flash('Невірний email або пароль', 'error')
    
    return render_template('login.html')

@routes_app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('routes.login'))

@routes_app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'student':
        grades = Grade.query.filter_by(student_id=current_user.id).all()
        return render_template('student_dashboard.html', grades=grades)
    else:
        subjects = Subject.query.filter_by(teacher_id=current_user.id).all()
        groups = Group.query.join(User).filter(User.role == 'student').distinct().all()
        return render_template('teacher_dashboard.html', subjects=subjects, groups=groups)

@routes_app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        old_group_id = current_user.group_id  # Зберігаємо стару групу
        new_full_name = request.form.get('full_name')
        new_email = request.form.get('email')
        new_password = request.form.get('password')
        group_action = request.form.get('group_action') if current_user.role == 'student' else None
        
        # Валідація імені та email
        if ' ' not in new_full_name.strip():
            flash("Введіть повне ім'я", 'error')
            return redirect(url_for('routes.edit_profile'))
        
        if not is_valid_email(new_email):
            flash('Невірний формат email', 'error')
            return redirect(url_for('routes.edit_profile'))
        
        existing_email = User.query.filter(User.email == new_email, User.id != current_user.id).first()
        if existing_email:
            flash('Email вже використовується', 'error')
            return redirect(url_for('routes.edit_profile'))
        
        # Обробка групи (тільки для студентів)
        if current_user.role == 'student':
            if group_action == 'existing':
                new_group_id = request.form.get('group_id')
                group = Group.query.get(new_group_id)
                if not group:
                    flash('Невірна група', 'error')
                    return redirect(url_for('routes.edit_profile'))
                current_user.group_id = group.id
                
            elif group_action == 'new':
                new_group_name = request.form.get('new_group_name', '').strip()
                if not new_group_name:
                    flash('Введіть назву групи', 'error')
                    return redirect(url_for('routes.edit_profile'))
                
                normalized_name = Group.normalize_name(new_group_name)
                existing_group = Group.query.filter_by(name=normalized_name).first()
                
                if existing_group:
                    current_user.group_id = existing_group.id
                else:
                    new_group = Group(name=normalized_name)
                    db.session.add(new_group)
                    try:
                        db.session.commit()  # Зберегти групу перед прив'язкою
                    except Exception as e:
                        db.session.rollback()
                        flash('Помилка при створенні групи', 'error')
                        return redirect(url_for('routes.edit_profile'))
                    current_user.group_id = new_group.id
            else:
                flash('Невірна дія для групи', 'error')
                return redirect(url_for('routes.edit_profile'))
        
        # Видалення оцінок при зміні групи
        if current_user.role == 'student' and current_user.group_id != old_group_id:
            # Оптимізований запит для видалення оцінок
            Grade.query.filter(
                Grade.student_id == current_user.id,
                Grade.subject.has(group_id=old_group_id)
            ).delete()
        
        # Оновлення даних користувача
        current_user.full_name = new_full_name
        current_user.email = new_email
        
        if new_password:
            current_user.password_hash = generate_password_hash(new_password)
        
        try:
            db.session.commit()
            flash('Профіль оновлено', 'success')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Помилка оновлення профілю: {str(e)}")
            flash('Помилка при оновленні профілю', 'error')
        
        return redirect(url_for('routes.dashboard'))
    
    groups = Group.query.all() if current_user.role == 'student' else []
    return render_template('edit_profile.html', groups=groups)


@routes_app.route('/add_subject', methods=['GET', 'POST'])
@login_required
def add_subject():
    if current_user.role != 'teacher':
        flash('Доступ заборонено', 'error')
        return redirect(url_for('routes.dashboard'))

    groups = Group.query.all()
    
    if request.method == 'POST':
        subject_name = request.form.get('subject_name')
        group_action = request.form.get('group_action')
        group_id = request.form.get('group_id')
        new_group_name = request.form.get('new_group_name')

        # Обробка групи
        if group_action == 'existing':
            group = Group.query.get(group_id)
            if not group:
                flash('Невірна група', 'error')
                return redirect(url_for('routes.add_subject'))
                
        elif group_action == 'new':
            if not new_group_name:
                flash('Введіть назву групи', 'error')
                return redirect(url_for('routes.add_subject'))
                
            normalized_name = Group.normalize_name(new_group_name)
            group = Group.query.filter_by(name=normalized_name).first()
            
            if not group:
                group = Group(name=normalized_name)
                db.session.add(group)
                db.session.commit()
                
            group_id = group.id
            
        else:
            flash('Невірна дія', 'error')
            return redirect(url_for('routes.add_subject'))

        # Перевірка унікальності предмету
        existing_subject = Subject.query.filter_by(
            name=subject_name,
            group_id=group_id
        ).first()
        
        if existing_subject:
            flash('Цей предмет вже існує у цій групі', 'error')
            return redirect(url_for('routes.add_subject'))
            
        new_subject = Subject(
            name=subject_name,
            teacher_id=current_user.id,
            group_id=group_id
        )
        db.session.add(new_subject)
        db.session.commit()
        
        flash('Предмет успішно додано', 'success')
        return redirect(url_for('routes.dashboard'))
    
    return render_template('add_subject.html', groups=groups)

@routes_app.route('/add_grade', methods=['GET', 'POST'])
@login_required
def add_grade():
    if current_user.role != 'teacher':
        flash('Доступ заборонено', 'error')
        return redirect(url_for('routes.dashboard'))

    groups = Group.query.join(User).filter(User.role == 'student').distinct().all()
    
    if request.method == 'POST':
        student_id = request.form.get('student_id')
        subject_id = request.form.get('subject_id')
        grade = request.form.get('grade')
        date_str = request.form.get('date')
        comment = request.form.get('comment')

        if not all([student_id, subject_id, grade, date_str]):
            flash("Заповніть усі обов'язкові поля", 'error')
            return redirect(url_for('routes.add_grade'))

        try:
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            flash("Невірний формат дати", 'error')
            return redirect(url_for('routes.add_grade'))

        try:
            grade_int = int(grade)
            if grade_int < 1 or grade_int > 12:
                raise ValueError
        except ValueError:
            flash("Оцінка має бути від 1 до 12", 'error')
            return redirect(url_for('routes.add_grade'))

        new_grade = Grade(
            student_id=student_id,
            subject_id=subject_id,
            grade=grade_int,
            date=date,
            comment=comment
        )
        db.session.add(new_grade)
        db.session.commit()
        flash('Оцінка додана', 'success')
        return redirect(url_for('routes.dashboard'))
    
    return render_template('add_grade.html', groups=groups)

@routes_app.route('/get_students')
@login_required
def get_students():
    group_id = request.args.get('group_id')
    students = User.query.filter_by(group_id=group_id, role='student').all()
    students_data = [{'id': s.id, 'full_name': s.full_name} for s in students]
    return jsonify({'students': students_data})

@routes_app.route('/get_subjects')
@login_required
def get_subjects():
    group_id = request.args.get('group_id')
    subjects = Subject.query.filter_by(group_id=group_id, teacher_id=current_user.id).all()
    subjects_data = [{'id': s.id, 'name': s.name} for s in subjects]
    return jsonify({'subjects': subjects_data})

@routes_app.route('/delete_subject/<int:subject_id>', methods=['POST'])
@login_required
def delete_subject(subject_id):
    if current_user.role != 'teacher':
        flash('Доступ заборонено', 'error')
        return redirect(url_for('routes.dashboard'))
    
    subject = Subject.query.get_or_404(subject_id)
    
    # Перевірка, чи предмет належить поточному вчителю
    if subject.teacher_id != current_user.id:
        flash('Ви не можете видалити цей предмет', 'error')
        return redirect(url_for('routes.dashboard'))
    
    # Видалити всі оцінки, пов'язані з предметом (каскадне видалення)
    Grade.query.filter_by(subject_id=subject.id).delete()
    
    # Видалити сам предмет
    db.session.delete(subject)
    db.session.commit()
    
    flash('Предмет та всі пов\'язані оцінки видалено', 'success')
    return redirect(url_for('routes.dashboard'))


@routes_app.route('/subject_grades/<int:subject_id>')
@login_required
def subject_grades(subject_id):
    if current_user.role != 'teacher':
        flash('Доступ заборонено', 'error')
        return redirect(url_for('routes.dashboard'))
    
    subject = Subject.query.get_or_404(subject_id)
    if subject.teacher_id != current_user.id:
        flash('Цей предмет не належить вам', 'error')
        return redirect(url_for('routes.dashboard'))
    
    grades = Grade.query.filter_by(subject_id=subject_id).all()
    return render_template('subject_grades.html', grades=grades, subject=subject)

@routes_app.route('/edit_grade/<int:grade_id>', methods=['GET', 'POST'])
@login_required
def edit_grade(grade_id):
    grade = Grade.query.get_or_404(grade_id)
    subject = Subject.query.get(grade.subject_id)
    
    if current_user.role != 'teacher' or subject.teacher_id != current_user.id:
        flash('Доступ заборонено', 'error')
        return redirect(url_for('routes.dashboard'))
    
    if request.method == 'POST':
        try:
            grade.grade = int(request.form['grade'])
            grade.date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
            grade.comment = request.form.get('comment')
            db.session.commit()
            flash('Оцінку оновлено', 'success')
            return redirect(url_for('routes.subject_grades', subject_id=grade.subject_id))
        except ValueError:
            flash('Невірні дані', 'error')
    
    return render_template('edit_grade.html', grade=grade)

@routes_app.route('/delete_grade/<int:grade_id>', methods=['POST'])
@login_required
def delete_grade(grade_id):
    grade = Grade.query.get_or_404(grade_id)
    subject = Subject.query.get(grade.subject_id)
    
    if current_user.role != 'teacher' or subject.teacher_id != current_user.id:
        flash('Доступ заборонено', 'error')
        return redirect(url_for('routes.dashboard'))
    
    db.session.delete(grade)
    db.session.commit()
    flash('Оцінку видалено', 'success')
    return redirect(url_for('routes.subject_grades', subject_id=grade.subject_id))


@routes_app.route('/add_material/<int:subject_id>', methods=['GET', 'POST'])
@login_required
def add_material(subject_id):
    try:
        if current_user.role != 'teacher':
            flash('Доступ заборонено', 'error')
            return redirect(url_for('routes.dashboard'))
        
        subject = Subject.query.get_or_404(subject_id)
        
        if request.method == 'POST':
            title = request.form.get('title')
            description = request.form.get('description')
            file = request.files.get('file')
            
            # Обробка файлу
            relative_path = None
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                unique_filename = f"{uuid4().hex}_{filename}"
                upload_folder = current_app.config['UPLOAD_FOLDER']
                os.makedirs(upload_folder, exist_ok=True)  # Створення папки, якщо не існує
                file_path = os.path.join(upload_folder, unique_filename)
                file.save(file_path)
                relative_path = os.path.join('uploads', unique_filename)
            
            new_material = StudyMaterial(
                title=title,
                description=description,
                file_path=relative_path,
                subject_id=subject_id
            )
            db.session.add(new_material)
            db.session.commit()
            flash('Матеріал успішно додано', 'success')
            return redirect(url_for('routes.subject_materials', subject_id=subject_id))
        
        return render_template('add_material.html', subject=subject)
    
    except Exception as e:
        current_app.logger.error(f"Помилка додавання матеріалу: {str(e)}")
        flash('Сталася помилка під час додавання матеріалу', 'error')
        return redirect(url_for('routes.subject_materials', subject_id=subject_id))


@routes_app.route('/delete_material/<int:material_id>', methods=['POST'])
@login_required
def delete_material(material_id):
    material = StudyMaterial.query.get_or_404(material_id)
    subject_id = material.subject_id
    
    if current_user.role != 'teacher' or material.subject.teacher_id != current_user.id:
        flash('Доступ заборонено', 'error')
        return redirect(url_for('routes.dashboard'))
    
    # Видалення файлу
    if material.file_path:
        file_path = os.path.join(current_app.root_path, 'static', material.file_path)
        if os.path.exists(file_path):
            os.remove(file_path)
    
    db.session.delete(material)
    db.session.commit()
    flash('Матеріал видалено', 'success')
    return redirect(url_for('routes.subject_materials', subject_id=subject_id))

@routes_app.route('/subject/<int:subject_id>/materials')
@login_required
def subject_materials(subject_id):
    try:
        subject = Subject.query.get_or_404(subject_id)
        
        if current_user.role != 'teacher' or subject.teacher_id != current_user.id:
            flash('Доступ заборонено', 'error')
            return redirect(url_for('routes.dashboard'))
        
        # Отримання матеріалів
        materials = StudyMaterial.query.filter_by(subject_id=subject_id).order_by(StudyMaterial.created_at.desc()).all()
        
        # Отримання оцінок з іменами студентів
        grades = db.session.query(
            Grade, 
            User.full_name
        ).join(
            User, Grade.student_id == User.id
        ).filter(
            Grade.subject_id == subject_id,
            User.group_id == subject.group_id
        ).order_by(Grade.date.desc()).all()
        
        return render_template(
            'subject_materials.html',
            subject=subject,
            materials=materials,
            grades=grades
        )
    
    except Exception as e:
        current_app.logger.error(f"Помилка завантаження сторінки: {str(e)}")
        flash('Помилка завантаження даних', 'error')
        return redirect(url_for('routes.dashboard'))
    
@routes_app.route('/student_stats')
@login_required
def student_stats():
    student_id = current_user.id
    grades = Grade.query.filter_by(student_id=student_id).all()
    
    # Середній бал
    overall_avg = db.session.query(func.avg(Grade.grade)).filter_by(student_id=student_id).scalar() or 0
    
    # Статистика по предметах
    subjects_stats = {}
    for subject in Subject.query.all():
        subject_grades = Grade.query.filter_by(
            student_id=student_id, 
            subject_id=subject.id
        ).order_by(Grade.date.asc()).all()
        
        if not subject_grades:
            continue

        all_grades = [g.grade for g in subject_grades]
        avg = round(sum(all_grades)/len(all_grades), 1)
        last_grade = subject_grades[-1].grade

        # Нова логіка тенденції
        trend = "neutral"
        if len(all_grades) >= 2:
            # Розділяємо всі оцінки на дві частини
            split_index = len(all_grades) // 2
            first_part = all_grades[:split_index]
            second_part = all_grades[split_index:]
            
            avg_first = sum(first_part)/len(first_part)
            avg_second = sum(second_part)/len(second_part)
            
            if avg_second > avg_first + 0.2:
                trend = "up"
            elif avg_second < avg_first - 0.2:
                trend = "down"
            else:
                trend = "stable"

        subjects_stats[subject.name] = {
            "average": avg,
            "last_grade": last_grade,
            "trend": trend
        }


    # Дані для графіка
    grades_list = [g.grade for g in grades]
    dates = [g.date.strftime("%Y-%m-%d") for g in grades if g.date]

    # Відсоток успішних оцінок
    success_percentage = round(
        (sum(1 for g in grades if g.grade >= 7) / len(grades) * 100), 2
    ) if grades else 0

    return render_template(
        'student_stats.html',
        overall_avg=round(overall_avg, 1),
        grades=grades,
        subjects_stats=subjects_stats,
        success_percentage=success_percentage,
        dates=dates,
        grades_list=grades_list
    )