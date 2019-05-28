from flask import Flask
from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager

import os
import logging
from logging.handlers import SMTPHandler, RotatingFileHandler

db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)
    login.init_app(app)

    from app.report import bp as report_bp
    app.register_blueprint(report_bp, url_prefix='/api/report')

    # from app.auth import bp as auth_bp
    # app.register_blueprint(auth_bp, url_prefix='/api/auth')

    from app.search import bp as search_bp
    app.register_blueprint(search_bp, url_prefix='/api/search')

    from app.analysis import bp as analysis_bp
    app.register_blueprint(analysis_bp, url_prefix='/api/analysis')

    if not app.debug and not app.testing:
        if app.config['MAIL_SERVER']:
            auth = None
            if app.config['MAIL_USERNAME'] or app.config['MAIL_PASSWORD']:
                auth = (app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
            secure = None
            if app.config['MAIL_USE_TLS']:
                secure = ()
            mail_handler = SMTPHandler(
                mailhost=(app.config['MAIL_SERVER'], app.config['MAIL_PORT']),
                fromaddr='no-reply@' + app.config['MAIL_SERVER'],
                toaddrs=app.config['ADMINS'], subject='NewsEye Investigator Failure',
                credentials=auth, secure=secure)
            mail_handler.setLevel(logging.ERROR)
            app.logger.addHandler(mail_handler)

        if not os.path.exists('logs'):
            os.mkdir('logs')
        file_handler = RotatingFileHandler('logs/investigator.log', maxBytes=10240,
                                          backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)

        app.logger.setLevel(logging.INFO)
        app.logger.info('NewsEye Investigator startup')

    return app

# This is required for the migrations to work properly
from app import models
