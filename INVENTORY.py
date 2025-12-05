import streamlit as st
import pandas as pd
import sqlite3
import hashlib
from datetime import datetime

# ----------------- DB & AUTH HELPERS -----------------

DB_NAME = "inventory_system.db"

def get_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def create_tables():
    conn = get_connection()
    cur = conn.cursor()

    # Users (User Management & Authentication)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT
        );
    """)

    # Items (Item Management)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_code TEXT UNIQUE,
            name TEXT,
            category TEXT,
            unit_price REAL,
            min_stock INTEGER,
            quantity INTEGER DEFAULT 0,
            description TEXT
        );
    """)

    # Stock Movements (Stock Management + Dispatch/Purchase)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS stock_movements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER,
            movement_type TEXT, -- PURCHASE, DISPATCH, ADJUSTMENT, INITIAL
            quantity INTEGER,   -- positive for in, negative for out
            party TEXT,         -- supplier/customer/other
            note TEXT,
            ts TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (item_id) REFERENCES items(id)
        );
    """)

    # Suppliers (Supplier Management)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            contact_person TEXT,
            phone TEXT,
            email TEXT,
            address TEXT,
            product_categories TEXT,
            notes TEXT,
            rating REAL
        );
    """)

    conn.commit()

    # Ensure at least one admin exists
    cur.execute("SELECT COUNT(*) FROM users WHERE role='admin';")
    if cur.fetchone()[0] == 0:
        # default admin: admin / admin
        cur.execute(
            "INSERT OR IGNORE INTO users (username, password, role) VALUES (?,?,?)",
            ("admin", hash_password("admin"), "admin")
        )
        conn.commit()

    conn.close()

def add_user(username, password, role):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO users (username, password, role) VALUES (?,?,?)",
            (username, hash_password(password), role)
        )
        conn.commit()
        return True, "User created"
    except sqlite3.IntegrityError:
        return False, "Username already exists"
    finally:
        conn.close()

def login_user(username, password):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, username, role FROM users WHERE username=? AND password=?",
        (username, hash_password(password))
    )
    row = cur.fetchone()
    conn.close()
    return row

def get_users():
    conn = get_connection()
    df = pd.read_sql_query("SELECT id, username, role FROM users", conn)
    conn.close()
    return df

def update_user_role(user_id, new_role):
    conn = get_connection()
    conn.execute("UPDATE users SET role=? WHERE id=?", (new_role, user_id))
    conn.commit()
    conn.close()

def reset_user_password(user_id, new_password):
    conn = get_connection()
    conn.execute(
        "UPDATE users SET password=? WHERE id=?",
        (hash_password(new_password), user_id)
    )
    conn.commit()
    conn.close()

def delete_user(user_id):
    conn = get_connection()
    conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    conn.close()

# ------------- ITEM MANAGEMENT HELPERS --------------

def get_items():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM items", conn)
    conn.close()
    return df

