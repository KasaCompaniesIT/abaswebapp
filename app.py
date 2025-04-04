from flask import Flask, render_template, g
# from turbo_flask import Turbo
from datetime import datetime

app = Flask(__name__)
# turbo = Turbo(app)

app.config.from_mapping(
        SECRET_KEY='dev'
    )

# @app.before_request
# def before_request():
#     g.turbo = turbo

@app.route("/")
def home():
    return render_template("index.html")

@app.route('/manifest.json')
def manifest():
    return app.send_from_directory('static', 'manifest.json')

from . import db

from . import auth
app.register_blueprint(auth.bp)

from . import admin
app.register_blueprint(admin.bp)

from . import timesheet
app.register_blueprint(timesheet.bp)
# app.add_url_rule('/timesheet', endpoint='index')

def dateformat(value, format="%A"):
    value = value.strip()  # Remove leading and trailing whitespaces
    date_obj = datetime.strptime(value, "%m/%d/%y")
    return date_obj.strftime(format)

app.jinja_env.filters['dateformat'] = dateformat

if __name__ == "__main__":
    app.run(debug=True)
    
        