import streamlit as st
import pandas as pd
import sqlite3
import hashlib
from io import StringIO

# ================= AUTH & DATABASE ==================

def get_connection():
    return sqlite3.connect("inventory.db", check_same_thread=False)

def create_tables():
    conn = get_connection()
    conn.execute(
        """CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT
        );"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id TEXT,
            name TEXT,
            category TEXT,
            quantity INTEGER,
            price REAL,
            location TEXT
        );"""
    )
    conn.commit()
    conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def add_user(username, password, role):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            (username, hash_password(password), role)
        )
        conn.commit()
        return True
    except:
        return False
    finally:
        conn.close()

def login_user(username, password):
    conn = get_connection()
    cursor = conn.execute(
        "SELECT * FROM users WHERE username=? AND password=?",
        (username, hash_password(password))
    )
    data = cursor.fetchone()
    conn.close()
    return data

# ================= APP LOGIC ==================

st.set_page_config(page_title="Inventory Management", layout="wide")
create_tables()

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "role" not in st.session_state:
    st.session_state.role = None

# ---------------- LOGIN / REGISTER UI ----------------

if not st.session_state.logged_in:
    tab1, tab2 = st.tabs(["🔐 Login", "📝 Register"])

    with tab1:
        st.subheader("Login")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            user = login_user(username, password)
            if user:
                st.session_state.logged_in = True
                st.session_state.user = username
                st.session_state.role = user[3]
                st.success(f"Welcome {username} ({st.session_state.role})")
                st.rerun()
            else:
                st.error("Invalid username or password")

    with tab2:
        st.subheader("Create Account")
        new_username = st.text_input("New Username")
        new_password = st.text_input("New Password", type="password")
        role = st.selectbox("Role", ["user", "admin"])
        if st.button("Register"):
            if add_user(new_username, new_password, role):
                st.success("Registration successful! You can login now.")
            else:
                st.error("Username already exists!")

    st.stop()

# ================= After Login ==================

st.sidebar.success(f"Logged in as: {st.session_state.user} ({st.session_state.role})")
if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()

# ================= Inventory Functions ==================

def load_inventory():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM inventory", conn)
    conn.close()
    return df

def save_item(item_id, name, category, quantity, price, location):
    conn = get_connection()
    conn.execute(
        "INSERT INTO inventory (item_id, name, category, quantity, price, location) VALUES (?,?,?,?,?,?)",
        (item_id, name, category, quantity, price, location)
    )
    conn.commit()
    conn.close()

def update_item(db_id, name, category, quantity, price, location):
    conn = get_connection()
    conn.execute(
        "UPDATE inventory SET name=?, category=?, quantity=?, price=?, location=? WHERE id=?",
        (name, category, quantity, price, location, db_id)
    )
    conn.commit()
    conn.close()

def delete_item(db_id):
    conn = get_connection()
    conn.execute("DELETE FROM inventory WHERE id=?", (db_id,))
    conn.commit()
    conn.close()

# ================= Main UI ==================

st.title("📦 Inventory Management System")

df = load_inventory()

tab_view, tab_add = st.tabs(["📋 View Inventory", "➕ Add Item"])

# View Tab
with tab_view:
    st.header("Inventory List")

    if df.empty:
        st.info("No inventory records yet.")
    else:
        st.dataframe(df)

        selected = st.selectbox("Select item to edit/delete", df["item_id"].tolist())
        row = df[df["item_id"] == selected].iloc[0]

        name = st.text_input("Name", row["name"])
        category = st.text_input("Category", row["category"])
        quantity = st.number_input("Quantity", value=row["quantity"], min_value=0)
        price = st.number_input("Price", value=row["price"], min_value=0.0)
        location = st.text_input("Location", row["location"])

        col1, col2 = st.columns(2)

        with col1:
            if st.button("Update"):
                update_item(row["id"], name, category, quantity, price, location)
                st.success("Updated Successfully")
                st.rerun()

        # Delete only for Admins
        if st.session_state.role == "admin":
            with col2:
                if st.button("Delete"):
                    delete_item(row["id"])
                    st.success("Deleted Successfully")
                    st.rerun()

# Add Item Tab (Admin Only)
with tab_add:
    if st.session_state.role != "admin":
        st.warning("Only Admins can add new inventory items.")
        st.stop()

    st.header("Add New Item")
    item_id = st.text_input("Item ID")
    name = st.text_input("Name")
    category = st.text_input("Category")
    quantity = st.number_input("Quantity", min_value=0)
    price = st.number_input("Unit Price", min_value=0.0)
    location = st.text_input("Location")

    if st.button("Add Item"):
        save_item(item_id, name, category, quantity, price, location)
        st.success("Item added successfully")
        st.rerun()
