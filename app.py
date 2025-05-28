import streamlit as st
import pandas as pd
import smtplib
from email.message import EmailMessage
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# --- Configuration ---
GSHEET_URL = "https://docs.google.com/spreadsheets/d/143qPp6BdeGu9qgjMMqZgVmOwqGLablvjw5axtDdWIxQ/edit?gid=0#gid=0"
SHEET_NAME = "DailyData"

# Email setup - IMPORTANT: Store these in Streamlit secrets for production
# For example, in a .streamlit/secrets.toml file:
# [secrets]
# admin_password = "YourAdminPassword"
# sender_email = "your_email@gmail.com"
# sender_app_password = "your_gmail_app_password" # This is crucial for Gmail SMTP
# receiver_email = "receiver_email@example.com"

# Using direct assignment for demonstration, but prefer st.secrets
ADMIN_PASSWORD = "Scorpio143"  # Consider moving this to st.secrets as well
SENDER_EMAIL = "jxrjaxib@gmail.com"
SENDER_PASS = "fqkr ekzp ocfz sgpy" # This should be an App Password, not your regular Gmail password.
RECEIVER_EMAIL = "hafizjazib6@gmail.com"

# Define expected headers for clarity and potential use in get_all_records
EXPECTED_HEADERS = ['date', 'datetime', 'amount', 'currency', 'client', 'paid',
                    'video_name', 'length_min', 'initial_date', 'deadline']

# --- Google Sheets Functions ---
@st.cache_resource(ttl=3600) # Cache the client for 1 hour to avoid re-authenticating frequently
def get_gsheet_client():
    """Initializes and returns a gspread client using Streamlit secrets."""
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    try:
        # If deploying to Streamlit Cloud, configure st.secrets["gcp_service_account"]
        # local testing might require a service_account.json file path
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Failed to authenticate with Google Sheets. Check 'gcp_service_account' in secrets: {e}")
        st.stop()

def load_video_data():
    """Loads video data from the Google Sheet into a pandas DataFrame."""
    try:
        client = get_gsheet_client()
        sheet = client.open_by_url(GSHEET_URL).worksheet(SHEET_NAME)
        
        # Get all records with expected headers
        data = sheet.get_all_records(expected_headers=EXPECTED_HEADERS)
        
        df = pd.DataFrame(data)
        
        # Ensure only expected columns are present and in order
        df = df[EXPECTED_HEADERS] 

        # Type conversions
        df['paid'] = df['paid'].apply(lambda x: True if str(x).lower() in ['true', 'yes', '1'] else False)
        
        # Coerce non-numeric to NaN, then fill NaN with 0.0
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0.0)
        df['length_min'] = pd.to_numeric(df['length_min'], errors='coerce').fillna(0.0)

        # Convert date columns to date objects, coercing errors to NaT
        df['date'] = pd.to_datetime(df['date'], errors='coerce').dt.date 
        df['initial_date'] = pd.to_datetime(df['initial_date'], errors='coerce').dt.date
        df['deadline'] = pd.to_datetime(df['deadline'], errors='coerce').dt.date
        
        # Convert datetime column to datetime objects
        df['datetime'] = pd.to_datetime(df['datetime'], errors='coerce')
        
        return df
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"Worksheet '{SHEET_NAME}' not found in the spreadsheet. Please check the SHEET_NAME variable.")
        return pd.DataFrame(columns=EXPECTED_HEADERS) # Return empty DF with expected columns
    except Exception as e:
        st.error(f"Error loading video data from Google Sheet. Ensure sheet URL, name, and service account permissions are correct. Error: {e}")
        return pd.DataFrame(columns=EXPECTED_HEADERS) # Return empty DF on error

