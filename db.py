import pyodbc

import click
from flask import current_app, g


def get_db():
    if 'db' not in g:
        # g.db = pyodbc.connect('DRIVER={ODBC Driver 18 for SQL Server};SERVER=kasa-sql.kasa.kasacontrols.com;DATABASE=keserp;UID=abas_webapp;PWD=Autograph-Filtrate8-Fester-Synopsis;Encrypt=no;')        
        g.db = pyodbc.connect('DRIVER={SQL Server};SERVER=kasa-sql.kasa.kasacontrols.com;DATABASE=keserp;UID=abas_webapp;PWD=Autograph-Filtrate8-Fester-Synopsis;Encrypt=no;')

    return g.db


def close_db(e=None):
    db = g.pop('db', None)

    if db is not None:
        db.close()

def importCSVData():
    file = ''


# def init_db():
#     db = get_db()

#     with current_app.open_resource('schema.sql') as f:
#         db.executescript(f.read().decode('utf8'))

# @click.command('init-db')
# def init_db_command():
#     """Clear the existing data and create new tables."""
#     init_db()
#     click.echo('Initialized the database.')

# def init_app(app):
#     app.teardown_appcontext(close_db)
#     app.cli.add_command(init_db_command)