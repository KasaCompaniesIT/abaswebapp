from flask import Flask, render_template

app = Flask(__name__)

app.config.from_mapping(
        SECRET_KEY='dev'
    )

@app.route("/")
def home():
    return render_template("index.html")

from . import db

from . import auth
app.register_blueprint(auth.bp)

from . import admin
app.register_blueprint(admin.bp)

from . import timesheet
app.register_blueprint(timesheet.bp)
# app.add_url_rule('/timesheet', endpoint='index')

if __name__ == "__main__":
    app.run(debug=True)
    
        