def create_item(item_code, name, category, unit_price, min_stock, quantity, description):
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO items
               (item_code, name, category, unit_price, min_stock, quantity, description)
               VALUES (?,?,?,?,?,?,?)""",
            (item_code, name, category, unit_price, min_stock, quantity, description)
        )
        conn.commit()
        return True, "Item created"
    except sqlite3.IntegrityError:
        return False, "Item code must be unique"
    finally:
        conn.close()

def update_item(item_id, name, category, unit_price, min_stock, quantity, description):
    conn = get_connection()
    conn.execute(
        """UPDATE items
           SET name=?, category=?, unit_price=?, min_stock=?, quantity=?, description=?
           WHERE id=?""",
        (name, category, unit_price, min_stock, quantity, description, item_id)
    )
    conn.commit()
    conn.close()

def delete_item_record(item_id):
    conn = get_connection()
    conn.execute("DELETE FROM items WHERE id=?", (item_id,))
    conn.commit()
    conn.close()

# ------------- STOCK MANAGEMENT HELPERS -------------

def log_stock_movement(item_id, movement_type, quantity, party, note):
    conn = get_connection()
    conn.execute(
        """INSERT INTO stock_movements
           (item_id, movement_type, quantity, party, note)
           VALUES (?,?,?,?,?)""",
        (item_id, movement_type, quantity, party, note)
    )
    conn.commit()
    conn.close()

def adjust_stock(item_id, delta_qty, movement_type, party="", note=""):
    # Ensure no negative stock
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT quantity FROM items WHERE id=?", (item_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return False, "Item not found"

    current_qty = row[0]
    new_qty = current_qty + delta_qty
    if new_qty < 0:
        conn.close()
        return False, "Operation would result in negative stock"

    cur.execute("UPDATE items SET quantity=? WHERE id=?", (new_qty, item_id))
    conn.commit()
    conn.close()

    # Log movement
    log_stock_movement(item_id, movement_type, delta_qty, party, note)
    return True, "Stock updated"

def get_stock_movements(limit=200):
    conn = get_connection()
    df = pd.read_sql_query(
        """SELECT sm.id, i.item_code, i.name, sm.movement_type,
                  sm.quantity, sm.party, sm.note, sm.ts
           FROM stock_movements sm
           JOIN items i ON sm.item_id = i.id
           ORDER BY sm.ts DESC
           LIMIT ?""",
        conn,
        params=(limit,)
    )
    conn.close()
    return df

# ------------- SUPPLIER MANAGEMENT HELPERS ----------

def get_suppliers():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM suppliers", conn)
    conn.close()
    return df

def create_supplier(name, contact_person, phone, email, address, product_categories, notes, rating):
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO suppliers
               (name, contact_person, phone, email, address,
                product_categories, notes, rating)
               VALUES (?,?,?,?,?,?,?,?)""",
            (name, contact_person, phone, email, address,
             product_categories, notes, rating)
        )
        conn.commit()
        return True, "Supplier created"
    except sqlite3.IntegrityError:
        return False, "Supplier name must be unique"
    finally:
        conn.close()

def update_supplier(
    supplier_id, name, contact_person, phone, email,
    address, product_categories, notes, rating
):
    conn = get_connection()
    conn.execute(
        """UPDATE suppliers
           SET name=?, contact_person=?, phone=?, email=?,
               address=?, product_categories=?, notes=?, rating=?
           WHERE id=?""",
        (name, contact_person, phone, email,
         address, product_categories, notes, rating, supplier_id)
    )
    conn.commit()
    conn.close()

def delete_supplier_record(supplier_id):
    conn = get_connection()
    conn.execute("DELETE FROM suppliers WHERE id=?", (supplier_id,))
    conn.commit()
    conn.close()

# ------------- STREAMLIT APP ------------------------

st.set_page_config(
    page_title="Inventory Management System",
    layout="wide",
    page_icon="📦"
)

create_tables()

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user" not in st.session_state:
    st.session_state.user = None
if "role" not in st.session_state:
    st.session_state.role = None

def require_admin():
    if st.session_state.role != "admin":
        st.warning("Only admin users can perform this action.")
        return False
    return True

# ----------- AUTH SCREENS ------------

if not st.session_state.logged_in:
    col1, col2 = st.columns(2)
    with col1:
        st.header("🔐 Login")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            user = login_user(username, password)
            if user:
                st.session_state.logged_in = True
                st.session_state.user = user[1]
                st.session_state.role = user[2]
                st.success(f"Welcome, {user[1]} ({user[2]})")
                st.experimental_rerun()
            else:
                st.error("Invalid username or password.")

    with col2:
        st.header("📝 Register")
        new_username = st.text_input("New username")
        new_password = st.text_input("New password", type="password")
        new_role = st.selectbox("Role", ["user", "admin"])
        if st.button("Register"):
            ok, msg = add_user(new_username, new_password, new_role)
            if ok:
                st.success("Registration successful. Please login.")
            else:
                st.error(msg)

    st.stop()

