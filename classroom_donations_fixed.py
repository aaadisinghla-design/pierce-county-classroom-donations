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
                        except (stripe.StripeError, ValueError, RuntimeError) as exc:
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
