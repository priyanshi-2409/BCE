#Student_ID_25017334_Name_Priyanshi_Jadeja

from flask import (
    Blueprint, render_template, session, redirect,
    url_for, request, flash, abort, make_response
)
from app.dbfunc import get_connection, fetch_one, execute_query
from datetime import date, datetime, timedelta
from decimal import Decimal

booking_bp = Blueprint("booking_bp", __name__, url_prefix="")

# HELPER FUNCTIONS

def fetch_all(query, params=None):
    conn = get_connection()
    if not conn:
        return []
    cursor = conn.cursor(dictionary=True)
    cursor.execute(query, params)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


# USER DASHBOARD
@booking_bp.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        session["next"] = request.url
        return redirect(url_for("auth_bp.login"))

    user_id = session["user_id"]

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # Dropdown events
    cursor.execute("""
        SELECT event_id, name 
        FROM event
        WHERE is_active = TRUE
        ORDER BY name
    """)
    all_events = cursor.fetchall()

    # Dropdown dates
    cursor.execute("""
        SELECT DISTINCT occur_date
        FROM event_occurrence
        ORDER BY occur_date
    """)
    all_dates = cursor.fetchall()

    # User bookings
    cursor.execute("""
        SELECT DISTINCT
            b.booking_id,
            b.status,
            b.total_after_discounts AS total_price,
            b.booking_ts,
            e.name AS event_name
        FROM booking b
        JOIN booking_line bl ON bl.booking_id = b.booking_id
        JOIN event_occurrence o ON o.occurrence_id = bl.occurrence_id
        JOIN event e ON e.event_id = o.event_id
        WHERE b.user_id = %s
        ORDER BY b.booking_id DESC
    """, (user_id,))
    bookings = cursor.fetchall()

    # Booking lines
    cursor.execute("""
        SELECT 
            bl.booking_id,
            bl.qty,
            bl.unit_price,
            o.occur_date,
            o.start_time,
            o.end_time
        FROM booking_line bl
        JOIN event_occurrence o ON o.occurrence_id = bl.occurrence_id
        WHERE bl.booking_id IN (
            SELECT booking_id FROM booking WHERE user_id=%s
        )
        ORDER BY o.occur_date
    """, (user_id,))
    lines = cursor.fetchall()

    # FETCH WAITING LIST OFFERS FOR THIS USER
    cursor.execute("""
        SELECT 
            wl.waiting_id,
            eo.occur_date,
            e.name AS event_name
        FROM waiting_list wl
        JOIN event_occurrence eo ON eo.occurrence_id = wl.occurrence_id
        JOIN event e ON e.event_id = eo.event_id
        WHERE wl.user_id = %s
        AND wl.status = 'OFFERED'
        ORDER BY wl.request_ts ASC
    """, (user_id,))
    offers = cursor.fetchall()

    cursor.close()
    conn.close()

    # Group lines by booking_id
    booking_days = {}
    for line in lines:
        booking_days.setdefault(line["booking_id"], []).append(line)

    return render_template(
        "user_dashboard.html",
        bookings=bookings,
        booking_days=booking_days,
        all_events=all_events,
        all_dates=all_dates,
        offers=offers   
    )
#WAITING_LIST
@booking_bp.route("/waiting_offer/<int:waiting_id>")
def waiting_offer(waiting_id):

    if "user_id" not in session:
        session["next"] = request.url
        return redirect(url_for("auth_bp.login"))

    user_id = session["user_id"]

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch waiting list entry
    cursor.execute("""
        SELECT wl.waiting_id, wl.user_id, wl.occurrence_id,
               eo.event_id
        FROM waiting_list wl
        JOIN event_occurrence eo ON eo.occurrence_id = wl.occurrence_id
        WHERE wl.waiting_id = %s AND wl.status = 'OFFERED'
    """, (waiting_id,))
    wl = cursor.fetchone()

    if not wl or wl["user_id"] != user_id:
        cursor.close()
        conn.close()
        abort(403)

    # Remove from waiting list
    cursor.execute("DELETE FROM waiting_list WHERE waiting_id = %s", (waiting_id,))
    conn.commit()

    cursor.close()
    conn.close()

    # Redirect user to select days for that event
    return redirect(url_for("booking_bp.select_days", event_id=wl["event_id"]))
