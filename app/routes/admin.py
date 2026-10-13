#Student_ID_25017334_Name_Priyanshi_Jadeja
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from app.dbfunc import get_connection, execute_query, fetch_one
from app.routes.auth import admin_required

admin_bp = Blueprint("admin_bp", __name__, url_prefix="/admin")

# ADMIN DASHBOARD

@admin_bp.route("/dashboard")
@admin_required
def dashboard():

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # EVENTS LIST
    cursor.execute("""
        SELECT e.*, l.name AS location_name
        FROM event e
        JOIN location l ON l.location_id = e.location_id
        ORDER BY e.event_id DESC
    """)
    events = cursor.fetchall()

    # LOCATIONS LIST
    cursor.execute("SELECT * FROM location ORDER BY name")
    locations = cursor.fetchall()

    # CATEGORIES LIST
    cursor.execute("SELECT * FROM category ORDER BY name")
    categories = cursor.fetchall()

    # OCCURRENCES LIST
    cursor.execute("""
        SELECT 
            o.*, 
            e.name AS event_name
        FROM event_occurrence o
        JOIN event e ON e.event_id = o.event_id
        ORDER BY o.occur_date
    """)
    occurrences = cursor.fetchall()

    # USERS LIST
    cursor.execute("""
        SELECT user_id, email, role 
        FROM user_account
        ORDER BY user_id DESC
    """)
    users = cursor.fetchall()

    # BOOKINGS LIST 

    cursor.execute("""
        SELECT 
            b.booking_id,
            b.status,
            b.booking_ts,
            b.total_after_discounts AS total_price,
            u.email AS user_email,
            e.name AS event_name
        FROM booking b
        JOIN user_account u ON b.user_id = u.user_id
        JOIN booking_line bl ON bl.booking_id = b.booking_id
        JOIN event_occurrence o ON o.occurrence_id = bl.occurrence_id
        JOIN event e ON e.event_id = o.event_id
        GROUP BY 
            b.booking_id,
            b.status,
            b.booking_ts,
            b.total_after_discounts,
            u.email,
            e.name
        ORDER BY b.booking_id DESC
    """)
    bookings = cursor.fetchall()

    # MONTHLY SALES

    cursor.execute("""
        SELECT 
            DATE_FORMAT(b.booking_ts, '%M') AS month,
            SUM(total_after_discounts) AS revenue,
            COUNT(booking_id) AS bookings
        FROM booking b
        WHERE b.status = 'CONFIRMED'
        GROUP BY MONTH(b.booking_ts), DATE_FORMAT(b.booking_ts, '%M')
        ORDER BY MONTH(b.booking_ts)
    """)
    monthly_sales = cursor.fetchall()

    # TOTAL REVENUE
    cursor.execute("""
        SELECT SUM(total_after_discounts) AS total_revenue
        FROM booking
        WHERE status = 'CONFIRMED'
    """)
    total_revenue = cursor.fetchone()["total_revenue"] or 0

    # TOTAL BOOKINGS
    cursor.execute("SELECT COUNT(*) AS total_bookings FROM booking")
    total_bookings = cursor.fetchone()["total_bookings"]

    # CANCELLED BOOKINGS
    cursor.execute("""
        SELECT COUNT(*) AS cancelled
        FROM booking
        WHERE status = 'CANCELLED'
    """)
    cancelled = cursor.fetchone()["cancelled"]

    # REFUNDS LIST 

    cursor.execute("""
        SELECT 
            p.payment_id,
            p.booking_id,
            p.amount,
            p.payment_ts,
            u.email,
            e.name AS event_name
        FROM payment p
        JOIN booking b ON b.booking_id = p.booking_id
        JOIN user_account u ON u.user_id = b.user_id
        JOIN booking_line bl ON bl.booking_id = b.booking_id
        JOIN event_occurrence eo ON eo.occurrence_id = bl.occurrence_id
        JOIN event e ON e.event_id = eo.event_id
        WHERE p.method = 'REFUND'
        GROUP BY 
            p.payment_id,
            p.booking_id,
            p.amount,
            p.payment_ts,
            u.email,
            e.name
        ORDER BY p.payment_ts DESC
    """)
    refunds = cursor.fetchall()

    # REFUND SUMMARY
    cursor.execute("""
    SELECT COALESCE(SUM(amount), 0) AS total_refunds
    FROM payment
    WHERE status = 'SUCCESS'
      AND method = 'REFUND'
    """)
    total_refunds = cursor.fetchone()["total_refunds"]

    # REVENUE PER EVENT

    cursor.execute("""
        SELECT 
            e.name AS event_name,
            SUM(b.total_after_discounts) AS revenue,
            COUNT(b.booking_id) AS bookings
        FROM booking b
        JOIN booking_line bl ON bl.booking_id = b.booking_id
        JOIN event_occurrence o ON o.occurrence_id = bl.occurrence_id
        JOIN event e ON e.event_id = o.event_id
        WHERE b.status = 'CONFIRMED'
        GROUP BY e.event_id, e.name
        ORDER BY revenue DESC
    """)
    revenue_per_event = cursor.fetchall()

    # WAITING LIST
    cursor.execute("""
        SELECT 
            w.waiting_id,
            u.email,
            o.occur_date,
            w.status
        FROM waiting_list w
        JOIN user_account u ON u.user_id = w.user_id
        JOIN event_occurrence o ON o.occurrence_id = w.occurrence_id
        ORDER BY w.waiting_id DESC
    """)
    waiting = cursor.fetchall()

    # TOP USERS
    cursor.execute("""
        SELECT 
            u.email,
            COUNT(b.booking_id) AS bookings,
            SUM(b.total_after_discounts) AS revenue
        FROM booking b
        JOIN user_account u ON u.user_id = b.user_id
        WHERE b.status = 'CONFIRMED'
        GROUP BY u.user_id, u.email
        ORDER BY revenue DESC
        LIMIT 10
    """)
    top_users = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "admin_dashboard.html",
        events=events,
        locations=locations,
        categories=categories,
        occurrences=occurrences,
        users=users,
        bookings=bookings,
        total_revenue=total_revenue,
        total_bookings=total_bookings,
        cancelled=cancelled,
        revenue_per_event=revenue_per_event,
        monthly_sales=monthly_sales,
        waiting=waiting,
        top_users=top_users,
        refunds=refunds,
        total_refunds=total_refunds
    )

