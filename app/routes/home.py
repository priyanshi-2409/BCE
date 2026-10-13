#Student_ID_25017334_Name_Priyanshi_Jadeja
from flask import Blueprint, render_template, request, url_for, flash, redirect
from app.dbfunc import get_connection

home_bp = Blueprint("home_bp", __name__)

# HOME PAGE

@home_bp.route("/")
def home():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch upcoming events automatically
    cursor.execute("""
        SELECT 
            e.event_id,
            e.name,
            e.start_date,
            e.end_date,
            e.base_total_price,
            l.name AS venue_name,
            e.image_url
        FROM event e
        JOIN location l ON e.location_id = l.location_id
        WHERE e.is_active = TRUE
        AND e.start_date >= CURDATE()
        ORDER BY e.start_date ASC
        LIMIT 2;
    """)
    upcoming_events = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("home.html", upcoming_events=upcoming_events)


# SEARCH RESULTS

@home_bp.route("/search", methods=["GET"])
def search():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    keyword = request.args.get("keyword", "").strip()
    category_id = request.args.get("category_id")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    price_type = request.args.get("price_type")  # FREE / PAID / ANY

    # Validate date range
    if start_date and end_date and start_date > end_date:
        flash("Start date cannot be after end date.")
        return redirect(url_for("home_bp.home"))

    # Base query 
    query = """
        SELECT 
            e.event_id,
            e.name,
            e.description,
            e.base_total_price,
            l.name AS venue_name,
            l.capacity,

            CASE 
                WHEN MIN(o.price_per_day) IS NULL THEN 'FREE'
                WHEN MIN(o.price_per_day) = 0 AND MAX(o.price_per_day) = 0 THEN 'FREE'
                ELSE 'PAID'
            END AS price_type,

            MIN(o.occur_date) AS next_date

        FROM event e
        JOIN location l ON l.location_id = e.location_id
        LEFT JOIN event_occurrence o ON o.event_id = e.event_id
        LEFT JOIN event_category ec ON ec.event_id = e.event_id
        LEFT JOIN category c ON c.category_id = ec.category_id
        WHERE e.is_active = TRUE
    """

    params = []

    # Keyword filter
    if keyword:
        query += " AND (e.name LIKE %s OR e.description LIKE %s) "
        params += [f"%{keyword}%", f"%{keyword}%"]

    # Category filter
    if category_id and category_id != "all":
        query += " AND c.category_id = %s "
        params.append(category_id)

    # Date range filter
    if start_date and end_date:
        query += " AND o.occur_date BETWEEN %s AND %s "
        params += [start_date, end_date]

    # Price filter
    if price_type == "FREE":
        query += " AND o.price_per_day = 0 "
    elif price_type == "PAID":
        query += " AND o.price_per_day > 0 "

    query += """
        GROUP BY e.event_id, e.name, l.name, l.capacity
        ORDER BY next_date IS NULL, next_date ASC
    """

    cursor.execute(query, params)
    events = cursor.fetchall()

    # Fetch categories for each event
    cursor.execute("""
        SELECT 
            ec.event_id,
            c.name AS category_name
        FROM event_category ec
        JOIN category c ON c.category_id = ec.category_id
    """)
    raw_categories = cursor.fetchall()

    categories_map = {}
    for row in raw_categories:
        categories_map.setdefault(row["event_id"], []).append(row["category_name"])

    for e in events:
        e["categories"] = categories_map.get(e["event_id"], [])

    cursor.close()
    conn.close()

    return render_template("events.html", events=events)

# STATIC PAGES

@home_bp.route("/about")
def about():
    return render_template("about_us.html")

@home_bp.route("/lesp")
def lesp():
    return render_template("lesp.html")