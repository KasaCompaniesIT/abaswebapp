from flask import Flask, render_template
import pymssql

# dbConn = pymssql.connect(
#         server='kasa-sql.kasa.kasacontrols.com',
#         user='abas_webapp',
#         password='Autograph-Filtrate8-Fester-Synopsis',
#         database='keserp',
#         as_dict=True
#     )

app = Flask(__name__)


@app.route("/")
def home():
    return render_template("index.html")






from . import admin
app.register_blueprint(admin.bp)

from . import timesheet
app.register_blueprint(timesheet.bp)
app.add_url_rule('/', endpoint='index')



if __name__ == "__main__":
    app.run()

        