import streamlit as st
import sqlite3
import uuid

# 1. Page Configuration
st.set_page_config(
    page_title="Chalk Fund",
    layout="wide"
)

# 2. SQL DATABASE STORAGE IMPLEMENTATION
DB_FILE = "pierce_classrooms.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS registries (
            id TEXT PRIMARY KEY,
            district TEXT,
            school TEXT,
            teacher TEXT,
            vendor TEXT,
            description TEXT,
            total_cost REAL,
            cart_url TEXT,
            status TEXT
        )
    """)
    conn.commit()
    
    # Inject default items if the database is brand new and empty
    cursor.execute("SELECT COUNT(*) FROM registries")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
            INSERT INTO registries VALUES (
                'v1', 'Sumner-Bonney Lake SD', 'Tehaleh Heights Elementary',
                'Mrs. Vance (Grade 1)', 'Amazon Business', 
                '24ct Ticonderoga Pencils (x10), Pack of 4 Sensory Foam Blocks', 
                145.50, 'https://amazon.com', 'Pending'
            )
        """)
        cursor.execute("""
            INSERT INTO registries VALUES (
                'v2', 'Sumner-Bonney Lake SD', 'Donald Eismann Elementary',
                'Mr. Brody (SPED Room)', 'Walmart Business', 
                'Classroom Reading Rug (8x12ft), 3 Weighted Sensory Lap Pads', 
                320.00, 'https://walmart.com', 'Pending'
            )
        """)
        conn.commit()
    conn.close()

init_db()

def get_all_carts():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, district, school, teacher, vendor, description, total_cost, cart_url, status FROM registries")
    rows = cursor.fetchall()
    conn.close()
    
    carts = []
    for r in rows:
        carts.append({
            "id": r[0], "district": r[1], "school": r[2], "teacher": r[3],
            "vendor": r[4], "description": r[5], "total_cost": r[6], "cart_url": r[7], "status": r[8]
        })
    return carts

def add_cart_to_db(uid, dist, sch, teacher, vendor, desc, cost, url):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO registries VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Pending')", (uid, dist, sch, teacher, vendor, desc, cost, url))
    conn.commit()
    conn.close()

def update_cart_status_in_db(uid, status_val):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE registries SET status = ? WHERE id = ?", (status_val, uid))
    conn.commit()
    conn.close()


# 3. App Title Header Banners
st.title("🏛️ Pierce County Direct Vendor Donation Hub")
st.caption("Teachers prep carts • Donors fund them directly • Vendors ship securely to the school warehouse")
st.markdown("---")

# 4. Workspace Profiles
role = st.radio("Choose Your Workspace Mode:", ["Donor View", "Teacher Management"], horizontal=True)

# 5. Sidebar Location Navigator
st.sidebar.header("📍 Location Navigator")
district_list = ["Sumner-Bonney Lake SD", "Tacoma School District No. 1", "Puyallup School District"]
selected_district = st.sidebar.selectbox("Select School District", district_list)

schools_map = {
    "Sumner-Bonney Lake SD": ["Tehaleh Heights Elementary", "Donald Eismann Elementary", "Maple Lawn Elementary"],
    "Tacoma School District No. 1": ["Sherman Elementary", "Lowell Elementary"],
    "Puyallup School District": ["Maplewood Elementary", "Wildwood Elementary"]
}
selected_school = st.sidebar.selectbox("Select Elementary Campus", schools_map[selected_district])

st.sidebar.markdown("---")
st.sidebar.info("🔒 Masked Shipping Enabled: Retailers will automatically route items to your school warehouse to preserve staff privacy.")


# 6. TEACHER MANAGEMENT MODULE
if role == "Teacher Management":
    st.header("✏️ Create Direct Vendor Request")
    st.markdown("Paste your shared cart or wishlist link from **Amazon, Walmart, Target, Scholastic, or any other store**.")
    
    with st.form("teacher_cart_form", clear_on_submit=True):
        t_name = st.text_input("Your Name & Grade (e.g., Ms. Smith - Grade 2)")
        vendor_name = st.selectbox("Select Vendor Store", ["Amazon Business", "Walmart Business", "Target Registry", "Lakeshore Learning", "Scholastic"])
        cart_summary = st.text_area("List of items in this cart")
        cost = st.number_input("Total Cart Value (\$)", min_value=1.00, step=0.01)
        cart_link = st.text_input("Shared Cart / Wishlist Link URL (Paste any retail link here)")
        
        if st.form_submit_button("Publish Cart for Donors"):
            if not t_name or not cart_summary or not cart_link or cost <= 0:
                st.error("Please fill out all cart parameters.")
            else:
                if not cart_link.startswith(("http://", "https://")):
                    cart_link = "https://" + cart_link
                
                add_cart_to_db(str(uuid.uuid4()), selected_district, selected_school, t_name, vendor_name, cart_summary, cost, cart_link)
                st.success("Your cart has been permanently saved to the database! Switch to 'Donor View' to check it out.")


