"""
database.py - Database connection helper for Flask
This file handles all SQLite connections and provides helper functions.
"""

import sqlite3
from flask import g

# Database file location (same folder as main.py)
DATABASE = 'rehab_coach.db'


def get_db():
    """
    Get database connection for the current request.
    
    Uses Flask's 'g' object to store the connection.
    The same connection is reused throughout a single request.
    
    Returns:
        sqlite3.Connection: Database connection object
    """
    if 'db' not in g:
        # Create new connection
        g.db = sqlite3.connect(DATABASE)
        # Return rows as dictionaries (access by column name like row['email'])
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    """
    Close database connection at the end of request.
    This is automatically called by Flask via teardown_appcontext.
    
    Args:
        e: Exception (if any) that caused the teardown
    """
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db(app):
    """
    Initialize the database with schema.sql.
    Only run this once to create tables!
    
    Args:
        app: Flask application instance
    """
    with app.app_context():
        db = get_db()
        with app.open_resource('schema.sql', mode='r') as f:
            db.executescript(f.read())
        db.commit()
        print("✅ Database initialized successfully!")


def query_db(query, args=(), one=False):
    """
    Execute a SELECT query and return results.
    
    Args:
        query: SQL query string with ? placeholders
        args: Tuple of values to substitute for ?
        one: If True, return only first row; if False, return all rows
    
    Returns:
        Single row (dict-like) if one=True, or list of rows if one=False
        Returns None if no results and one=True
    
    Example:
        # Get single user
        user = query_db('SELECT * FROM users WHERE id = ?', (user_id,), one=True)
        
        # Get all patients
        patients = query_db('SELECT * FROM patients')
    """
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv


def execute_db(query, args=()):
    """
    Execute an INSERT, UPDATE, or DELETE query.
    Automatically commits the transaction.
    
    Args:
        query: SQL query string with ? placeholders
        args: Tuple of values to substitute for ?
    
    Returns:
        int: The lastrowid (useful for getting ID of inserted row)
    
    Example:
        # Insert new user and get their ID
        new_id = execute_db(
            'INSERT INTO users (email, password, name, role) VALUES (?, ?, ?, ?)',
            (email, hashed_pw, name, role)
        )
    """
    db = get_db()
    cursor = db.execute(query, args)
    db.commit()
    return cursor.lastrowid
