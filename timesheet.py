from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for
)
from werkzeug.exceptions import abort

bp = Blueprint('timesheet', __name__)

@bp.route("/timesheet")
def lookup():
    return render_template('timesheet/index.html')