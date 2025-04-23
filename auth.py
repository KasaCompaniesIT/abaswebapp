import functools 
import pyodbc

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.exceptions import abort 
from urllib.parse import urlparse, urljoin
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
            error = 'AbasID is required.'
        elif not password:
            error = 'Password is required.'

        if error is None:
            try:
                # cursor.execute(
                #     "INSERT INTO login (username, password) VALUES (?, ?)",
                #     (username, generate_password_hash(password))
                # )
                cursor.execute(
                    "UPDATE Employee SET Password = ? WHERE EmpID = ?",
                    (generate_password_hash(password), username)
                )
                cursor.commit()
            except pyodbc.DatabaseError as err:
                error = f"AbasID {username} is invalid."
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
       
        lookupByName = False
        if not username.isdigit():
            lookupByName = True

        # Query the database to check if the username exists
        if lookupByName:
            user = cursor.execute(
                'SELECT * FROM employee WHERE TRIM(emp) = ?', (username,)
            ).fetchone()
        else:
            # Check if the username exists in the database
            user = cursor.execute(
                'SELECT * FROM employee WHERE empid = ?', (username,)
            ).fetchone()
       
        # print(user)
        if user.Password is None:
            error = 'Abas ID is not registered. Click register to create a password.'
        else:            
            if user is None or not check_password_hash(user.Password, password):
                error = 'Invalid username or password.'
            else:
                session.clear()
                session['user_id'] = user.EmpID
                next_page = request.form.get('next')  # Get the 'next' parameter from the form
                print(f"Next page: {next_page}")
                if not next_page or not is_safe_url(next_page):
                    next_page = url_for('home')  # Default to the home page
                return redirect(next_page)

        flash(error)

    next_page = request.args.get('next', '')
    return render_template('auth/login.html', next=next_page)


@bp.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')

    if user_id is None:
        g.user = None
    else:
        g.user = user_id
        g.user = get_db().cursor().execute(
            'SELECT EmpID, Emp, EmpName, Dept, Supervisor, isAdmin FROM employee WHERE empid = ?', (user_id,)
        ).fetchone()


@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))


@bp.route('/validate_username', methods=['POST'])
def validate_username():
    username = request.json.get('username')  # Get the username from the AJAX request
    db = get_db()
    cursor = db.cursor()
    lookupByName = False
    if not username.isdigit():
        lookupByName = True

    # Query the database to check if the username exists
    if lookupByName:
        user = cursor.execute(
            'SELECT * FROM employee WHERE TRIM(emp) = ?', (username,)
        ).fetchone()
    else:
        # Check if the username exists in the database
        user = cursor.execute(
            'SELECT * FROM employee WHERE empid = ?', (username,)
        ).fetchone()

    if user:
        return {'exists': True}  # Username exists
    else:
        return {'exists': False}  # Username does not exist


def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('auth.login', next=request.url))

        return view(**kwargs)

    return wrapped_view


def is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc
