from datetime import datetime
import os
import sqlite3

import pandas as pd
import streamlit as st
import stripe

st.set_page_config(page_title="Pierce County Classroom Donations", page_icon="📚", layout="wide")

DB_PATH = os.getenv("DB_PATH", "classroom_donations.db")
APP_URL = os.getenv("APP_URL", "http://localhost:8501").rstrip("/")
STRIPE_SECRET_KEY = (
    st.secrets.get("STRIPE_SECRET_KEY")
    if "STRIPE_SECRET_KEY" in st.secrets
    else os.getenv("STRIPE_SECRET_KEY", "")
)
if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY

DISTRICTS = [
    "Tacoma Public Schools",
    "Puyallup School District",
    "Bethel School District",
    "Clover Park School District",
    "Peninsula School District",
    "Sumner-Bonney Lake School District",
]

CATEGORIES = [
    "STEM & Robotics",
    "Books & Literacy",
    "Art & Music",
    "Classroom Supplies",
    "Special Education",
]


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_name TEXT NOT NULL,
            school_name TEXT NOT NULL,
            district TEXT NOT NULL,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            goal_amount REAL NOT NULL,
            raised_amount REAL NOT NULL DEFAULT 0.0,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def create_checkout(request_row: dict, donor: str, amount: float, message: str):
    if not STRIPE_SECRET_KEY:
        raise RuntimeError("STRIPE_SECRET_KEY is not configured.")
    if amount < 5.0:
        raise ValueError("Donation amount must be at least $5.00.")

    amount_cents = int(round(float(amount) * 100))
    checkout_session = stripe.checkout.Session.create(
        mode="payment",
        payment_method_types=["card"],
        line_items=[
            {
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": f"Donation: {request_row['title']}",
                        "description": f"{request_row['teacher_name']} — {request_row['school_name']}",
                    },
                    "unit_amount": amount_cents,
                },
                "quantity": 1,
            }
        ],
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
            req_id = request_row["id"]
            checkout_key = f"checkout_url_{req_id}"

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
                        "Your Name", placeholder="Anonymous", key=f"name_{req_id}"
                    )
                    amt = st.number_input(
                        "Amount ($)",
                        min_value=5.0,
                        value=25.0,
                        step=5.0,
                        key=f"amt_{req_id}",
                    )
                    msg = st.text_input(
                        "Note to Teacher", placeholder="Great project!", key=f"msg_{req_id}"
                    )

                    if st.button(
                        "Proceed to Checkout",
                        key=f"btn_{req_id}",
                        use_container_width=True,
                    ):
                        try:
                            session = create_checkout(request_row, donor, amt, msg)
                            st.session_state[checkout_key] = session.url
                        except (stripe.StripeError, ValueError, RuntimeError) as exc:
                            st.error(f"Checkout error: {exc}")

                    if st.session_state.get(checkout_key):
                        st.link_button(
                            "💳 Pay Now on Stripe",
                            st.session_state[checkout_key],
                            type="primary",
                            use_container_width=True,
                        )

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
                    conn.execute(
                        """
                        INSERT INTO requests
                        (teacher_name, school_name, district, title, category,
                         description, goal_amount, raised_amount, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 0.0, ?)
                        """,
                        (
                            t_name.strip(),
                            s_name.strip(),
                            dist,
                            p_title.strip(),
                            cat,
                            desc.strip(),
                            float(goal),
                            datetime.now().strftime("%Y-%m-%d"),
                        ),
                    )
                st.success("Your classroom request has been published!")
            except sqlite3.Error as exc:
                st.error(f"Database error while publishing: {exc}")