# ----------- MAIN APP AFTER LOGIN ------------

st.sidebar.markdown(f"👤 **{st.session_state.user}** (`{st.session_state.role}`)")
if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.session_state.user = None
    st.session_state.role = None
    st.experimental_rerun()

module = st.sidebar.radio(
    "Modules",
    [
        "Dashboard",
        "Item Management",
        "Stock Management",
        "Supplier Management",
        "Dispatch / Sales",
        "Reporting & Analytics",
        "User Management & Authentication",
    ]
)

st.title("📦 Inventory Management System")

# ---------- DASHBOARD ----------
if module == "Dashboard":
    st.subheader("Overview")

    items_df = get_items()

    col_a, col_b, col_c = st.columns(3)
    total_items = len(items_df)
    total_stock = int(items_df["quantity"].sum()) if not items_df.empty else 0
    total_value = float((items_df["quantity"] * items_df["unit_price"]).sum()) if not items_df.empty else 0.0

    col_a.metric("Total Items", total_items)
    col_b.metric("Total Units in Stock", total_stock)
    col_c.metric("Total Inventory Value", f"{total_value:,.2f}")

    if not items_df.empty:
        low_stock_df = items_df[items_df["quantity"] <= items_df["min_stock"]]
        st.markdown("### 🔻 Low Stock Items")
        if low_stock_df.empty:
            st.success("No items below minimum stock level.")
        else:
            st.warning(f"{len(low_stock_df)} item(s) are at or below minimum stock.")
            st.dataframe(
                low_stock_df[["item_code", "name", "quantity", "min_stock"]],
                use_container_width=True
            )

    st.markdown("### Recent Stock Movements")
    movements_df = get_stock_movements(limit=20)
    if movements_df.empty:
        st.info("No stock movements yet.")
    else:
        st.dataframe(movements_df, use_container_width=True)

# ---------- ITEM MANAGEMENT ----------
elif module == "Item Management":
    st.subheader("Item Management Module")

    items_df = get_items()

    tab_list, tab_form = st.tabs(["📋 View Items", "✏️ Add / Edit Item"])

    with tab_list:
        if items_df.empty:
            st.info("No items found.")
        else:
            st.dataframe(items_df, use_container_width=True)

    with tab_form:
        st.markdown("#### Create or Update Item")

        mode = st.radio("Mode", ["Add New Item", "Edit Existing Item"], horizontal=True)

        if mode == "Edit Existing Item" and items_df.empty:
            st.info("No items available to edit. Switch to *Add New Item*.")
        else:
            if mode == "Edit Existing Item":
                item_choice = st.selectbox(
                    "Select Item",
                    items_df["item_code"].tolist()
                )
                selected_row = items_df[items_df["item_code"] == item_choice].iloc[0]
                item_id = selected_row["id"]
                item_code = st.text_input("Item Code", selected_row["item_code"], disabled=True)
                name = st.text_input("Name", selected_row["name"])
                category = st.text_input("Category", selected_row["category"])
                unit_price = st.number_input(
                    "Unit Price",
                    min_value=0.0,
                    value=float(selected_row["unit_price"]),
                    step=0.01
                )
                min_stock = st.number_input(
                    "Minimum Stock Level",
                    min_value=0,
                    value=int(selected_row["min_stock"]),
                    step=1
                )
                quantity = st.number_input(
                    "Current Quantity",
                    min_value=0,
                    value=int(selected_row["quantity"]),
                    step=1
                )
                description = st.text_area("Description", selected_row["description"] or "")

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("💾 Update Item"):
                        if not require_admin():
                            st.stop()
                        update_item(item_id, name, category, unit_price, min_stock, quantity, description)
                        st.success("Item updated successfully.")
                        st.experimental_rerun()
                with col2:
                    if st.button("🗑️ Delete Item"):
                        if not require_admin():
                            st.stop()
                        delete_item_record(item_id)
                        st.success("Item deleted.")
                        st.experimental_rerun()

            else:  # Add new
                item_code = st.text_input("Item Code (unique)")
                name = st.text_input("Name")
                category = st.text_input("Category")
                unit_price = st.number_input("Unit Price", min_value=0.0, step=0.01)
                min_stock = st.number_input("Minimum Stock Level", min_value=0, step=1)
                quantity = st.number_input("Initial Quantity", min_value=0, step=1)
                description = st.text_area("Description")

                if st.button("➕ Create Item"):
                    if not require_admin():
                        st.stop()
                    if not item_code or not name:
                        st.error("Item code and name are required.")
                    else:
                        ok, msg = create_item(
                            item_code, name, category,
                            unit_price, min_stock, quantity, description
                        )
                        if ok:
                            # Log initial stock as adjustment if quantity > 0
                            if quantity > 0:
                                items_df = get_items()
                                new_item = items_df[items_df["item_code"] == item_code].iloc[0]
                                log_stock_movement(
                                    item_id=new_item["id"],
                                    movement_type="INITIAL",
                                    quantity=quantity,
                                    party="SYSTEM",
                                    note="Initial stock"
                                )
                            st.success("Item created successfully.")
                            st.experimental_rerun()
                        else:
                            st.error(msg)

# ---------- STOCK MANAGEMENT ----------
elif module == "Stock Management":
    st.subheader("Stock Management Module")

    items_df = get_items()
    if items_df.empty:
        st.info("No items defined. Please create items first in Item Management.")
    else:
        col_left, col_right = st.columns(2)

        with col_left:
            st.markdown("#### Adjust Stock (Purchase / Adjustment)")
            item_codes = items_df["item_code"].tolist()
            selected_code = st.selectbox("Item", item_codes, key="stock_item")
            row = items_df[items_df["item_code"] == selected_code].iloc[0]

            st.write(f"Current Stock: **{row['quantity']}** units")
            delta = st.number_input("Quantity to Add (+)", min_value=0, step=1)
            movement_type = st.selectbox("Movement Type", ["PURCHASE", "ADJUSTMENT"])
            party = st.text_input("Supplier / Source (optional)")
            note = st.text_area("Note", "Stock update")

            if st.button("✅ Apply Stock Increase"):
                if not require_admin():
                    st.stop()
                if delta <= 0:
                    st.error("Quantity must be greater than zero.")
                else:
                    ok, msg = adjust_stock(row["id"], delta, movement_type, party, note)
                    if ok:
                        st.success(msg)
                        st.experimental_rerun()
                    else:
                        st.error(msg)

        with col_right:
            st.markdown("#### Stock Movements Log")
            movements_df = get_stock_movements(limit=200)
            if movements_df.empty:
                st.info("No stock movements logged yet.")
            else:
                st.dataframe(movements_df, use_container_width=True)

