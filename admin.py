from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for
)
from werkzeug.exceptions import abort

bp = Blueprint('admin', __name__)

@bp.route('/admin')
def index():
    return render_template('admin/index.html')

@bp.route("/admin/import")
def importCSV():
    
    return render_template('admin/importCSV.html')
