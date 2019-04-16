from datetime import datetime
from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
from flask_login import UserMixin
from app import db, login


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True)
    created_on = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    all_tasks = db.relationship('Task', back_populates='user', lazy='dynamic', foreign_keys="Task.user_id")

    def __repr__(self):
        return '<User {}>'.format(self.username)


class Result(db.Model):
    __tablename__ = 'results'
    id = db.Column(db.Integer, primary_key=True)
    task_type = db.Column(db.String(255), nullable=False)
    task_parameters = db.Column(JSONB, nullable=False)
    result = db.Column(db.JSON)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint('task_type', 'task_parameters', name='uq_results_task_type_task_parameters'),)

    def __repr__(self):
        return '<Result {}: {}>'.format(self.task_type, self.task_parameters)


class Report(db.Model):
    __tablename__ = 'reports'
    id = db.Column(db.Integer, primary_key=True)
    task_uuid = db.Column(UUID(as_uuid=True), db.ForeignKey('tasks.uuid'))
    report_language = db.Column(db.String(255))
    report_format = db.Column(db.String(255))
    report_content = db.Column(db.JSON)
    report_generated = db.Column(db.DateTime, default=datetime.utcnow)
    task = db.relationship('Task', back_populates='task_reports', foreign_keys=[task_uuid])

    def __repr__(self):
        return '<Report>'


class Task(db.Model):
    __tablename__ = 'tasks'
    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    hist_parent_id = db.Column(UUID(as_uuid=True), db.ForeignKey('tasks.uuid'))
    task_type = db.Column(db.String(255), nullable=False)
    task_parameters = db.Column(JSONB, nullable=False)
    task_status = db.Column(db.String(255))
    task_started = db.Column(db.DateTime, default=datetime.utcnow)
    task_finished = db.Column(db.DateTime, default=datetime.utcnow)
    last_accessed = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', back_populates='all_tasks', foreign_keys=[user_id])
    hist_children = db.relationship('Task', primaryjoin="Task.uuid==Task.hist_parent_id")
    task_result = db.relationship('Result', primaryjoin="and_(foreign(Task.task_type)==Result.task_type, foreign(Task.task_parameters)==Result.task_parameters)")
    task_reports = db.relationship('Report', back_populates='task', foreign_keys="Report.task_uuid")

    def dict(self, style='status'):
        if style == 'status':
            return {
                'uuid': self.uuid,
                'task_type': self.task_type,
                'task_parameters': self.task_parameters,
                'task_status': self.task_status,
                'task_started': self.task_started,
                'task_finished': self.task_finished,
            }
        elif style == 'result':
            return {
                'uuid': self.uuid,
                'task_type': self.task_type,
                'task_parameters': self.task_parameters,
                'task_status': self.task_status,
                'task_started': self.task_started,
                'task_finished': self.task_finished,
                'task_result': self.task_result.result if self.task_result else None,
            }
        elif style == 'full':
            return {
                'uuid': self.uuid,
                'task_type': self.task_type,
                'task_parameters': self.task_parameters,
                'task_status': self.task_status,
                'task_result': self.task_result.result if self.task_result else None,
                'hist_parent_id': self.hist_parent_id,
                'task_started': self.task_started,
                'task_finished': self.task_finished,
                'last_accessed': self.last_accessed,
            }
        else:
            raise KeyError('''Unknown value for parameter 'style'! Valid options: status, result, full. ''')

    def __repr__(self):
        return '<Task {}: {}>'.format(self.task_type, self.task_parameters)


# Needed by flask_login
@login.user_loader
def load_user(id):
    return User.query.get(int(id))


# User login using a Bearer Token, if it exists
@login.request_loader
def load_user_from_request(request):
    username = request.headers.get('Authorization')
    if username:
        username = username.replace('Bearer ', '', 1)
        user = User.query.filter_by(username=username).first()
        return user
    return None