# ---------- SUPPLIER MANAGEMENT ----------
elif module == "Supplier Management":
    st.subheader("Supplier Management Module")

    suppliers_df = get_suppliers()

    tab_list, tab_form = st.tabs(["📋 View Suppliers", "✏️ Add / Edit Supplier"])

    with tab_list:
        if suppliers_df.empty:
            st.info("No suppliers recorded.")
        else:
            st.dataframe(suppliers_df, use_container_width=True)

    with tab_form:
        mode = st.radio("Mode", ["Add New Supplier", "Edit Existing Supplier"], horizontal=True)

        if mode == "Edit Existing Supplier" and suppliers_df.empty:
            st.info("No suppliers to edit.")
        else:
            if mode == "Edit Existing Supplier":
                supplier_name = st.selectbox(
                    "Select Supplier",
                    suppliers_df["name"].tolist()
                )
                row = suppliers_df[suppliers_df["name"] == supplier_name].iloc[0]
                supplier_id = row["id"]

                name = st.text_input("Supplier Name", row["name"])
                contact_person = st.text_input("Contact Person", row["contact_person"] or "")
                phone = st.text_input("Phone", row["phone"] or "")
                email = st.text_input("Email", row["email"] or "")
                address = st.text_area("Address", row["address"] or "")
                product_categories = st.text_area("Product Categories", row["product_categories"] or "")
                notes = st.text_area("Notes", row["notes"] or "")
                rating = st.slider(
                    "Performance Rating",
                    min_value=0.0,
                    max_value=5.0,
                    value=float(row["rating"] or 0.0),
                    step=0.1
                )

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("💾 Update Supplier"):
                        if not require_admin():
                            st.stop()
                        update_supplier(
                            supplier_id, name, contact_person, phone, email,
                            address, product_categories, notes, rating
                        )
                        st.success("Supplier updated.")
                        st.experimental_rerun()
                with col2:
                    if st.button("🗑️ Delete Supplier"):
                        if not require_admin():
                            st.stop()
                        delete_supplier_record(supplier_id)
                        st.success("Supplier deleted.")
                        st.experimental_rerun()
            else:
                name = st.text_input("Supplier Name")
                contact_person = st.text_input("Contact Person")
                phone = st.text_input("Phone")
                email = st.text_input("Email")
                address = st.text_area("Address")
                product_categories = st.text_area("Product Categories (comma separated)")
                notes = st.text_area("Notes")
                rating = st.slider(
                    "Performance Rating",
                    min_value=0.0,
                    max_value=5.0,
                    value=4.0,
                    step=0.1
                )

                if st.button("➕ Create Supplier"):
                    if not require_admin():
                        st.stop()
                    if not name:
                        st.error("Supplier name is required.")
                    else:
                        ok, msg = create_supplier(
                            name, contact_person, phone, email,
                            address, product_categories, notes, rating
                        )
                        if ok:
                            st.success("Supplier created.")
                            st.experimental_rerun()
                        else:
                            st.error(msg)

# ---------- DISPATCH / SALES ----------
elif module == "Dispatch / Sales":
    st.subheader("Dispatch / Sales Module")

    items_df = get_items()

    if items_df.empty:
        st.info("No items available. Please create items first.")
    else:
        col_left, col_right = st.columns(2)

        with col_left:
            st.markdown("#### Create Dispatch / Sales Entry")
            item_code = st.selectbox("Item", items_df["item_code"].tolist())
            row = items_df[items_df["item_code"] == item_code].iloc[0]
            st.write(f"Available Stock: **{row['quantity']}** units")

            qty = st.number_input("Dispatch Quantity", min_value=1, step=1)
            customer = st.text_input("Customer / Department")
            reference = st.text_input("Reference / Invoice No.")
            note = st.text_area("Note", "Dispatch / Sales")

            if st.button("🚚 Dispatch Item"):
                # Users (role 'user') are allowed to dispatch, but stock rules enforced
                delta = -int(qty)
                ok, msg = adjust_stock(
                    row["id"],
                    delta,
                    "DISPATCH",
                    customer,
                    f"{reference} - {note}"
                )
                if ok:
                    st.success("Dispatch recorded and stock updated.")
                    st.experimental_rerun()
                else:
                    st.error(msg)

        with col_right:
            st.markdown("#### Recent Dispatches")
            movements_df = get_stock_movements(limit=200)
            dispatch_df = movements_df[movements_df["movement_type"] == "DISPATCH"]
            if dispatch_df.empty:
                st.info("No dispatch records yet.")
            else:
                st.dataframe(dispatch_df, use_container_width=True)

