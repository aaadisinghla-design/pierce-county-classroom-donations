import os
import sqlite3
from datetime import datetime
from decimal import Decimal, InvalidOperation

import pandas as pd
import streamlit as st
import stripe

# ---------------- Configuration ----------------
st.set_page_config(
    page_title="Pierce County Classroom Donations",
    page_icon="📚",
    layout="wide",
)

DB_FILE = os.getenv("DB_FILE", "classroom_donations.db")
APP_URL = os.getenv("APP_URL", "http://localhost:8501").rstrip("/")

# Prefer Streamlit secrets; fall back to environment variables.
try:
    STRIPE_SECRET_KEY = st.secrets.get("STRIPE_SECRET_KEY", "")
except Exception:
    STRIPE_SECRET_KEY = ""

STRIPE_SECRET_KEY = STRIPE_SECRET_KEY or os.getenv("STRIPE_SECRET_KEY", "")
stripe.api_key = STRIPE_SECRET_KEY


# ---------------- Database ----------------
def get_conn():
    conn = sqlite3.connect(DB_FILE, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_name TEXT NOT NULL,
                school_name TEXT NOT NULL,
                district TEXT NOT NULL,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                goal_amount REAL NOT NULL CHECK (goal_amount > 0),
                raised_amount REAL NOT NULL DEFAULT 0.0 CHECK (raised_amount >= 0),
                created_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS donations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER NOT NULL,
                donor_name TEXT,
                amount REAL NOT NULL CHECK (amount > 0),
                message TEXT,
                stripe_session_id TEXT UNIQUE NOT NULL,
                donated_at TEXT,
                FOREIGN KEY (request_id) REFERENCES requests(id)
            )
        """)
        count = conn.execute("SELECT COUNT(*) FROM requests").fetchone()[0]
        if count == 0:
            today = datetime.now().strftime("%Y-%m-%d")
            samples = [
                ("Ms. Alvarez", "Lakeridge Middle School", "Sumner-Bonney Lake",
                 "STEM Robotics & Sensor Kits", "STEM & Tech",
                 "Programmable microcontrollers and ultrasonic sensors for 8th-grade engineering.",
                 450.0, 180.0, today),
                ("Mr. Jenkins", "Bonney Lake High School", "Sumner-Bonney Lake",
                 "AP Physics Lab Equipment", "Science",
                 "Digital force sensors and dynamics carts for mechanics labs.",
                 600.0, 425.0, today),
                ("Mrs. Chen", "Emerald Ridge High School", "Puyallup",
                 "Classroom Library & Novels", "Books & Literacy",
                 "Diverse contemporary fiction and non-fiction sets for 10th-grade English.",
                 300.0, 90.0, today),
            ]
            conn.executemany("""
                INSERT INTO requests
                (teacher_name, school_name, district, title, category,
                 description, goal_amount, raised_amount, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, samples)


init_db()


