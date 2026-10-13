#Student_ID_25017334_Name_Priyanshi_Jadeja
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from app.dbfunc import get_connection
from functools import wraps
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "error")
            return redirect(url_for("auth_bp.login"))
        return f(*args, **kwargs)
    return wrapper

auth_bp = Blueprint("auth_bp", __name__)


# ADMIN ACCESS DECORATOR

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        # Must be logged in AND role must be ADMIN
        if "user_id" not in session or session.get("role") != "ADMIN":
            flash("Admin access required.")
            return redirect(url_for("auth_bp.login"))
        return f(*args, **kwargs)
    return wrapper


# REGISTER

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        first = request.form.get("first_name")
        last = request.form.get("last_name")
        email = request.form.get("email")
        password = request.form.get("password")

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # Check if email already exists
        cursor.execute("SELECT * FROM user_account WHERE email = %s", (email,))
        existing = cursor.fetchone()

        if existing:
            flash("An account with this email already exists.", "error")
            cursor.close()
            conn.close()
            return redirect(url_for("auth_bp.register"))

        # Hash password
        hashed_pw = generate_password_hash(password)

        # Insert new user
        cursor.execute("""
            INSERT INTO user_account 
            (first_name, last_name, email, password_hash, role)
            VALUES (%s, %s, %s, %s, %s)
        """, (first, last, email, hashed_pw, "END_USER"))

        conn.commit()
        cursor.close()
        conn.close()

        flash("Registration successful! Please log in.", "success")
        return redirect(url_for("auth_bp.login"))

    return render_template("register.html")


# LOGIN

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":

        email = request.form.get("email")
        password = request.form.get("password")

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM user_account WHERE email = %s", (email,))
        user = cursor.fetchone()

        cursor.close()
        conn.close()

        # Invalid login
        if not user or not check_password_hash(user["password_hash"], password):
            flash("Invalid email or password.", "error")
            return redirect(url_for("auth_bp.login"))

        # Valid login -> store session
        session["user_id"] = user["user_id"]
        session["email"] = user["email"]
        session["role"] = user["role"]

        # Redirect to previous page if stored
        next_page = request.args.get("next")
        if next_page:
            return redirect(next_page)

        # Redirect based on role
        if user["role"] == "ADMIN":
            return redirect(url_for("admin_bp.dashboard"))
        else:
            return redirect(url_for("booking_bp.dashboard"))

    return render_template("login.html")


# LOGOUT

@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for("home_bp.home"))

# UPDATE PASSWORD

@auth_bp.route("/update_password", methods=["POST"])
@login_required
def update_password():
    old_pw = request.form.get("old_password")
    new_pw = request.form.get("new_password")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT password_hash FROM user_account WHERE user_id=%s", (session["user_id"],))
    user = cursor.fetchone()

    # Check old password
    if not check_password_hash(user["password_hash"], old_pw):
        flash("Old password is incorrect.", "error")
        cursor.close()
        conn.close()
        return redirect(url_for("booking_bp.dashboard"))

    # Update to new password
    new_hash = generate_password_hash(new_pw)
    cursor.execute("UPDATE user_account SET password_hash=%s WHERE user_id=%s",
                   (new_hash, session["user_id"]))
    conn.commit()

    cursor.close()
    conn.close()

    flash("Password updated successfully!", "success")
    return redirect(url_for("booking_bp.dashboard"))