# EVENT CRUD

@admin_bp.route("/events/add", methods=["POST"])
@admin_required
def add_event():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO event 
        (name, description, conditions, start_date, end_date, last_booking_date, location_id, base_total_price)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        request.form["name"],
        request.form["description"],
        request.form["conditions"],
        request.form["start_date"],
        request.form["end_date"],
        request.form["last_booking_date"],
        request.form["location_id"],
        request.form["base_total_price"]
    ))
    conn.commit()

    event_id = cursor.lastrowid

    # Insert categories
    for cid in request.form.getlist("category_ids"):
        cursor.execute("""
            INSERT INTO event_category (event_id, category_id)
            VALUES (%s, %s)
        """, (event_id, cid))
    conn.commit()

    cursor.close()
    conn.close()
    return redirect(url_for("admin_bp.dashboard"))
#EDIT EVENT
@admin_bp.route('/edit_event/<int:event_id>', methods=['GET', 'POST'])
@admin_required
def edit_event(event_id):

    event = fetch_one("SELECT * FROM event WHERE event_id = %s", (event_id,))
    if not event:
        flash("Event not found.", "error")
        return redirect(url_for('admin_bp.dashboard'))

    if request.method == 'POST':
        update_query = """
            UPDATE event
            SET name=%s,
                base_total_price=%s,
                start_date=%s,
                end_date=%s,
                last_booking_date=%s,
                conditions=%s
            WHERE event_id=%s
        """
        execute_query(update_query, (
            request.form.get('name'),
            request.form.get('base_total_price'),
            request.form.get('start_date'),
            request.form.get('end_date'),
            request.form.get('last_booking_date'),
            request.form.get('conditions'),
            event_id
        ))

        flash("Event updated successfully!", "success")
        return redirect(url_for('admin_bp.dashboard'))

    return render_template('admin_edit_event.html', event=event)

#DELETE EVENT
@admin_bp.route("/events/delete/<int:event_id>")
def delete_event(event_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT COUNT(*) AS cnt
        FROM booking_line bl
        JOIN event_occurrence eo ON bl.occurrence_id = eo.occurrence_id
        WHERE eo.event_id = %s
    """, (event_id,))
    row = cursor.fetchone()

    if row["cnt"] > 0:
        flash("Cannot delete event with existing bookings.", "error")
        cursor.close()
        conn.close()
        return redirect(url_for("admin_bp.dashboard"))

    
    cursor.execute("DELETE FROM event_occurrence WHERE event_id=%s", (event_id,))
    cursor.execute("DELETE FROM event WHERE event_id=%s", (event_id,))
    conn.commit()

    cursor.close()
    conn.close()
    flash("Event deleted successfully.", "success")
    return redirect(url_for("admin_bp.dashboard"))


# CATEGORY CRUD

@admin_bp.route("/categories/add", methods=["POST"])
@admin_required
def add_category():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("INSERT INTO category (name) VALUES (%s)", (request.form["name"],))
    conn.commit()

    cursor.close()
    conn.close()
    return redirect(url_for("admin_bp.dashboard"))
#EDIT 
@admin_bp.route("/categories/edit/<int:category_id>", methods=["GET", "POST"])
@admin_required
def edit_category(category_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM category WHERE category_id=%s", (category_id,))
    category = cursor.fetchone()

    if not category:
        flash("Category not found.", "error")
        return redirect(url_for('admin_bp.dashboard'))

    if request.method == "POST":
        cursor.execute("""
            UPDATE category
            SET name=%s
            WHERE category_id=%s
        """, (request.form["name"], category_id))
        conn.commit()

        cursor.close()
        conn.close()
        flash("Category updated successfully.", "success")
        return redirect(url_for('admin_bp.dashboard'))

    cursor.close()
    conn.close()
    return render_template("admin_edit_category.html", category=category)

@admin_bp.route("/categories/delete/<int:category_id>")
@admin_required
def delete_category(category_id):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("DELETE FROM category WHERE category_id = %s", (category_id,))
        conn.commit()
        flash("Category deleted successfully.", "success")
    except Exception:
        conn.rollback()
        flash("Cannot delete category that is in use.", "error")

    cursor.close()
    conn.close()
    return redirect(url_for("admin_bp.dashboard"))

# OCCURRENCE CRUD

@admin_bp.route("/occurrences/add", methods=["POST"])
@admin_required
def add_occurrence():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO event_occurrence
        (event_id, occur_date, start_time, end_time, price_per_day, capacity_override)
        VALUES (%s,%s,%s,%s,%s,%s)
    """, (
        request.form["event_id"],
        request.form["occur_date"],
        request.form["start_time"],
        request.form["end_time"],
        request.form["price_per_day"],
        request.form.get("capacity_override") or None
    ))
    conn.commit()

    cursor.close()
    conn.close()
    return redirect(url_for("admin_bp.dashboard"))

