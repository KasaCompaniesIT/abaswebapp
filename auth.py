import functools 
import pyodbc

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash

from db import get_db

# adminpw = "scrypt:32768:8:1$EgSDoL8bO49k61nA$99d5477640b1bd8d20a2ab512e2fac45782522b5fb3e889cfe4cda94a44c2059a1d4b8fb6de4455c8b32211fd6134c473f40fa769852cc88a90acc65431bd9f5"

bp = Blueprint('auth', __name__, url_prefix='/auth')


@bp.route('/register', methods=('GET', 'POST'))
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        cursor = db.cursor()
        error = None

        if not username:
            error = 'Username is required.'
        elif not password:
            error = 'Password is required.'

        if error is None:
            try:
                cursor.execute(
                    "INSERT INTO login (username, password) VALUES (?, ?)",
                    (username, generate_password_hash(password))
                )
                cursor.commit()
            except pyodbc.DatabaseError as err:
                error = f"User {username} is already registered."
            else:
                return redirect(url_for("auth.login"))

        flash(error)
        
    return render_template('auth/register.html')


@bp.route('/login', methods=('GET', 'POST'))
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db()
        cursor = db.cursor()
        error = None
        user = cursor.execute(
            'SELECT * FROM login WHERE username = ?', (username,)
        ).fetchone()

        try:
            if username is None:
                error = 'Invalid Login.'
            elif not check_password_hash(user.password, password):
                error = 'Invalid Login.'
        except TypeError:
            error = 'Invalid Login.'

        if error is None:
            session.clear()
            session['user_id'] = user.id
            return redirect(url_for('admin.index'))

        flash(error)

    return render_template('auth/login.html')


@bp.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')

    if user_id is None:
        g.user = None
    else:
        g.user = 'admin'
        g.user = get_db().cursor().execute(
            'SELECT * FROM login WHERE id = ?', (user_id,)
        ).fetchone()


@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))


def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('auth.login'))

        return view(**kwargs)

    return wrapped_view