#join waiting list 
@booking_bp.route("/join_waiting_list/<int:occurrence_id>")
def join_waiting_list(occurrence_id):

    if "user_id" not in session:
        session["next"] = request.url
        return redirect(url_for("auth_bp.login"))

    user_id = session["user_id"]

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # Check if user already in waiting list for this occurrence
    cursor.execute("""
        SELECT waiting_id 
        FROM waiting_list
        WHERE user_id = %s AND occurrence_id = %s
    """, (user_id, occurrence_id))
    existing = cursor.fetchone()

    if existing:
        cursor.close()
        conn.close()
        flash("You are already on the waiting list for this date.", "info")
        return redirect(url_for("booking_bp.dashboard"))

    # Insert new waiting list entry
    cursor.execute("""
        INSERT INTO waiting_list (user_id, occurrence_id, status, request_ts)
        VALUES (%s, %s, 'WAITING', NOW())
    """, (user_id, occurrence_id))
    conn.commit()

    cursor.close()
    conn.close()

    flash("You have been added to the waiting list.", "success")
    return redirect(url_for("booking_bp.dashboard"))

#SELECT DAYS
@booking_bp.route("/select_days/<int:event_id>", methods=["GET", "POST"])
def select_days(event_id):

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch event
    cursor.execute("SELECT * FROM event WHERE event_id=%s", (event_id,))
    event = cursor.fetchone()
    if not event:
        cursor.close()
        conn.close()
        abort(404)

    # Fetch venue capacity
    cursor.execute(
        "SELECT capacity FROM location WHERE location_id=%s",
        (event["location_id"],)
    )
    location = cursor.fetchone()

    # Fetch occurrences + remaining tickets
    cursor.execute("""
        SELECT 
            o.*,
            (
                COALESCE(o.capacity_override, %(cap)s)
                -
                COALESCE((
                    SELECT SUM(bl.qty)
                    FROM booking_line bl
                    JOIN booking b ON b.booking_id = bl.booking_id
                    WHERE bl.occurrence_id = o.occurrence_id
                    AND b.status = 'CONFIRMED'
                ), 0)
            ) AS remaining_tickets
        FROM event_occurrence o
        WHERE o.event_id = %(event_id)s
        ORDER BY o.occur_date
    """, {
        "cap": location["capacity"],
        "event_id": event_id
    })
    occurrences = cursor.fetchall()

    cursor.close()
    conn.close()

    # POST: Validate booking input
    
    if request.method == "POST":
        selected_days = []
        error = None

        # 2‑month booking rule
        today = datetime.today().date()
        max_booking_date = today + timedelta(days=60)

        for occ in occurrences:
            field = f"qty_{occ['occurrence_id']}"
            qty_raw = request.form.get(field)

            if not qty_raw:
                continue

            # Validate integer
            try:
                qty = int(qty_raw)
            except ValueError:
                error = "Quantities must be whole numbers."
                break

            # Validate non-negative
            if qty < 0:
                error = "Quantities cannot be negative."
                break

            # Validate capacity
            if qty > occ["remaining_tickets"]:
                error = f"Only {occ['remaining_tickets']} tickets left for {occ['occur_date']}."
                break

            # Validate 2‑month rule
            occ_date = occ["occur_date"]
            if occ_date > max_booking_date:
                error = (
                    f"Bookings for {occ_date} are too far in advance. "
                    f"You can only book up to {max_booking_date}."
                )
                break

            # Add selected day
            if qty > 0:
                selected_days.append({
                    "occurrence_id": occ["occurrence_id"],
                    "qty": qty,
                    "price": float(occ["price_per_day"])
                })

        # Handle errors
        if error:
            return render_template(
                "booking_select_days.html",
                event=event,
                occurrences=occurrences,
                error=error
            )

        if not selected_days:
            return render_template(
                "booking_select_days.html",
                event=event,
                occurrences=occurrences,
                error="Please select at least one day."
            )

        # Student checkbox
        is_student = request.form.get("is_student") == "on"

        # Save booking selection
        session["booking_selection"] = {
            "event_id": event_id,
            "days": selected_days,
            "is_student": is_student
        }

        return redirect(url_for("booking_bp.booking_confirm"))

    # GET: Render page
    return render_template(
        "booking_select_days.html",
        event=event,
        occurrences=occurrences
    )

