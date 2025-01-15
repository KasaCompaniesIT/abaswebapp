from flask import Flask, render_template
import pymssql

dbConn = pymssql.connect(
        server='kasa-sql.kasa.kasacontrols.com',
        user='abas_webapp',
        password='Autograph-Filtrate8-Fester-Synopsis',
        database='keserp',
        as_dict=True
    )

var = "Hello, World!"

app = Flask(__name__)


@app.route("/")
def home():
    return render_template("home.html", data = var)

@app.route("/lookup")
def lookup():
    return render_template(lookup.html, "")

@app.route("/admin/import")
def importCSV():
    
    return render_template(importCSV.html)












if __name__ == "__main__":
    app.run()

        