#Student_ID_25017334_Name_Priyanshi_Jadeja
from flask import Blueprint, render_template, abort
from app.dbfunc import get_connection

events_bp = Blueprint("events_bp", __name__)

# EVENTS LIST

@events_bp.route("/events")
def events_list():

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            e.event_id,
            e.name,
            e.description,
            e.conditions,
            e.start_date,
            e.end_date,
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
        WHERE e.is_active = TRUE

        /* FIXED GROUP BY — all non-aggregated columns included */
        GROUP BY 
            e.event_id,
            e.name,
            e.description,
            e.conditions,
            e.start_date,
            e.end_date,
            e.base_total_price,
            l.name,
            l.capacity

        ORDER BY 
            next_date IS NULL, 
            next_date ASC
    """)

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

# EVENT DETAILS

@events_bp.route("/event/<int:event_id>")
def event_details(event_id):

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # Event + location
    cursor.execute("""
        SELECT 
            e.*,
            l.name AS location_name,
            l.capacity AS location_capacity
        FROM event e
        JOIN location l ON l.location_id = e.location_id
        WHERE e.event_id = %s
    """, (event_id,))
    event = cursor.fetchone()

    if not event:
        cursor.close()
        conn.close()
        abort(404)

    # Categories
    cursor.execute("""
        SELECT c.name
        FROM category c
        JOIN event_category ec ON ec.category_id = c.category_id
        WHERE ec.event_id = %s
    """, (event_id,))
    categories = [row["name"] for row in cursor.fetchall()]

    # Occurrences + remaining tickets
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
        "cap": event["location_capacity"],
        "event_id": event_id
    })
    occurrences = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "event_details.html",
        event=event,
        categories=categories,
        occurrences=occurrences
    )