# CONFIRM BOOKING
@booking_bp.route("/confirm_booking", methods=["GET", "POST"])
def booking_confirm():

    selection = session.get("booking_selection")
    if not selection:
        flash("No booking selection found.", "error")
        return redirect(url_for("home_bp.home"))

    # Student flag (POST overrides session)
    if request.method == "POST":
        is_student = request.form.get("is_student") == "on"
    else:
        is_student = selection.get("is_student", False)

    event_id = selection["event_id"]
    days = selection["days"]

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch event
    cursor.execute("""
        SELECT event_id, name, base_total_price
        FROM event
        WHERE event_id = %s
    """, (event_id,))
    event = cursor.fetchone()

    # Fetch occurrences
    occ_ids = [d["occurrence_id"] for d in days]
    placeholders = ",".join(["%s"] * len(occ_ids))

    cursor.execute(f"""
        SELECT 
            occurrence_id,
            occur_date,
            start_time,
            end_time,
            price_per_day
        FROM event_occurrence
        WHERE occurrence_id IN ({placeholders})
    """, occ_ids)
    occurrences = cursor.fetchall()

    cursor.close()
    conn.close()

    # Build line items
    lines = []
    subtotal = 0

    for d in days:
        occ = next(o for o in occurrences if o["occurrence_id"] == d["occurrence_id"])
        qty = d["qty"]
        price = d["price"]
        line_total = qty * price
        subtotal += line_total

        lines.append({
            "occur_date": occ["occur_date"],
            "start_time": occ["start_time"],
            "end_time": occ["end_time"],
            "qty": qty,
            "unit_price": price,
            "line_total": line_total
        })

    # BCE ADVANCE BOOKING DISCOUNT
    # Use earliest selected date
    earliest_date = min([l["occur_date"] for l in lines])
    days_in_advance = (earliest_date - datetime.today().date()).days

    advance_discount = 0

    if 50 <= days_in_advance <= 60:
        advance_discount = subtotal * 0.20
    elif 35 <= days_in_advance < 50:
        advance_discount = subtotal * 0.15
    elif 25 <= days_in_advance < 35:
        advance_discount = subtotal * 0.10
    elif 15 <= days_in_advance < 25:
        advance_discount = subtotal * 0.05
    else:
        advance_discount = 0

    # STUDENT DISCOUNT (10%)
    student_discount = subtotal * 0.10 if is_student else 0.0

    # Total discount
    discount = advance_discount + student_discount
    final_total = subtotal - discount

    # Save snapshot
    session["booking_confirmed"] = {
        "event_id": event_id,
        "days": days,
        "subtotal": subtotal,
        "discount": discount,
        "final_total": final_total,
        "is_student": is_student
    }

    return render_template(
        "booking_confirm.html",
        event=event,
        lines=lines,
        subtotal=subtotal,
        discount=discount,
        final_total=final_total,
        is_student=is_student,
        advance_discount=advance_discount,
        student_discount=student_discount,
        days_in_advance=days_in_advance
    )

