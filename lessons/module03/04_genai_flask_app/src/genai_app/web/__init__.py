from flask import Blueprint

bp = Blueprint("web", __name__)

from genai_app.web import routes  # noqa: E402, F401  (registers the routes on bp)
