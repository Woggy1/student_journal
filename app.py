from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate
from models import db, User, Subject, StudyMaterial, Group, Grade
from config import Config
import os
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Налаштування шляху для завантажень
    upload_folder = os.path.join(app.root_path, 'static/uploads')
    os.makedirs(upload_folder, exist_ok=True)
    app.config['UPLOAD_FOLDER'] = upload_folder
    app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB

    # Ініціалізація розширень
    db.init_app(app)
    Migrate(app, db)  # Для міграцій
    
    login_manager = LoginManager()
    login_manager.login_view = 'routes.login'
    login_manager.init_app(app)

    # Реєстрація Blueprint
    from routes import routes_app
    app.register_blueprint(routes_app)

    # Логування
    if not app.debug:
        handler = RotatingFileHandler('app.log', maxBytes=10000, backupCount=3)
        handler.setLevel(logging.INFO)
        app.logger.addHandler(handler)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', debug=True)  