# ---------- REPORTING & ANALYTICS ----------
elif module == "Reporting & Analytics":
    st.subheader("Reporting and Analytics Module")

    items_df = get_items()
    movements_df = get_stock_movements(limit=1000)

    if items_df.empty:
        st.info("No data available yet.")
    else:
        # Current stock summary
        st.markdown("### 📊 Stock Summary")
        stock_df = items_df[[
            "item_code", "name", "category",
            "quantity", "unit_price", "min_stock"
        ]].copy()
        stock_df["total_value"] = stock_df["quantity"] * stock_df["unit_price"]
        st.dataframe(stock_df, use_container_width=True)

        # Low stock
        low_stock_df = stock_df[stock_df["quantity"] <= stock_df["min_stock"]]
        st.markdown("### 🔻 Low Stock Items")
        if low_stock_df.empty:
            st.success("No low stock items.")
        else:
            st.dataframe(low_stock_df, use_container_width=True)

    if not movements_df.empty:
        # Convert ts to datetime
        try:
            movements_df["ts"] = pd.to_datetime(movements_df["ts"])
        except Exception:
            pass

        st.markdown("### 📅 Daily Dispatch Summary")
        dispatch_df = movements_df[movements_df["movement_type"] == "DISPATCH"].copy()
        if dispatch_df.empty:
            st.info("No dispatch movements to report.")
        else:
            dispatch_df["date"] = dispatch_df["ts"].dt.date
            daily_summary = dispatch_df.groupby("date")["quantity"].sum().reset_index()
            daily_summary["quantity"] = daily_summary["quantity"].abs()
            st.dataframe(daily_summary, use_container_width=True)

        st.markdown("### 🧾 Purchase History")
        purchase_df = movements_df[movements_df["movement_type"] == "PURCHASE"].copy()
        if purchase_df.empty:
            st.info("No purchase movements to report.")
        else:
            st.dataframe(purchase_df, use_container_width=True)

        st.markdown("### ⭐ Supplier Performance (based on purchase records)")
        if not purchase_df.empty:
            supplier_perf = purchase_df.groupby("party")["quantity"].sum().reset_index()
            supplier_perf["quantity"] = supplier_perf["quantity"].abs()
            supplier_perf = supplier_perf.rename(
                columns={"party": "Supplier", "quantity": "Total Units Purchased"}
            )
            st.dataframe(supplier_perf, use_container_width=True)

# ---------- USER MANAGEMENT & AUTH ----------
elif module == "User Management & Authentication":
    st.subheader("User Management and Authentication Module")

    if not require_admin():
        st.stop()

    users_df = get_users()
    st.markdown("### Existing Users")
    st.dataframe(users_df, use_container_width=True)

    st.markdown("### Create New User")
    col1, col2, col3 = st.columns(3)
    with col1:
        u_name = st.text_input("Username", key="um_username")
    with col2:
        u_pass = st.text_input("Password", type="password", key="um_password")
    with col3:
        u_role = st.selectbox("Role", ["user", "admin"], key="um_role")

    if st.button("➕ Create User (Admin Panel)"):
        if not u_name or not u_pass:
            st.error("Username and password are required.")
        else:
            ok, msg = add_user(u_name, u_pass, u_role)
            if ok:
                st.success("User created.")
                st.experimental_rerun()
            else:
                st.error(msg)

    st.markdown("### Modify Existing User")
    if not users_df.empty:
        user_row = st.selectbox(
            "Select User",
            users_df.to_dict("records"),
            format_func=lambda r: f"{r['username']} ({r['role']})"
        )

        new_role = st.selectbox(
            "New Role",
            ["user", "admin"],
            index=0 if user_row["role"] == "user" else 1
        )
        new_password = st.text_input(
            "Reset Password (optional)",
            type="password",
            key="reset_pw"
        )

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("Update Role / Password"):
                update_user_role(user_row["id"], new_role)
                if new_password:
                    reset_user_password(user_row["id"], new_password)
                st.success("User updated.")
                st.experimental_rerun()
        with col2:
            if st.button("Delete User"):
                if user_row["username"] == st.session_state.user:
                    st.error("You cannot delete the currently logged-in user.")
                else:
                    delete_user(user_row["id"])
                    st.success("User deleted.")
                    st.experimental_rerun()
