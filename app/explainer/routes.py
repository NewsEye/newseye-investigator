from flask_login import login_required, current_user
from flask_restplus import Resource
from app.auth import AuthParser
from app.explainer import ns
from app.explainer.explainer_utils import make_explanation, get_formats, get_languages

from flask import current_app


@ns.route("/explain")
class Explain(Resource):
    parser = AuthParser()
    parser.add_argument(
        "language",
        default="en",
        help="The language the explanation should be written in.",
    )
    parser.add_argument(
        "format", default="ul", help="The format of the body of the explanation."
    )
    parser.add_argument("run", help="run uuid")

    @login_required
    @ns.expect(parser)
    def get(self):
        """
        Retrieve an explanation generated from the task results.
        """
        args = self.parser.parse_args()
        current_app.logger.debug("ARGS: %s" % args)
        explanation = make_explanation(args)
        current_app.logger.debug("EXPLANATION: %s" % explanation)
        return explanation


@ns.route("/languages")
class LanguageList(Resource):
    @login_required
    @ns.expect(AuthParser())
    def get(self):
        """
        List the languages supported by the Explainer component.
        """
        return get_languages()


@ns.route("/formats")
class FormatList(Resource):
    @login_required
    @ns.expect(AuthParser())
    def get(self):
        """
        List the text formatting options supported by the Explainer component.
        """
        return get_formats()