#EDIT OCCURRENCE

@admin_bp.route('/occurrences/edit/<int:occurrence_id>', methods=['GET', 'POST'])
@admin_required
def edit_occurrence(occurrence_id):

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT o.*, e.name AS event_name
        FROM event_occurrence o
        JOIN event e ON e.event_id = o.event_id
        WHERE o.occurrence_id = %s
    """, (occurrence_id,))
    occurrence = cursor.fetchone()

    if not occurrence:
        flash("Occurrence not found.", "danger")
        return redirect(url_for('admin_bp.dashboard'))

    cursor.execute("SELECT event_id, name FROM event ORDER BY name")
    events = cursor.fetchall()

    if request.method == 'POST':
        cursor.execute("""
            UPDATE event_occurrence
            SET event_id=%s, occur_date=%s, start_time=%s, end_time=%s, price_per_day=%s
            WHERE occurrence_id=%s
        """, (
            request.form["event_id"],
            request.form["occur_date"],
            request.form["start_time"],
            request.form["end_time"],
            request.form["price_per_day"],
            occurrence_id
        ))
        conn.commit()

        cursor.close()
        conn.close()
        flash("Occurrence updated successfully!", "success")
        return redirect(url_for('admin_bp.dashboard'))

    cursor.close()
    conn.close()
    return render_template("admin_edit_occurrence.html", occurrence=occurrence, events=events)

#DELETE OCCURRENCE

@admin_bp.route("/occurrences/delete/<int:occurrence_id>")
@admin_required
def delete_occurrence(occurrence_id):
    conn = get_connection()
    cursor = conn.cursor()

    try:
     cursor.execute("DELETE FROM event_occurrence WHERE occurrence_id=%s", (occurrence_id,))
     conn.commit()
     flash("Occurrence deleted successfully.", "success")
    except Exception:
     conn.rollback()
     flash("Cannot delete occurrence with existing bookings.", "error")
    
    cursor.close()
    conn.close()
    return redirect(url_for("admin_bp.dashboard"))

# LOCATION CRUD

@admin_bp.route('/locations/edit/<int:location_id>', methods=['GET', 'POST'])
@admin_required
def edit_location(location_id):

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM location WHERE location_id = %s", (location_id,))
    location = cursor.fetchone()

    if not location:
        flash("Location not found.", "danger")
        return redirect(url_for('admin_bp.dashboard'))

    if request.method == 'POST':
        cursor.execute("""
            UPDATE location
            SET name=%s, capacity=%s, address=%s
            WHERE location_id=%s
        """, (
            request.form["name"],
            request.form["capacity"],
            request.form["address"],
            location_id
        ))
        conn.commit()

        cursor.close()
        conn.close()
        flash("Location updated successfully!", "success")
        return redirect(url_for('admin_bp.dashboard'))

    cursor.close()
    conn.close()
    return render_template("admin_edit_location.html", location=location)

#ADD LOCATION

@admin_bp.route("/locations/add", methods=["POST"])
@admin_required
def add_location():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO location (name, capacity, address)
        VALUES (%s, %s, %s)
    """, (
        request.form["name"],
        request.form["capacity"],
        request.form["address"]
    ))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for("admin_bp.dashboard"))

#DELETE LOCATION

@admin_bp.route("/locations/delete/<int:location_id>")
@admin_required
def delete_location(location_id):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("DELETE FROM location WHERE location_id = %s", (location_id,))
        conn.commit()
        flash("Location deleted successfully.", "success")
    except Exception:
        conn.rollback()
        flash("Cannot delete location that is in use.", "error")

    cursor.close()
    conn.close()

    return redirect(url_for("admin_bp.dashboard"))

# USER DELETE

@admin_bp.route("/users/delete/<int:user_id>")
@admin_required
def delete_user(user_id):

    # Prevent admin from deleting themselves
    if session.get("user_id") == user_id:
        flash("You cannot delete your own admin account.", "warning")
        return redirect(url_for("admin_bp.dashboard"))

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_account WHERE user_id=%s", (user_id,))
    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for("admin_bp.dashboard"))