def save_video_entry(amount, currency, client, paid, video_name, length_min, initial_date, deadline):
    """Saves a new video entry to the Google Sheet and sends an email notification."""
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    
    new_entry_dict = {
        "date": today,
        "datetime": timestamp,
        "amount": amount,
        "currency": currency,
        "client": client if client else "Unknown",
        "paid": paid,
        "video_name": video_name,
        "length_min": length_min if currency == "PKR" else 0.0, # Only save length_min for PKR
        "initial_date": initial_date,
        "deadline": deadline
    }

    try:
        client_gs = get_gsheet_client()
        spreadsheet = client_gs.open_by_url(GSHEET_URL)
        sheet = spreadsheet.worksheet(SHEET_NAME)
        
        new_entry_values = []
        for col in EXPECTED_HEADERS:
            value = new_entry_dict[col]
            if isinstance(value, datetime):
                new_entry_values.append(value.strftime("%Y-%m-%d %H:%M:%S"))
            elif isinstance(value, datetime.date):
                new_entry_values.append(value.strftime("%Y-%m-%d"))
            else:
                new_entry_values.append(value)

        sheet.append_row(new_entry_values, value_input_option='USER_ENTERED')
        
        st.success("Video entry added successfully!")
        
        subject = "📥 New Video Entry Added"
        content = f"""New entry added:

Date: {today}
Time: {timestamp}
Client: {client}
Video Name: {video_name}
Amount: {currency} {amount}
Length: {length_min} min
Paid: {'Yes' if paid else 'No'}
Initial Date: {initial_date}
Deadline: {deadline}
"""
        send_notification_email(subject, content)
        rerun() # Rerun to clear form and refresh data after successful submission
    except Exception as e:
        st.error(f"Failed to save video entry or send email: {e}")

def update_entire_sheet(df_to_update):
    """Updates the entire Google Sheet with the content of a DataFrame."""
    try:
        client = get_gsheet_client()
        sheet = client.open_by_url(GSHEET_URL).worksheet(SHEET_NAME)
        
        # Clear the entire sheet content (headers and data)
        sheet.clear()
        
        df_for_gsheet = df_to_update.copy()
        
        # Convert date and datetime objects back to string format for GSheets
        for col in ['date', 'initial_date', 'deadline']:
            df_for_gsheet[col] = df_for_gsheet[col].apply(lambda x: x.strftime("%Y-%m-%d") if pd.notna(x) else '')
        
        df_for_gsheet['datetime'] = df_for_gsheet['datetime'].apply(lambda x: x.strftime("%Y-%m-%d %H:%M:%S") if pd.notna(x) else '')
        
        # Convert boolean to string 'TRUE'/'FALSE' for GSheets
        df_for_gsheet['paid'] = df_for_gsheet['paid'].apply(lambda x: 'TRUE' if x else 'FALSE')

        # Ensure correct column order before updating
        df_to_write = df_for_gsheet[EXPECTED_HEADERS]
        data_to_write = [df_to_write.columns.values.tolist()] + df_to_write.values.tolist()
        
        # Update the sheet starting from A1
        sheet.update(data_to_write, value_input_option='USER_ENTERED')
        st.success("Sheet updated successfully.")
    except Exception as e:
        st.error(f"Failed to update Google Sheet: {e}")

# --- Email Functions ---
def send_notification_email(subject, content):
    """Sends an email notification."""
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = SENDER_EMAIL
        msg["To"] = RECEIVER_EMAIL
        msg.set_content(content)
        
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(SENDER_EMAIL, SENDER_PASS)
            smtp.send_message(msg)
    except Exception as e:
        st.warning(f"Email sending failed: {e}. Please check SENDER_EMAIL, SENDER_PASS (App Password), and internet connection.")

# --- Utility Functions ---
def get_month_name(date_str):
    """Converts a date string (YYYY-MM-DD) to a Month Year format (e.g., "January 2023")."""
    try:
        # Ensure date_str is a string for datetime.strptime
        return datetime.strptime(str(date_str), "%Y-%m-%d").strftime("%B %Y") 
    except:
        return "Unknown"

