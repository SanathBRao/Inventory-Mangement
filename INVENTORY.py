import streamlit as st
import pandas as pd
from io import StringIO

st.set_page_config(
    page_title="Inventory Management",
    page_icon="📦",
    layout="wide"
)

# ---------- Helpers ----------
def init_inventory():
    if "inventory" not in st.session_state:
        st.session_state.inventory = pd.DataFrame(
            columns=[
                "Item ID",
                "Name",
                "Category",
                "Quantity",
                "Unit Price",
                "Location"
            ]
        ).astype({
            "Quantity": "int64",
            "Unit Price": "float64"
        })


def generate_item_id():
    """Generate a simple incremental Item ID like ITM-0001."""
    df = st.session_state.inventory
    if df.empty:
        return "ITM-0001"
    existing_ids = df["Item ID"].str.replace("ITM-", "").astype(int)
    next_num = existing_ids.max() + 1
    return f"ITM-{next_num:04d}"


def add_or_update_item(item_id, name, category, quantity, price, location):
    df = st.session_state.inventory

    if item_id in df["Item ID"].values:
        # Update existing
        st.session_state.inventory.loc[
            st.session_state.inventory["Item ID"] == item_id,
            ["Name", "Category", "Quantity", "Unit Price", "Location"]
        ] = [name, category, quantity, price, location]
        st.success(f"Updated item {item_id}")
    else:
        # Add new
        new_row = {
            "Item ID": item_id,
            "Name": name,
            "Category": category,
            "Quantity": quantity,
            "Unit Price": price,
            "Location": location,
        }
        st.session_state.inventory = pd.concat(
            [df, pd.DataFrame([new_row])],
            ignore_index=True
        )
        st.success(f"Added new item {item_id}")


def delete_item(item_id):
    df = st.session_state.inventory
    st.session_state.inventory = df[df["Item ID"] != item_id].reset_index(drop=True)
    st.success(f"Deleted item {item_id}")


# ---------- Initialize ----------
init_inventory()

st.title("📦 Inventory Management Dashboard")

# ---------- Sidebar ----------
st.sidebar.header("⚙️ Settings & Data")

# Import CSV
uploaded_file = st.sidebar.file_uploader(
    "Import inventory from CSV",
    type=["csv"],
    help="CSV must have columns: Item ID, Name, Category, Quantity, Unit Price, Location"
)

if uploaded_file is not None:
    try:
        csv_data = pd.read_csv(uploaded_file)
        required_cols = ["Item ID", "Name", "Category", "Quantity", "Unit Price", "Location"]
        if all(col in csv_data.columns for col in required_cols):
            st.session_state.inventory = csv_data[required_cols]
            st.sidebar.success("Inventory loaded from CSV.")
        else:
            st.sidebar.error(f"CSV missing required columns: {required_cols}")
    except Exception as e:
        st.sidebar.error(f"Error reading CSV: {e}")

# Download CSV
if not st.session_state.inventory.empty:
    csv_buffer = StringIO()
    st.session_state.inventory.to_csv(csv_buffer, index=False)
    st.sidebar.download_button(
        label="📥 Download inventory as CSV",
        data=csv_buffer.getvalue(),
        file_name="inventory_export.csv",
        mime="text/csv",
    )

st.sidebar.markdown("---")
low_stock_threshold = st.sidebar.number_input(
    "Low stock threshold",
    min_value=0,
    value=5,
    step=1,
    help="Items with quantity <= this value are considered low stock."
)

# ---------- Main Tabs ----------
tab_manage, tab_view, tab_low = st.tabs(
    ["➕ Add / Edit Item", "📋 View Inventory", "⚠️ Low Stock"]
)

