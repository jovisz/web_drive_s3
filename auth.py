from flask import session, redirect, url_for
from functools import wraps
import config

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper

def authenticate(username, password):
    user = config.USERS.get(username)
    if not user:
        return False, "User not found"
    elif user['password'] != password:
        return False, "Incorrect password"

    return True, ""

def get_user_prefix(username):
    return config.USERS.get(username, {}).get('prefix', '')
