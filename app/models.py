from datetime import datetime
from werkzeug.http import http_date
from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidSignatureError
from flask import current_app
from flask_login import UserMixin
from app import db, login
from config import Config


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True)
    created_on = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    all_tasks = db.relationship('TaskInstance', back_populates='user', lazy='dynamic', foreign_keys="TaskInstance.user_id")

    def __repr__(self):
        return '<User {}>'.format(self.username)


class Result(db.Model):
    __tablename__ = 'results'
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'))
    task = db.relationship('Task', back_populates='task_results', foreign_keys=[task_id])
    result = db.Column(db.JSON)
    interestingness = db.Column(db.JSON)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)
    # __table_args__ = (UniqueConstraint('task_type', 'task_parameters', name='uq_results_task_type_task_parameters'),)

    result_reports = db.relationship('Report', back_populates='result', foreign_keys='Report.result_id')
    
    def __repr__(self):
        return '<Result id: {} task: {} date: {}>'.format(self.id, self.task_id, self.last_updated)


class Report(db.Model):
    __tablename__ = 'reports'
    id = db.Column(db.Integer, primary_key=True)

    result_id = db.Column(db.Integer, db.ForeignKey('results.id'))
    result = db.relationship('Result', back_populates='result_reports', foreign_keys=[result_id])

    report_language = db.Column(db.String(255))
    report_format = db.Column(db.String(255))
    report_content = db.Column(db.JSON)
    report_generated = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return '<Report>'


class Task(db.Model):
    __tablename__ = 'tasks'
    id = db.Column(db.Integer, primary_key=True)
    # search/analysis
    task_type = db.Column(db.String(255), nullable=False)
    utility_name = db.Column(db.String(255))
    search_query = db.Column(JSONB, nullable=False)
    utility_parameters = db.Column(JSONB)
    
    __table_args__ = (UniqueConstraint('task_type', 'utility_name', 'search_query', 'utility_parameters', name='uq_task_type_task_parameters'),)
    
    # result_id = db.Column(db.Integer, db.ForeignKey('results.id', ondelete='CASCADE'))
    task_results = db.relationship('Result', back_populates='task', foreign_keys="Result.task_id")
    task_instances = db.relationship('TaskInstance', back_populates='task', foreign_keys="TaskInstance.task_id")
    
    input_type = db.Column(db.String(255))
    output_type = db.Column(db.String(255))

    @property
    def task_result(self):
        if self.task_results:
            return sorted(self.task_results, key=lambda r: r.last_updated)[-1]        
        
    def __repr__(self):
        return '<Task id: {} type: {} utlity: {} search: {} parameters: {}>'.format(self.id, self.task_type, self.utility_name, self.search_query, self.utility_parameters)


class TaskInstance(db.Model):
    __tablename__ = "task_instances"
    id = db.Column(db.Integer, primary_key=True)
    
    # external id
    uuid = db.Column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'))
    task = db.relationship('Task', back_populates='task_instances', foreign_keys=[task_id])
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    user = db.relationship('User', back_populates='all_tasks', foreign_keys=[user_id])

    # search history of a user
    # currently not used
    # to make top-level relations between tasks
    hist_parent_id = db.Column(UUID(as_uuid=True), db.ForeignKey('task_instances.uuid'))
    # shortcuts for searching children given parents
    hist_children = db.relationship('TaskInstance', primaryjoin="TaskInstance.uuid==TaskInstance.hist_parent_id")

    # force refresh: if True executes analysis utility once again, if False tries to find result from DB
    force_refresh = db.Column(db.Boolean)

    # parent task
    source_uuid = db.Column(UUID(as_uuid=True), db.ForeignKey('task_instances.uuid'))
    # created/running/finished/failed
    task_status = db.Column(db.String(255))
    
    # timestamps
    task_started  = db.Column(db.DateTime, default=datetime.utcnow)
    task_finished = db.Column(db.DateTime)
    last_accessed = db.Column(db.DateTime, default=datetime.utcnow)

    # result: keeps result for a current user even if result in Task table already updated
    result_id = db.Column(db.Integer, db.ForeignKey('results.id'))   
    
    @property
    def task_type(self):
        return self.task.task_type

    @property
    def utility_parameters(self):
        return self.task.utility_parameters

    @property
    def utility(self):
        return self.task.utility_name

    @property
    def input_type(self):
        return self.task.input_type
    
    @property
    def output_type(self):
        return self.task.output_type
    
    @property
    def search_query(self):
        return self.task.search_query

    @search_query.setter
    def search_query(self, query):
        self.task.search_query = query
    
    @property
    def task_parameters(self):
        if self.task_type == "search":
            return self.task.search_query
        else:
            return {"utility":self.task.utility_name,
                    "search_query":self.task.search_query,
                    "utility_parameters":self.task.utility_parameters}
        
    @property
    def task_result(self):
        if self.result_id:
            return next((result for result in self.task.task_results if result.id == self.result_id), None)
        else:
            the_most_recent_result = self.task.task_result
            if the_most_recent_result:
                if not self.force_refresh:
                    self.result_id = the_most_recent_result.id
                return the_most_recent_result

    @property
    def task_report(self):
        result = self.task_result
        if result:
            reports = result.result_reports
            if reports:
                return sorted(reports, key=lambda r: r.report_generated)[-1]

    @property
    def result_with_interestingness(self):
        if self.task_result:
            return {'result' : self.task_result.result,
                    'interestingness' : self.task_result.interestingness}
        
    # different versions of the output
    def dict(self, style='status'):
        if style == 'status':
            return {
                'uuid': str(self.uuid),
                'task_type': self.task_type,
                'task_parameters': self.task_parameters,
                'task_status': self.task_status,
                'task_started': http_date(self.task_started),
                'task_finished': http_date(self.task_finished),
            }
        elif style == 'result':
            return {
                'uuid': str(self.uuid),
                'task_type': self.task_type,
                'task_parameters': self.task_parameters,
                'task_status': self.task_status,
                'task_started': http_date(self.task_started),
                'task_finished': http_date(self.task_finished),
                'task_result': self.result_with_interestingness
            }
        elif style == 'search_result':
            return {
                'uuid': str(self.uuid),
                'task_type': self.task_type,
                'task_parameters': self.task_parameters,
                'task_status': self.task_status,
                'task_started': http_date(self.task_started),
                'task_finished': http_date(self.task_finished),
                'task_result': self.task_result.result
            }

        elif style == 'full':
            return {
                'uuid': str(self.uuid),
                'task_type': self.task_type,
                'task_parameters': self.task_parameters,
                'task_status': self.task_status,
                'task_result':  self.result_with_interestingness,
                'hist_parent_id': self.hist_parent_id,
                'task_started': http_date(self.task_started),
                'task_finished': http_date(self.task_finished),
                'last_accessed': http_date(self.last_accessed),
            }
        elif style == 'reporter':
            return {
                'uuid': str(self.uuid),
                'task_type': self.task_type,
                'task_parameters': self.task_parameters,
                'task_status': self.task_status,
                'task_result': self.result_with_interestingness if self.task_result else None,
                'hist_parent_id': str(self.hist_parent_id),
                'task_started': http_date(self.task_started),
                'task_finished': http_date(self.task_finished),
                'last_accessed': http_date(self.last_accessed),
            }
        else:
            raise KeyError('''Unknown value for parameter 'style'! Valid options: status, result, full. ''')

    
        
    def __repr__(self):
        return '<TaskInstance {}: {}, {}>'.format(self.uuid, self.task_id, self.user_id)


# Needed by flask_login
@login.user_loader
def load_user(id):
    return User.query.get(int(id))


# User login using a Bearer Token, if it exists
@login.request_loader
def load_user_from_request(request):
    token = request.headers.get('Authorization')
    if token is None:
        return None
    if token[:4] == 'JWT ':
        token = token.replace('JWT ', '', 1)
        try:
            decoded = jwt.decode(token, Config.SECRET_KEY, algorithm='HS256')
        except (ExpiredSignatureError, InvalidSignatureError):
            return None
        user = User.query.filter_by(username=decoded['username']).first()
        if not user:
            user = User(username=decoded['username'])
            db.session.add(user)
            current_app.logger.info("Added new user '{}' to the database".format(user.username))
        else:
            user.last_seen = datetime.utcnow()
        db.session.commit()
        return user
    return None