# ---------- Tab: Add / Edit ----------
with tab_manage:
    st.subheader("Add or Edit Item")

    col_left, col_right = st.columns(2)

    with col_left:
        mode = st.radio(
            "Mode",
            ["Add New Item", "Edit Existing Item"],
            horizontal=True
        )

    df = st.session_state.inventory

    if mode == "Edit Existing Item" and df.empty:
        st.info("Inventory is empty. Switch to **Add New Item** to create your first item.")

    if mode == "Add New Item":
        col1, col2, col3 = st.columns(3)

        with col1:
            item_id = st.text_input(
                "Item ID",
                value=generate_item_id(),
                help="You can change this if you want a custom ID.",
            )
            name = st.text_input("Name")

        with col2:
            category = st.text_input("Category")
            quantity = st.number_input(
                "Quantity",
                min_value=0,
                step=1,
                value=0
            )

        with col3:
            price = st.number_input(
                "Unit Price",
                min_value=0.0,
                step=0.01,
                value=0.0,
                format="%.2f"
            )
            location = st.text_input("Location", placeholder="e.g., Rack A / Store Room")

        if st.button("💾 Save Item", type="primary"):
            if not name:
                st.error("Name is required.")
            else:
                add_or_update_item(item_id, name, category, quantity, price, location)

    else:  # Edit Existing
        if not df.empty:
            selected_id = st.selectbox(
                "Select Item ID to edit",
                df["Item ID"].tolist()
            )

            item_row = df[df["Item ID"] == selected_id].iloc[0]

            col1, col2, col3 = st.columns(3)

            with col1:
                item_id = st.text_input("Item ID", value=item_row["Item ID"], disabled=True)
                name = st.text_input("Name", value=item_row["Name"])

            with col2:
                category = st.text_input("Category", value=item_row["Category"])
                quantity = st.number_input(
                    "Quantity",
                    min_value=0,
                    step=1,
                    value=int(item_row["Quantity"])
                )

            with col3:
                price = st.number_input(
                    "Unit Price",
                    min_value=0.0,
                    step=0.01,
                    value=float(item_row["Unit Price"]),
                    format="%.2f"
                )
                location = st.text_input(
                    "Location",
                    value=str(item_row["Location"])
                )

            col_save, col_delete = st.columns(2)

            with col_save:
                if st.button("💾 Update Item", type="primary"):
                    if not name:
                        st.error("Name is required.")
                    else:
                        add_or_update_item(item_id, name, category, quantity, price, location)

            with col_delete:
                if st.button("🗑️ Delete Item"):
                    delete_item(item_id)
        else:
            st.warning("No items to edit.")

# ---------- Tab: View Inventory ----------
with tab_view:
    st.subheader("Inventory Overview")

    df = st.session_state.inventory.copy()

    if df.empty:
        st.info("No items in inventory yet.")
    else:
        # Filters
        with st.expander("🔍 Filters", expanded=False):
            col_f1, col_f2, col_f3 = st.columns(3)

            with col_f1:
                category_filter = st.text_input("Filter by category (contains)")
            with col_f2:
                location_filter = st.text_input("Filter by location (contains)")
            with col_f3:
                min_qty = st.number_input(
                    "Min quantity",
                    min_value=0,
                    value=0,
                    step=1
                )

        if category_filter:
            df = df[df["Category"].str.contains(category_filter, case=False, na=False)]
        if location_filter:
            df = df[df["Location"].str.contains(location_filter, case=False, na=False)]
        df = df[df["Quantity"] >= min_qty]

        # Add total value column
        df["Total Value"] = df["Quantity"] * df["Unit Price"]

        st.metric(
            "Total Inventory Value",
            f"{df['Total Value'].sum():,.2f}"
        )

        st.dataframe(
            df.reset_index(drop=True),
            use_container_width=True
        )

# ---------- Tab: Low Stock ----------
with tab_low:
    st.subheader("⚠️ Low Stock Items")

    df = st.session_state.inventory
    if df.empty:
        st.info("No items in inventory.")
    else:
        low_df = df[df["Quantity"] <= low_stock_threshold].copy()
        if low_df.empty:
            st.success("No items are currently below the low stock threshold.")
        else:
            st.warning(f"{len(low_df)} item(s) are at or below the threshold ({low_stock_threshold}).")
            st.dataframe(low_df.reset_index(drop=True), use_container_width=True)