def extract_time(datetime_obj):
    """Extracts time (e.g., "9:30pm") from a datetime object."""
    try:
        if pd.isna(datetime_obj): # Check for NaT (Not a Time)
            return "Time Unknown"
        return datetime_obj.strftime("%I:%M%p").lower().lstrip("0")
    except:
        return "Time Unknown"

def rerun():
    """Forces Streamlit to rerun the script immediately."""
    # This toggles a dummy session state variable to force a rerun
    st.session_state["__rerun_flag__"] = not st.session_state.get("__rerun_flag__", False)
    st.rerun()

def format_text(date, amount, currency, client, video_name, length_min, paid, initial, deadline, time_str):
    """Formats video entry details for display with HTML."""
    client_fmt = f"<b style='color: lightgreen;'>{client}</b>"
    video_fmt = f"<b style='color: deepskyblue;'>{video_name}</b>"
    amount_fmt = f"<b style='color: #FFD700;'>{currency} {amount:.2f}</b>"
    length_fmt = f"{length_min:.1f} min" if length_min and length_min > 0 else "N/A"
    paid_status = "✅ Paid" if paid else "❌ Not Paid"
    
    date_str = date.strftime("%Y-%m-%d") if pd.notna(date) else "N/A"
    initial_str = initial.strftime("%Y-%m-%d") if pd.notna(initial) else "N/A"
    deadline_str = deadline.strftime("%Y-%m-%d") if pd.notna(deadline) else "N/A"

    return f"""
    <div style='line-height: 1.6; border-bottom: 1px solid #333; padding-bottom: 5px; margin-bottom: 5px;'>
        <b style='color: lightgrey;'>{time_str}</b> | {amount_fmt} | Client: {client_fmt} | Video: {video_fmt} | Length: <span style='color: silver;'>{length_fmt}</span> | {paid_status} <br>
        <small style='color: grey;'>Initial Date: {initial_str} | Deadline: {deadline_str}</small>
    </div>
    """

