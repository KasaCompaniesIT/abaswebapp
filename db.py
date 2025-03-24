import pyodbc
import click
from flask import current_app, g
from config import DB_URL


def get_db():
    if 'db' not in g:        
        g.db = pyodbc.connect(DB_URL)
    return g.db


def close_db(e=None):
    db = g.pop('db', None)

    if db is not None:
        db.close()
