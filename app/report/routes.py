from flask import request
from flask_login import login_required, current_user
from flask_restplus import Resource
from app.report import ns
from app.models import Task, Report
from app.report.report_utils import generate_report, get_formats, get_languages
from werkzeug.exceptions import NotFound


@ns.route('/<string:task_uuid>')
class ReportTask(Resource):
    @login_required
    def get(self, task_uuid):
        """
        Retrieve the report generated from the task results.
        """
        report_language = request.args.get('language', 'en')
        report_format = request.args.get('format', 'p')
        task = Task.query.filter_by(uuid=task_uuid, user_id=current_user.id).first()
        if task is None:
            raise NotFound('Task {} not found for user {}'.format(task_uuid, current_user.username))
        task_report = Report.query.filter_by(task_uuid=task_uuid, report_format=report_format, report_language=report_language).first()
        if task_report:
            return task_report.report_content
        else:
            task_report = generate_report(task, report_language, report_format)
        return task_report.report_content


@ns.route('/languages')
class LanguageList(Resource):
    @login_required
    def get(self):
        """
        Lists the languages supported by the Reporter component.
        """
        return get_languages()


@ns.route('/formats')
class FormatList(Resource):
    @login_required
    def get(self):
        """
        Lists the text formatting options supported by the Reporter component.
        """
        return get_formats()