# 7. DONOR VIEW MODULE
if role == "Donor View":
    st.header(f"🎁 Active Carts Needing Funding: {selected_school}")
    
    all_database_carts = get_all_carts()
    active_carts = [c for c in all_database_carts if c["district"] == selected_district and c["school"] == selected_school]
    
    if not active_carts:
        st.info("No active teacher carts currently published for this campus location. Switch to 'Teacher Management' to add one!")
    else:
        for item in active_carts:
            with st.container():
                st.markdown(f"### 🛒 {item['vendor']} Cart — Prepared by {item['teacher']}")
                st.markdown(f"**Requested Supplies:** {item['description']}")
                st.markdown(f"### Total Cost: `${item['total_cost']:.2f}`")
                
                if item["status"] == "Paid":
                    st.success("🎉 Donated! This cart has been paid for and is being shipped straight to the school.")
                else:
                    st.markdown(f'<a href="{item["cart_url"]}" target="_blank" style="text-decoration:none;"><button style="background-color:#2563eb; color:white; border:none; padding:10px 20px; border-radius:8px; font-weight:bold; cursor:pointer; font-size:14px;">1. Open & Buy Cart on {item["vendor"]} ↗</button></a>', unsafe_allow_html=True)
                    st.caption(f"This routes you directly to {item['vendor']} to complete the checkout safely.")
                    
                    st.markdown("#### 2. Did you complete the retail checkout transaction?")
                    if st.button("Yes, I paid for this cart! Mark as Donated", key=f"paid_{item['id']}"):
                        update_cart_status_in_db(item['id'], "Paid")
                        st.success("Thank you for your incredible generosity! The database has updated.")
                        st.rerun()
                st.markdown("---")
                # 6. TEACHER MANAGEMENT MODULE
if role == "Teacher Management":
    st.header("✏️ Create Direct Vendor Request")
    st.markdown("Paste your shared cart or wishlist link from **Amazon, Walmart, Target, Scholastic, or any other store**.")
    
    with st.form("teacher_cart_form", clear_on_submit=True):
        t_name = st.text_input("Your Name & Grade (e.g., Ms. Smith - Grade 2)")
        vendor_name = st.selectbox("Select Vendor Store", ["Amazon Business", "Walmart Business", "Target Registry", "Lakeshore Learning", "Scholastic"])
        cart_summary = st.text_area("List of items in this cart")
        cost = st.number_input("Total Cart Value (\$)", min_value=1.00, step=0.01)
        cart_link = st.text_input("Shared Cart / Wishlist Link URL (Paste any retail link here)")
        
        if st.form_submit_button("Publish Cart for Donors"):
            if not t_name or not cart_summary or not cart_link or cost <= 0:
                st.error("Please fill out all cart parameters.")
            else:
                if not cart_link.startswith(("http://", "https://")):
                    cart_link = "https://" + cart_link
                
                add_cart_to_db(str(uuid.uuid4()), selected_district, selected_school, t_name, vendor_name, cart_summary, cost, cart_link)
                st.success("Your cart has been permanently saved to the database! Switch to 'Donor View' to check it out.")

    # --- NEW FEATURE: TEACHER RESET CONSOLE ---
    st.markdown("---")
    st.subheader("🛠️ Teacher Registry Administration")
    st.caption("Review your live campus requests. If a donor accidentally marked an item as paid, click 'Reset to Pending' below.")
    
    all_carts = get_all_carts()
    school_carts = [c for c in all_carts if c["district"] == selected_district and c["school"] == selected_school]
    
    if school_carts:
        for item in school_carts:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"**{item['teacher']}** — {item['vendor']} Cart (\${item['total_cost']:.2f}) | Status: `{item['status']}`")
            with col2:
                # If it was accidentally marked paid, this resets it back to pending in the SQLite file!
                if st.button("🔄 Reset to Pending", key=f"reset_{item['id']}"):
                    update_cart_status_in_db(item['id'], "Pending")
                    st.success("Status reset successfully!")
                    st.rerun()
    else:
        st.info("No items listed on this campus to manage.")