# COMPLETE BOOKING
@booking_bp.route("/booking/complete")
def booking_complete():

    # User must be logged in
    if "user_id" not in session:
        session["next"] = request.url
        return redirect(url_for("auth_bp.login"))

    # Retrieve booking data from session
    data = session.get("booking_confirmed")
    if not data:
        flash("No booking data found.", "error")
        return redirect(url_for("home_bp.home"))

    user_id = session["user_id"]
    event_id = data["event_id"]
    days = data["days"]
    subtotal = data["subtotal"]
    discount = data["discount"]
    final_total = data["final_total"]
    is_student = data.get("is_student", False)

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # Re-check availability
    for d in days:
        cursor.execute("""
            SELECT 
                o.occurrence_id,
                o.occur_date,
                (
                    COALESCE(o.capacity_override, l.capacity)
                    -
                    COALESCE((
                        SELECT SUM(bl.qty)
                        FROM booking_line bl
                        JOIN booking b ON b.booking_id = bl.booking_id
                        WHERE bl.occurrence_id = o.occurrence_id
                        AND b.status = 'CONFIRMED'
                    ), 0)
                ) AS remaining_tickets
            FROM event_occurrence o
            JOIN event e ON e.event_id = o.event_id
            JOIN location l ON l.location_id = e.location_id
            WHERE o.occurrence_id = %s
        """, (d["occurrence_id"],))
        occ_check = cursor.fetchone()

        if not occ_check or d["qty"] > occ_check["remaining_tickets"]:
            cursor.close()
            conn.close()
            flash("Tickets sold out while booking. Try again.")
            return redirect(url_for("booking_bp.select_days", event_id=event_id))

    # Insert booking
    cursor.execute("""
        INSERT INTO booking (
            user_id,
            booking_ts,
            status,
            student_flag_snapshot,
            total_before_discounts,
            total_discount,
            total_after_discounts
        )
        VALUES (%s, NOW(), 'PENDING_PAYMENT', %s, %s, %s, %s)
    """, (
        user_id,
        is_student,
        subtotal,
        discount,
        final_total
    ))
    conn.commit()

    booking_id = cursor.lastrowid

    # Insert booking lines
    for d in days:
        line_subtotal = d["qty"] * d["price"]

        cursor.execute("""
            INSERT INTO booking_line
            (booking_id, occurrence_id, qty, unit_price,
             line_subtotal, line_discount, line_total)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            booking_id,
            d["occurrence_id"],
            d["qty"],
            d["price"],
            line_subtotal,
            0,
            line_subtotal
        ))

    conn.commit()

    cursor.close()
    conn.close()

    # Clear session
    session.pop("booking_selection", None)
    session.pop("booking_confirmed", None)

    return redirect(url_for("booking_bp.payment_page", booking_id=booking_id))

# PAYMENT PAGE

@booking_bp.route("/payment/<int:booking_id>")
def payment_page(booking_id):

    booking = fetch_one(
        "SELECT total_after_discounts, status FROM booking WHERE booking_id = %s",
        (booking_id,)
    )
    if not booking:
        abort(404)

    if booking["status"] == "CONFIRMED":
        flash("This booking is already paid.", "error")
        return redirect(url_for("booking_bp.receipt", booking_id=booking_id))

    return render_template(
        "payment.html",
        booking_id=booking_id,
        amount=booking["total_after_discounts"]
    )

# PAYMENT PROCESS

@booking_bp.route("/payment_process/<int:booking_id>", methods=["POST"])
def payment_process(booking_id):

    required = ["card_name", "card_number", "expiry", "cvv", "billing_email"]
    if not all(request.form.get(f) for f in required):
        flash("All fields are required.", "error")
        return redirect(url_for("booking_bp.payment_page", booking_id=booking_id))

    booking = fetch_one(
        "SELECT total_after_discounts, status FROM booking WHERE booking_id = %s",
        (booking_id,)
    )
    if not booking:
        abort(404)

    if booking["status"] == "CONFIRMED":
        flash("This booking is already paid.", "error")
        return redirect(url_for("booking_bp.receipt", booking_id=booking_id))

    amount = booking["total_after_discounts"]

    # Insert payment
    execute_query("""
        INSERT INTO payment (booking_id, method, status, amount, provider_ref)
        VALUES (%s, 'CARD', 'SUCCESS', %s, 'SIMULATED_REF')
    """, (booking_id, amount))

    # Update booking status
    execute_query(
        "UPDATE booking SET status = 'CONFIRMED' WHERE booking_id = %s",
        (booking_id,)
    )
    flash("Payment successful!", "success")
    return redirect(url_for("booking_bp.receipt", booking_id=booking_id))

# RECEIPT VIEW

@booking_bp.route("/receipt/<int:booking_id>")
def receipt(booking_id):

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            b.booking_id,
            b.booking_ts,
            b.status,
            b.total_before_discounts,
            b.total_discount,
            b.total_after_discounts,
            u.email,
            e.name AS event_name,
            l.name AS location_name
        FROM booking b
        JOIN user_account u ON u.user_id = b.user_id
        JOIN booking_line bl ON bl.booking_id = b.booking_id
        JOIN event_occurrence eo ON eo.occurrence_id = bl.occurrence_id
        JOIN event e ON e.event_id = eo.event_id
        JOIN location l ON l.location_id = e.location_id
        WHERE b.booking_id = %s
        LIMIT 1
    """, (booking_id,))
    booking = cursor.fetchone()

    if not booking:
        cursor.close()
        conn.close()
        abort(404)

    cursor.execute("""
        SELECT 
            eo.occur_date,
            eo.start_time,
            eo.end_time,
            bl.qty,
            bl.unit_price,
            bl.line_total
        FROM booking_line bl
        JOIN event_occurrence eo ON eo.occurrence_id = bl.occurrence_id
        WHERE bl.booking_id = %s
        ORDER BY eo.occur_date
    """, (booking_id,))
    lines = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("receipt.html", booking=booking, lines=lines)