# --- Main Streamlit Application ---
def main():
    st.set_page_config(layout="wide", page_title="Buraaq Studios Analysis")
    st.title("🎬 Buraaq Studios Analysis")

    # Initialize session states if not already present
    if 'admin_mode' not in st.session_state:
        st.session_state.admin_mode = False
    if 'edit_index' not in st.session_state:
        st.session_state.edit_index = None
    if '__rerun_flag__' not in st.session_state: 
        st.session_state['__rerun_flag__'] = False

    # Load data from Google Sheet
    df = load_video_data()

    # --- Sidebar for Unpaid Videos and Admin Login ---
    with st.sidebar:
        st.header("🧾 Unpaid PKR Videos")
        unpaid_pkr = df[(df['currency'] == "PKR") & (~df['paid'])]
        paid_changed = False 

        if unpaid_pkr.empty:
            st.info("All PKR videos are marked as paid.")
        else:
            # Iterate using iterrows for row access, but update df using .at[] with original index
            for i, row in unpaid_pkr.iterrows():
                label = f"{row['date']} | {row['amount']} PKR | Client: {row['client']} | Video: {row['video_name']} | Length: {row['length_min']} min"
                paid_new = st.checkbox(label, value=False, key=f"unpaid_paid_chk_pkr_{row.name}") 
                if paid_new:
                    df.at[row.name, 'paid'] = True # Use .at[] with original index for DataFrame update
                    paid_changed = True

        st.header("💵 Unpaid USD Videos")
        unpaid_usd = df[(df['currency'] == "USD") & (~df['paid'])]
        if unpaid_usd.empty:
            st.info("All USD videos are marked as paid.")
        else:
            for i, row in unpaid_usd.iterrows():
                label = f"{row['date']} | ${row['amount']:.2f} | Client: {row['client']} | Video: {row['video_name']}"
                paid_new = st.checkbox(label, value=False, key=f"unpaid_paid_chk_usd_{row.name}")
                if paid_new:
                    df.at[row.name, 'paid'] = True
                    paid_changed = True

        if paid_changed:
            update_entire_sheet(df) # Update the GSheet with the modified df
            rerun() # Rerun to reflect changes and potentially re-fetch data

        with st.expander("🔐 Admin Login"):
            if not st.session_state.admin_mode:
                pwd = st.text_input("Enter admin password:", type="password", key="admin_pwd_input")
                if st.button("Login as Admin", key="admin_login_btn"):
                    if pwd == ADMIN_PASSWORD:
                        st.session_state.admin_mode = True
                        st.success("Logged in as admin.")
                        rerun()
                    else:
                        st.error("Incorrect password.")
            else:
                st.info("Currently logged in as admin.")
                if st.button("Logout Admin", key="admin_logout_btn"):
                    st.session_state.admin_mode = False
                    st.session_state.edit_index = None # Clear edit state on logout
                    st.success("Logged out.")
                    rerun()

    # --- Main content area: Menu Navigation ---
    menu_options = ["Submit Video", "View Monthly Breakdown"]
    if st.session_state.admin_mode:
        menu_options.append("Admin: Edit Entries")
    
    choice = st.selectbox("Menu", menu_options, key="main_menu_select")

    # --- Submit Video Section ---
    if choice == "Submit Video":
        st.subheader("Add New Video Earning Entry")
        
        # KEY CHANGE: Move currency selection OUTSIDE the form
        # This allows immediate rerun and dynamic display of PKR fields
        currency = st.selectbox("Select Currency", ["USD", "PKR"], key="currency_select_main") 
        
        with st.form("new_video_entry_form"):
            # Now, `currency` is already defined from the selectbox above,
            # and changes to it will trigger a rerun of the app, instantly updating the form.
            client = st.text_input("Enter Client Name (optional)", key="client_name_input")
            paid = st.checkbox("Mark as Paid", key="paid_checkbox")
            
            video_name_label = "Enter Video Name (optional)" if currency == "USD" else "Enter Video Name"
            video_name = st.text_input(video_name_label, key="video_name_input")
            
            today_date = datetime.today().date()
            initial_date = st.date_input("Initial Date", value=today_date, key="initial_date_input")
            deadline = st.date_input("Deadline", value=today_date, key="deadline_date_input")
            
            length_min = 0.0 # Default value
            amount = 0.0     # Default value

            # Conditional rendering of inputs based on the currency value
            if currency == "PKR":
                length_min = st.number_input("Enter Video Length (minutes)", min_value=0.0, step=0.1, key="length_min_input")
                pkr_per_minute = st.number_input("Enter PKR per minute rate (optional)", min_value=0.0, step=0.1, key="pkr_rate_input")
                
                # Calculate amount if rate and length are provided, else allow manual input
                if pkr_per_minute > 0 and length_min > 0:
                    amount = length_min * pkr_per_minute
                    st.markdown(f"**Calculated Video Amount:** {amount:.2f} PKR")
                else:
                    amount = st.number_input("Enter Video Amount (PKR)", min_value=0.0, step=0.01, key="pkr_amount_input")
            else: # USD
                amount = st.number_input("Enter Video Amount (USD)", min_value=0.0, step=0.01, key="usd_amount_input")

            # Submit button for the form
            submitted = st.form_submit_button("Add Entry")

            if submitted:
                # Validation logic for form submission
                if currency == "PKR":
                    if length_min <= 0:
                        st.error("For PKR videos, please enter video length greater than zero.")
                        st.stop() # Stop execution until user corrects
                    if amount <= 0:
                        st.error("For PKR videos, please enter a valid amount (either calculated or entered manually).")
                        st.stop()
                    if not video_name.strip():
                        st.error("Please enter the video name for PKR videos.")
                        st.stop()
                elif currency == "USD":
                    if amount <= 0:
                        st.error("For USD videos, please enter an amount greater than zero.")
                        st.stop()
                    if not video_name.strip():
                        st.warning("It's recommended to enter a video name for USD entries.")
                
                # Call save function if validation passes
                save_video_entry(amount, currency, client, paid, video_name, length_min,
                                 initial_date.strftime("%Y-%m-%d"), deadline.strftime("%Y-%m-%d"))
                # Rerun is called inside save_video_entry upon successful save

    # --- View Monthly Breakdown Section ---
    elif choice == "View Monthly Breakdown":
        st.subheader("📆 Monthly Video & Earnings Breakdown")
        if df.empty:
            st.info("No video data submitted yet. Please add entries via 'Submit Video'.")
        else:
            # Create 'month' column for grouping
            df['month'] = df['date'].apply(get_month_name)
            
            # Client filter for breakdown
            clients = sorted(df['client'].dropna().unique().tolist())
            selected_client_breakdown = st.selectbox("Filter by Client", ["All"] + clients, key="client_filter_select_breakdown")
            
            filtered_df_breakdown = df[df['client'] == selected_client_breakdown] if selected_client_breakdown != "All" else df

            # Helper to check if month format is valid for sorting
            def is_valid_month_format(m):
                try:
                    datetime.strptime(m, "%B %Y")
                    return True
                except:
                    return False

            # Get unique months and sort them descending (most recent first)
            months = [m for m in filtered_df_breakdown['month'].unique() if is_valid_month_format(m)]
            months_sorted = sorted(months, key=lambda m: datetime.strptime(m, "%B %Y"), reverse=True)

            if not months_sorted:
                st.info("No valid monthly data found for the selected filter.")
                return

            # Display data for each month
            for month in months_sorted:
                monthly_data = filtered_df_breakdown[filtered_df_breakdown['month'] == month]
                
                # Group by currency within each month
                for curr in monthly_data['currency'].unique():
                    currency_data = monthly_data[monthly_data['currency'] == curr]
                    
                    total_currency_monthly = currency_data['amount'].sum()
                    paid_total = currency_data[currency_data['paid']]['amount'].sum()
                    unpaid_total = total_currency_monthly - paid_total
                    
                    # Expander for each month/currency summary
                    with st.expander(f"📅 {month} — {curr} Total: {total_currency_monthly:.2f} | Earned: {paid_total:.2f} | To be Paid: {unpaid_total:.2f}"):
                        days = sorted(currency_data['date'].unique(), reverse=True) # Sort days descending
                        if not days:
                            st.info("No entries for this month/currency combination.")
                            continue

                        selected_day = st.selectbox("Select a date to view details", days, key=f"day_select_{month}_{curr}")
                        
                        day_data = currency_data[currency_data['date'] == selected_day]
                        total_day = day_data['amount'].sum()
                        
                        st.markdown(f"### 🗓️ {selected_day} — {len(day_data)} videos — {curr} {total_day:.2f}")
                        
                        # Sort daily data by datetime descending (latest time first)
                        day_data_sorted = day_data.sort_values(by='datetime', ascending=False)

                        for i, row in day_data_sorted.iterrows():
                            time_str = extract_time(row['datetime'])
                            formatted = format_text(row['date'], row['amount'], row['currency'], row['client'], row['video_name'],
                                                    row['length_min'], row['paid'], row['initial_date'], row['deadline'], time_str)
                            st.markdown(formatted, unsafe_allow_html=True)

    # --- Admin: Edit Entries Section ---
    elif choice == "Admin: Edit Entries":
        if not st.session_state.admin_mode:
            st.warning("Please log in as admin to access this section.")
            return

        st.subheader("⚙️ Admin: Edit Video Entries")
        if df.empty:
            st.info("No video data available to edit.")
            return

        # Client Filter for Edit Entries
        clients = sorted(df['client'].dropna().unique().tolist())
        selected_client_edit = st.selectbox("Filter by Client", ["All"] + clients, key="client_filter_select_edit")
        
        # Apply client filter to create the DataFrame for display
        display_df = df[df['client'] == selected_client_edit] if selected_client_edit != "All" else df

        # Sorting Options for Edit Entries
        # Exclude 'datetime' as it might be too granular for a primary sort selection
        # and 'month' as it's a derived column for display.
        sort_columns_options = [col for col in EXPECTED_HEADERS if col not in ['datetime']] 
        
        # Find the index of 'date' if it exists, otherwise default to 0
        default_sort_idx = 0
        if 'date' in sort_columns_options:
            default_sort_idx = sort_columns_options.index('date')

        selected_sort_column = st.selectbox(
            "Sort by Column", 
            sort_columns_options, 
            index=default_sort_idx, # Default to sorting by date
            key="sort_column_edit"
        )
        sort_order = st.radio("Sort Order", ["Descending", "Ascending"], index=0, key="sort_order_edit")
        
        # Apply sorting to the display_df
        if not display_df.empty:
            ascending = True if sort_order == "Ascending" else False
            try:
                # Ensure sort is stable if multiple rows have the same value for the primary sort column
                # By adding 'datetime' as a secondary sort key
                if selected_sort_column != 'datetime' and 'datetime' in display_df.columns:
                     display_df = display_df.sort_values(by=[selected_sort_column, 'datetime'], ascending=[ascending, False], ignore_index=False)
                else:
                    display_df = display_df.sort_values(by=selected_sort_column, ascending=ascending, ignore_index=False)

            except TypeError:
                st.warning(f"Cannot sort by '{selected_sort_column}' due to mixed data types in column. Showing unsorted.")
            except KeyError:
                st.warning(f"Sort column '{selected_sort_column}' not found. Showing unsorted.")


        st.write("Edit the table below directly:")
        # The key is important here for data_editor to maintain state
        edited_df_result = st.data_editor(
            display_df, # Pass the filtered AND sorted DataFrame for display
            key="admin_data_editor",
            column_config={
                "date": st.column_config.DateColumn("Date", format="YYYY-MM-DD", help="Date of entry"),
                "datetime": st.column_config.DatetimeColumn("Timestamp", format="YYYY-MM-DD HH:mm:ss", help="Exact time of entry"),
                "amount": st.column_config.NumberColumn("Amount", format="%.2f", help="Earning amount"),
                "currency": st.column_config.SelectboxColumn("Currency", options=["PKR", "USD"], help="Currency of earning"),
                "client": st.column_config.TextColumn("Client", help="Name of the client"),
                "paid": st.column_config.CheckboxColumn("Paid", help="Has the payment been received?"),
                "video_name": st.column_config.TextColumn("Video Name", help="Name or description of the video"),
                "length_min": st.column_config.NumberColumn("Length (min)", format="%.1f", help="Video length in minutes (primarily for PKR)"),
                "initial_date": st.column_config.DateColumn("Initial Date", format="YYYY-MM-DD", help="Date work started"),
                "deadline": st.column_config.DateColumn("Deadline", format="YYYY-MM-DD", help="Date work is due")
            },
            num_rows="dynamic", # Allows adding/deleting rows directly in the editor
            hide_index=True
        )

        if st.button("Save Changes to Sheet", key="save_admin_changes_btn"):
            # Get changes from the data_editor's session state
            # These dictionaries/sets refer to the original DataFrame's indices
            edited_rows = st.session_state["admin_data_editor"]["edited_rows"]
            added_rows = st.session_state["admin_data_editor"]["added_rows"]
            deleted_rows = st.session_state["admin_data_editor"]["deleted_rows"]

            updated_df = df.copy() # Start with a fresh copy of the original full DataFrame

            # 1. Handle Deletions: Drop rows by their original index
            if deleted_rows:
                # Convert set to list for .drop() if needed, though .drop() usually handles sets
                updated_df = updated_df.drop(index=list(deleted_rows))
                st.info(f"Deleted {len(deleted_rows)} rows.")

            # 2. Handle Edits: Apply changes to specific cells by original index
            for idx, changes in edited_rows.items():
                for col, value in changes.items():
                    if col in ['date', 'initial_date', 'deadline']:
                        if isinstance(value, str):
                            try:
                                updated_df.at[idx, col] = datetime.strptime(value, "%Y-%m-%d").date()
                            except ValueError:
                                st.warning(f"Invalid date format for row {idx}, column {col}: '{value}'. Skipping update for this cell.")
                                continue 
                        else: # Assume it's already a date object
                            updated_df.at[idx, col] = value
                    elif col == 'datetime':
                        if isinstance(value, str):
                            try:
                                updated_df.at[idx, col] = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
                            except ValueError:
                                st.warning(f"Invalid datetime format for row {idx}, column {col}: '{value}'. Skipping update for this cell.")
                                continue
                        else: # Assume it's already a datetime object
                            updated_df.at[idx, col] = value
                    elif col == 'paid': 
                        updated_df.at[idx, col] = bool(value) # Ensure boolean type
                    elif col in ['amount', 'length_min']: 
                        # FIX: Handle potential NaN from to_numeric correctly
                        numeric_val = pd.to_numeric(value, errors='coerce')
                        if pd.isna(numeric_val): # Check if it's NaN after conversion
                            updated_df.at[idx, col] = 0.0 # Assign 0.0 if it's NaN
                        else:
                            updated_df.at[idx, col] = numeric_val # Assign the converted numeric value
                    else:
                        updated_df.at[idx, col] = value
            
            if edited_rows:
                st.info(f"Edited {len(edited_rows)} rows.")

            # 3. Handle Additions: Concatenate new rows
            if added_rows:
                added_df = pd.DataFrame(added_rows)
                # Ensure correct dtypes for newly added rows to avoid issues during update_entire_sheet
                added_df['paid'] = added_df['paid'].astype(bool)
                added_df['amount'] = pd.to_numeric(added_df['amount'], errors='coerce').fillna(0.0)
                added_df['length_min'] = pd.to_numeric(added_df['length_min'], errors='coerce').fillna(0.0)
                
                # Convert date columns for added rows
                for col in ['date', 'initial_date', 'deadline']:
                    added_df[col] = pd.to_datetime(added_df[col], errors='coerce').dt.date
                added_df['datetime'] = pd.to_datetime(added_df['datetime'], errors='coerce')
                
                # Fill any potentially missing columns in added_df with defaults if they weren't entered
                for col in EXPECTED_HEADERS:
                    if col not in added_df.columns:
                        if col in ['amount', 'length_min']: added_df[col] = 0.0
                        elif col == 'paid': added_df[col] = False
                        elif col in ['date', 'initial_date', 'deadline']: added_df[col] = datetime.now().date()
                        elif col == 'datetime': added_df[col] = datetime.now()
                        else: added_df[col] = '' 

                added_df = added_df[EXPECTED_HEADERS] # Ensure order for consistency before concat
                updated_df = pd.concat([updated_df, added_df], ignore_index=True)
                st.info(f"Added {len(added_rows)} new rows.")

            # Only attempt to save if there were actual changes
            if edited_rows or added_rows or deleted_rows:
                try:
                    update_entire_sheet(updated_df)
                    st.success("Changes saved successfully!")
                    rerun() # Rerun to refresh the displayed data with the latest from GSheet
                except Exception as e:
                    st.error(f"Error saving changes: {e}")
                    st.warning("Please ensure all entries have valid data types (e.g., numbers for amount/length, correct date formats) and all required columns are present.")
            else:
                st.info("No changes to save.")


if __name__ == "__main__":
    main()