# ---------------- Stripe return verification ----------------
def verify_returned_payment(session_id):
    """Record a paid checkout session once, and update its project total atomically."""
    if not STRIPE_SECRET_KEY:
        st.session_state["payment_error"] = (
            "Stripe is not configured. Set STRIPE_SECRET_KEY before verifying payments."
        )
        return

    try:
        session = stripe.checkout.Session.retrieve(session_id)
        if session.payment_status != "paid":
            st.session_state["payment_error"] = (
                "This checkout session has not been marked as paid."
            )
            return

        metadata = session.metadata or {}
        request_id = int(metadata.get("request_id", ""))
        donor = metadata.get("donor_name", "Anonymous") or "Anonymous"
        message = metadata.get("message", "")
        amount_cents = session.amount_total
        if amount_cents is None or amount_cents <= 0:
            raise ValueError("Stripe returned an invalid payment amount.")
        dollars = amount_cents / 100.0
        donated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with get_conn() as conn:
            # INSERT OR IGNORE plus unique session id prevents double counting.
            cursor = conn.execute("""
                INSERT OR IGNORE INTO donations
                (request_id, donor_name, amount, message, stripe_session_id, donated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (request_id, donor, dollars, message, session_id, donated_at))

            if cursor.rowcount == 1:
                conn.execute("""
                    UPDATE requests
                    SET raised_amount = raised_amount + ?
                    WHERE id = ?
                """, (dollars, request_id))
                st.session_state["payment_success"] = (
                    f"Thank you, {donor}! Your ${dollars:,.2f} donation is confirmed."
                )
            else:
                st.session_state["payment_success"] = (
                    "This donation has already been recorded. Thank you!"
                )

    except (stripe.error.StripeError, ValueError, TypeError, KeyError, sqlite3.Error) as exc:
        st.session_state["payment_error"] = f"Payment verification error: {exc}"


session_id = st.query_params.get("session_id")
if session_id:
    verify_returned_payment(session_id)
    st.query_params.clear()
    st.rerun()

if "payment_success" in st.session_state:
    st.success(st.session_state.pop("payment_success"))
    st.balloons()

if "payment_error" in st.session_state:
    st.error(st.session_state.pop("payment_error"))


# ---------------- Helpers ----------------
DISTRICTS = [
    "Sumner-Bonney Lake", "Puyallup", "Tacoma", "Bethel", "Peninsula", "Clover Park"
]
CATEGORIES = ["STEM & Tech", "Science", "Books & Literacy", "Art & Music", "General Supplies"]


def create_checkout(request_row, donor, amount, message):
    if not STRIPE_SECRET_KEY:
        raise RuntimeError("Stripe is not configured. Add STRIPE_SECRET_KEY to secrets or env.")
    cents = int((Decimal(str(amount)) * 100).quantize(Decimal("1")))
    if cents < 500:
        raise ValueError("Donations must be at least $5.00.")

    checkout_session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {
                    "name": f"Donation: {request_row['title'][:200]}",
                    "description": (
                        f"Supporting {request_row['teacher_name']} at "
                        f"{request_row['school_name']}"
                    )[:500],
                },
                "unit_amount": cents,
            },
            "quantity": 1,
        }],
        mode="payment",
        metadata={
            "request_id": str(request_row["id"]),
            "donor_name": (donor.strip() or "Anonymous")[:200],
            "message": message.strip()[:500],
        },
        success_url=f"{APP_URL}/?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{APP_URL}/",
    )
    return checkout_session


# ---------------- Main UI ----------------
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Browse Classrooms", "Teacher Request Portal"])

if page == "Browse Classrooms":
    st.title("📚 Pierce County Classroom Donations")
    st.write("Directly fund classroom supplies and STEM projects for local teachers.")

    if not STRIPE_SECRET_KEY:
        st.warning(
            "Stripe is not configured. Add your Stripe test secret key to Streamlit secrets "
            "or the STRIPE_SECRET_KEY environment variable to enable checkout."
        )

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        district_filter = st.selectbox("Filter by School District", ["All", *DISTRICTS])
    with col_f2:
        category_filter = st.selectbox("Filter by Category", ["All", *CATEGORIES])

    with get_conn() as conn:
        query = "SELECT * FROM requests WHERE 1=1"
        params = []
        if district_filter != "All":
            query += " AND district = ?"
            params.append(district_filter)
        if category_filter != "All":
            query += " AND category = ?"
            params.append(category_filter)
        query += " ORDER BY id DESC"
        df = pd.read_sql_query(query, conn, params=params)

    if df.empty:
        st.info("No classroom projects match your selected filters.")
    else:
        for _, row in df.iterrows():
            request_row = row.to_dict()
            with st.container(border=True):
                c1, c2 = st.columns(2)
                with c1:
                    st.subheader(row["title"])
                    st.caption(
                        f"**{row['teacher_name']}** • {row['school_name']} ({row['district']})"
                    )
                    st.write(row["description"] or "")
                    goal = float(row["goal_amount"])
                    raised = float(row["raised_amount"])
                    pct = min(max(raised / goal, 0.0), 1.0) if goal > 0 else 0.0
                    st.progress(pct)
                    st.write(
                        f"**${raised:,.2f}** raised of **${goal:,.2f}** goal "
                        f"({int(pct * 100)}%)"
                    )

                with c2:
                    donor = st.text_input(
                        "Your Name", placeholder="Anonymous", key=f"name_{row['id']}"
                    )
                    amt = st.number_input(
                        "Amount ($)", min_value=5.0, value=25.0, step=5.0,
                        key=f"amt_{row['id']}"
                    )
                    msg = st.text_input(
                        "Note to Teacher", placeholder="Great project!",
                        key=f"msg_{row['id']}"
                    )

                    if st.button(
                        "Proceed to Checkout", key=f"btn_{row['id']}",
                        use_container_width=True
                    ):
                        try:
                            session = create_checkout(request_row, donor, amt, msg)
                            st.link_button(
                                "💳 Pay Now on Stripe", session.url,
                                type="primary", use_container_width=True
                            )
                        except (stripe.error.StripeError, ValueError, RuntimeError) as exc:
                            st.error(f"Checkout error: {exc}")

elif page == "Teacher Request Portal":
    st.title("✏️ Submit a Classroom Supply Request")
    with st.form("teacher_form", clear_on_submit=True):
        t_name = st.text_input("Teacher Name")
        s_name = st.text_input("School Name")
        dist = st.selectbox("School District", DISTRICTS)
        p_title = st.text_input("Project Title")
        cat = st.selectbox("Category", CATEGORIES)
        desc = st.text_area("Project Description")
        goal = st.number_input("Funding Goal ($)", min_value=25.0, value=250.0, step=25.0)
        submitted = st.form_submit_button("Publish Request")

    if submitted:
        if not t_name.strip() or not s_name.strip() or not p_title.strip():
            st.error("Please fill in Teacher Name, School Name, and Project Title.")
        elif goal < 25:
            st.error("The funding goal must be at least $25.")
        else:
            try:
                with get_conn() as conn:
                    conn.execute("""
                        INSERT INTO requests
                        (teacher_name, school_name, district, title, category,
                         description, goal_amount, raised_amount, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 0.0, ?)
                    """, (
                        t_name.strip(), s_name.strip(), dist, p_title.strip(), cat,
                        desc.strip(), float(goal), datetime.now().strftime("%Y-%m-%d")
                    ))
                st.success("Your classroom request has been published!")
            except sqlite3.Error as exc:
                st.error(f"Database error while publishing: {exc}")