# RECEIPT DOWNLOAD

@booking_bp.route("/download_receipt/<int:booking_id>")
def download_receipt(booking_id):

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            b.booking_id,
            b.booking_ts,
            b.status,
            b.total_before_discounts,
            b.total_discount,
            b.total_after_discounts,
            u.email,
            e.name AS event_name,
            l.name AS location_name
        FROM booking b
        JOIN user_account u ON u.user_id = b.user_id
        JOIN booking_line bl ON bl.booking_id = b.booking_id
        JOIN event_occurrence eo ON eo.occurrence_id = bl.occurrence_id
        JOIN event e ON e.event_id = eo.event_id
        JOIN location l ON l.location_id = e.location_id
        WHERE b.booking_id = %s
        LIMIT 1
    """, (booking_id,))
    booking = cursor.fetchone()

    if not booking:
        cursor.close()
        conn.close()
        abort(404)

    cursor.execute("""
        SELECT 
            eo.occur_date,
            eo.start_time,
            eo.end_time,
            bl.qty,
            bl.unit_price,
            bl.line_total
        FROM booking_line bl
        JOIN event_occurrence eo ON eo.occurrence_id = bl.occurrence_id
        WHERE bl.booking_id = %s
        ORDER BY eo.occur_date
    """, (booking_id,))
    lines = cursor.fetchall()

    cursor.close()
    conn.close()

    html = render_template("receipt_download.html", booking=booking, lines=lines)

    response = make_response(html)
    response.headers["Content-Disposition"] = f"attachment; filename=receipt_{booking_id}.html"
    return response

# CANCEL BOOKING
@booking_bp.route("/cancel/<int:booking_id>", methods=["GET", "POST"])
def cancel_booking(booking_id):

    if "user_id" not in session:
        session["next"] = request.url
        return redirect(url_for("auth_bp.login"))

    user_id = session["user_id"]
    role = session.get("role")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch booking + earliest event date
    cursor.execute("""
        SELECT 
            b.booking_id,
            b.user_id,
            b.status,
            b.total_after_discounts,
            e.name,
            MIN(eo.occur_date) AS first_date
        FROM booking b
        JOIN booking_line bl ON bl.booking_id = b.booking_id
        JOIN event_occurrence eo ON eo.occurrence_id = bl.occurrence_id
        JOIN event e ON e.event_id = eo.event_id
        WHERE b.booking_id = %s
        GROUP BY b.booking_id, b.user_id, b.status, b.total_after_discounts, e.name
    """, (booking_id,))
    booking = cursor.fetchone()

    if not booking:
        cursor.close()
        conn.close()
        abort(404)

    # Permission check
    if booking["user_id"] != user_id and role != "ADMIN":
        cursor.close()
        conn.close()
        abort(403)

    # Already cancelled?
    if booking["status"] == "CANCELLED":
        cursor.close()
        conn.close()
        flash("This booking is already cancelled.", "cancel_warning")
        return redirect(url_for("booking_bp.dashboard"))

    today = date.today()
    event_date = booking["first_date"]
    days_left = (event_date - today).days

    # Event already passed
    if days_left < 0:
        cursor.close()
        conn.close()
        flash("This event has already passed. Cancellation is not allowed.", "cancel_warning")
        return redirect(url_for("booking_bp.dashboard"))

    # BCE CANCELLATION RULES
    if days_left >= 40:
        refund_percent = 100
    elif 25 <= days_left <= 39:
        refund_percent = 60
    else:  # 0–24 days
        refund_percent = 0

    # Refund calculation
    refund = (
        Decimal(str(booking["total_after_discounts"])) *
        Decimal(refund_percent) / Decimal(100)
    ).quantize(Decimal("0.01"))

    # POST: Process cancellation
    if request.method == "POST":
        card_number = request.form.get("card_number")
        expiry = request.form.get("expiry")
        cvc = request.form.get("cvc")

        if not all([card_number, expiry, cvc]):
            cursor.close()
            conn.close()
            flash("All card fields are required.", "error")
            return redirect(url_for("booking_bp.cancel_booking", booking_id=booking_id))

        # Insert refund payment
        cursor.execute("""
            INSERT INTO payment (booking_id, method, status, amount, provider_ref)
            VALUES (%s, 'REFUND', 'SUCCESS', %s, 'SIMULATED_REFUND')
        """, (booking_id, refund))

        # Update booking status
        cursor.execute(
            "UPDATE booking SET status = 'CANCELLED' WHERE booking_id = %s",
            (booking_id,)
        )
        conn.commit()

        # WAITING LIST PROMOTION LOGIC
        # Find earliest waiting user for any of the cancelled occurrences
        cursor.execute("""
            SELECT wl.waiting_id, wl.user_id, wl.occurrence_id
            FROM waiting_list wl
            JOIN booking_line bl ON bl.occurrence_id = wl.occurrence_id
            WHERE bl.booking_id = %s
            AND wl.status = 'WAITING'
            ORDER BY wl.request_ts ASC
            LIMIT 1
        """, (booking_id,))
        next_user = cursor.fetchone()

        if next_user:
            cursor.execute("""
                UPDATE waiting_list
                SET status = 'OFFERED'
                WHERE waiting_id = %s
            """, (next_user["waiting_id"],))
            conn.commit()

        cursor.close()
        conn.close()

        flash(f"Booking cancelled. Refund processed: £{refund}", "success")
        return redirect(url_for("booking_bp.dashboard"))

    cursor.close()
    conn.close()

    return render_template(
        "cancel_booking.html",
        booking=booking,
        days_left=days_left,
        refund_percent=refund_percent,
        refund=refund
    )
