#Student_ID_25017334_Name_Priyanshi_Jadeja

import mysql.connector
from mysql.connector import Error

def get_connection():
    try:
        conn = mysql.connector.connect(
            host="127.0.0.1",
            port=3306,
            user="root",
            password="Pj6262@uni24",
            database="priyanshi_local"
        )
        print("DB CONNECTED")
        return conn
    except Error as e:
        print("Database connection error:", e)
        return None
def execute_query(query, params=None):
    conn = get_connection()
    if not conn:
        return None

    cursor = conn.cursor(dictionary=True)
    cursor.execute(query, params)
    conn.commit()
    cursor.close()
    conn.close()
    return True


def fetch_one(query, params=None):
    conn = get_connection()
    if not conn:
        return None

    cursor = conn.cursor(dictionary=True)
    cursor.execute(query, params)
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result