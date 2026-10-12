import os
import time
from datetime import date

import pymysql
from flask import Flask, redirect, render_template, request, url_for

app = Flask(__name__)

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "db"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", "password"),
    "database": os.getenv("DB_NAME", "expensedb"),
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": True,
}

CATEGORIES = ["Food", "Transport", "Rent", "Shopping", "Health", "Entertainment", "Other"]


def get_conn():
    return pymysql.connect(**DB_CONFIG)


def init_db(retries=30, delay=2):
    """Wait for MySQL to be ready, then create the table."""
    for attempt in range(1, retries + 1):
        try:
            conn = get_conn()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS expenses (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        title VARCHAR(120) NOT NULL,
                        amount DECIMAL(10,2) NOT NULL,
                        category VARCHAR(40) NOT NULL,
                        spent_on DATE NOT NULL
                    )
                    """
                )
            conn.close()
            print("Database ready.")
            return
        except pymysql.MySQLError as e:
            print(f"DB not ready (attempt {attempt}/{retries}): {e}")
            time.sleep(delay)
    raise RuntimeError("Could not connect to the database.")


@app.route("/")
def index():
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM expenses ORDER BY spent_on DESC, id DESC")
        expenses = cur.fetchall()
        cur.execute("SELECT COALESCE(SUM(amount), 0) AS total FROM expenses")
        total = cur.fetchone()["total"]
        cur.execute(
            "SELECT category, SUM(amount) AS subtotal FROM expenses "
            "GROUP BY category ORDER BY subtotal DESC"
        )
        summary = cur.fetchall()
    conn.close()
    return render_template(
        "index.html",
        expenses=expenses,
        total=total,
        summary=summary,
        categories=CATEGORIES,
        today=date.today().isoformat(),
    )


@app.route("/add", methods=["POST"])
def add():
    title = request.form.get("title", "").strip()
    category = request.form.get("category", "Other")
    spent_on = request.form.get("spent_on") or date.today().isoformat()
    try:
        amount = float(request.form.get("amount", "0"))
    except ValueError:
        amount = 0
    if title and amount > 0:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO expenses (title, amount, category, spent_on) "
                "VALUES (%s, %s, %s, %s)",
                (title, amount, category, spent_on),
            )
        conn.close()
    return redirect(url_for("index"))


@app.route("/delete/<int:expense_id>", methods=["POST"])
def delete(expense_id):
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM expenses WHERE id = %s", (expense_id,))
    conn.close()
    return redirect(url_for("index"))


@app.route("/health")
def health():
    try:
        conn = get_conn()
        conn.ping()
        conn.close()
        return {"status": "ok", "database": "connected"}, 200
    except Exception as e:
        return {"status": "error", "detail": str(e)}, 500


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
