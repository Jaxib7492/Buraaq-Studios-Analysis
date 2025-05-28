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
        'https://www.googleapis.com/auth/drive' # Needed for some gspread operations
    ]
    try:
        # Ensure 'gcp_service_account' is correctly configured in Streamlit secrets
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Failed to authenticate with Google Sheets. Check 'gcp_service_account' in secrets: {e}")
        st.stop() # Stop the app if authentication fails

def load_video_data():
    """Loads video data from the Google Sheet into a pandas DataFrame."""
    try:
        client = get_gsheet_client()
        sheet = client.open_by_url(GSHEET_URL).worksheet(SHEET_NAME)
        
        # Use get_all_records with expected_headers for robustness against unexpected sheet headers
        # This will map data based on the expected_headers list.
        data = sheet.get_all_records(expected_headers=EXPECTED_HEADERS)
        
        df = pd.DataFrame(data)
        
        # Ensure columns are in the correct order and have proper data types
        df = df[EXPECTED_HEADERS] # Reorder columns to match expected
        df['paid'] = df['paid'].astype(bool)
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0.0)
        df['length_min'] = pd.to_numeric(df['length_min'], errors='coerce').fillna(0.0)
        
        return df
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"Worksheet '{SHEET_NAME}' not found in the spreadsheet. Please check the SHEET_NAME variable.")
        return pd.DataFrame(columns=EXPECTED_HEADERS)
    except Exception as e:
        st.error(f"Error loading video data from Google Sheet. Ensure sheet URL, name, and service account permissions are correct. Error: {e}")
        return pd.DataFrame(columns=EXPECTED_HEADERS) # Return empty DataFrame on failure

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
        "length_min": length_min if currency == "PKR" else 0.0, # length_min only for PKR
        "initial_date": initial_date,
        "deadline": deadline
    }

    try:
        client_gs = get_gsheet_client()
        spreadsheet = client_gs.open_by_url(GSHEET_URL)
        sheet = spreadsheet.worksheet(SHEET_NAME)
        
        # Convert dict to list based on EXPECTED_HEADERS order
        new_entry_values = [new_entry_dict[col] for col in EXPECTED_HEADERS]
        
        # Append the new entry as a row
        sheet.append_row(new_entry_values, value_input_option='USER_ENTERED')
        
        st.success("Video entry added successfully!")
        
        # Send notification email
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
    except Exception as e:
        st.error(f"Failed to save video entry or send email: {e}")

def update_entire_sheet(df_to_update):
    """Updates the entire Google Sheet with the content of a DataFrame."""
    try:
        client = get_gsheet_client()
        sheet = client.open_by_url(GSHEET_URL).worksheet(SHEET_NAME)
        
        # Clear existing data and then write the updated DataFrame
        # This is a full overwrite, so it's efficient for moderate sheet sizes.
        sheet.clear()
        
        # Convert DataFrame to a list of lists, including headers
        # Ensure column order matches EXPECTED_HEADERS
        df_to_write = df_to_update[EXPECTED_HEADERS]
        data_to_write = [df_to_write.columns.values.tolist()] + df_to_write.values.tolist()
        
        sheet.update(data_to_write, value_input_option='USER_ENTERED')
        st.success("Sheet updated successfully (paid status changes applied).")
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
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%B %Y")
    except:
        return "Unknown"

def extract_time(datetime_str):
    """Extracts time (e.g., "9:30pm") from a datetime string (YYYY-MM-DD HH:MM:SS)."""
    try:
        dt = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%I:%M%p").lower().lstrip("0")
    except:
        return "Time Unknown"

def rerun():
    """Forces Streamlit to rerun the script immediately."""
    # This toggles a session state variable to ensure a rerun
    st.session_state["__rerun_flag__"] = not st.session_state.get("__rerun_flag__", False)
    st.rerun() # Use st.rerun() for immediate rerun (stable version)

def format_text(date, amount, currency, client, video_name, length_min, paid, initial, deadline, time_str):
    """Formats video entry details for display with HTML."""
    client_fmt = f"<b style='color: lightgreen;'>{client}</b>"
    video_fmt = f"<b style='color: deepskyblue;'>{video_name}</b>"
    amount_fmt = f"<b style='color: #FFD700;'>{currency} {amount:.2f}</b>"
    length_fmt = f"{length_min:.1f} min" if length_min and length_min > 0 else "N/A"
    paid_status = "✅ Paid" if paid else "❌ Not Paid"
    
    return f"""
    <div style='line-height: 1.6; border-bottom: 1px solid #333; padding-bottom: 5px; margin-bottom: 5px;'>
        <b style='color: lightgrey;'>{time_str}</b> | {amount_fmt} | Client: {client_fmt} | Video: {video_fmt} | Length: <span style='color: silver;'>{length_fmt}</span> | {paid_status} <br>
        <small style='color: grey;'>Initial Date: {initial} | Deadline: {deadline}</small>
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
        unpaid_pkr = df[(df['currency'] == "PKR") & (~df['paid'])].copy() # Use .copy() to avoid SettingWithCopyWarning
        paid_changed = False # Flag to check if any paid status was changed

        if unpaid_pkr.empty:
            st.info("All PKR videos are marked as paid.")
        else:
            for i, row in unpaid_pkr.iterrows():
                label = f"{row['date']} | {row['amount']} PKR | Client: {row['client']} | Video: {row['video_name']} | Length: {row['length_min']} min"
                # IMPORTANT FIX: Use row.name for unique keys, as it's the original DataFrame index
                paid_new = st.checkbox(label, value=False, key=f"unpaid_paid_chk_pkr_{row.name}") 
                if paid_new:
                    # Update the original DataFrame 'df' using its index
                    df.at[row.name, 'paid'] = True 
                    paid_changed = True

        st.header("💵 Unpaid USD Videos")
        unpaid_usd = df[(df['currency'] == "USD") & (~df['paid'])].copy() # Use .copy()
        if unpaid_usd.empty:
            st.info("All USD videos are marked as paid.")
        else:
            for i, row in unpaid_usd.iterrows():
                label = f"{row['date']} | ${row['amount']:.2f} | Client: {row['client']} | Video: {row['video_name']}"
                # IMPORTANT FIX: Use row.name for unique keys
                paid_new = st.checkbox(label, value=False, key=f"unpaid_paid_chk_usd_{row.name}")
                if paid_new:
                    # Update the original DataFrame 'df' using its index
                    df.at[row.name, 'paid'] = True
                    paid_changed = True

        # If any paid status changed, update the sheet and rerun the app
        if paid_changed:
            update_entire_sheet(df)
            rerun() # Forces a rerun to refresh the displayed data

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
                    st.session_state.edit_index = None # Clear any active edits
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
        with st.form("new_video_entry_form"):
            currency = st.selectbox("Select Currency", ["USD", "PKR"], key="currency_select")
            client = st.text_input("Enter Client Name (optional)", key="client_name_input")
            paid = st.checkbox("Mark as Paid", key="paid_checkbox")
            
            video_name_label = "Enter Video Name (optional)" if currency == "USD" else "Enter Video Name"
            video_name = st.text_input(video_name_label, key="video_name_input")
            
            today_date = datetime.today().date()
            initial_date = st.date_input("Initial Date", value=today_date, key="initial_date_input")
            deadline = st.date_input("Deadline", value=today_date, key="deadline_date_input") # Default to today
            
            length_min = 0.0
            amount = 0.0

            if currency == "PKR":
                length_min = st.number_input("Enter Video Length (minutes)", min_value=0.0, step=0.1, key="length_min_input")
                pkr_per_minute = st.number_input("Enter PKR per minute rate (optional)", min_value=0.0, step=0.1, key="pkr_rate_input")
                
                if pkr_per_minute > 0 and length_min > 0:
                    amount = length_min * pkr_per_minute
                    st.markdown(f"**Calculated Video Amount:** {amount:.2f} PKR")
                else:
                    amount = st.number_input("Enter Video Amount (PKR)", min_value=0.0, step=0.01, key="pkr_amount_input")
            else: # USD
                amount = st.number_input("Enter Video Amount (USD)", min_value=0.0, step=0.01, key="usd_amount_input")

            submitted = st.form_submit_button("Add Entry")

            if submitted:
                # Validation logic for form submission
                if currency == "PKR":
                    if length_min <= 0:
                        st.error("For PKR videos, please enter video length greater than zero.")
                        return
                    if amount <= 0:
                        st.error("For PKR videos, please enter a valid amount (either calculate or enter manually).")
                        return
                    if not video_name.strip():
                        st.error("Please enter the video name for PKR videos.")
                        return
                elif currency == "USD":
                    if amount <= 0:
                        st.error("For USD videos, please enter an amount greater than zero.")
                        return
                    if not video_name.strip():
                        st.warning("It's recommended to enter a video name for USD entries.")
                        # Allow submission but warn user
                
                # If all validations pass, save the entry
                save_video_entry(amount, currency, client, paid, video_name, length_min,
                                 initial_date.strftime("%Y-%m-%d"), deadline.strftime("%Y-%m-%d"))
                # Rerun is called inside save_video_entry upon successful save

    # --- View Monthly Breakdown Section ---
    elif choice == "View Monthly Breakdown":
        st.subheader("📆 Monthly Video & Earnings Breakdown")
        if df.empty:
            st.info("No video data submitted yet. Please add entries via 'Submit Video'.")
        else:
            # Add 'month' column for grouping
            df['month'] = df['date'].apply(get_month_name)
            
            # Client Filter
            clients = sorted(df['client'].dropna().unique().tolist())
            selected_client = st.selectbox("Filter by Client", ["All"] + clients, key="client_filter_select")
            
            filtered_df = df[df['client'] == selected_client] if selected_client != "All" else df

            # Filter out invalid month entries (from get_month_name returning "Unknown")
            def is_valid_month_format(m):
                try:
                    datetime.strptime(m, "%B %Y")
                    return True
                except:
                    return False

            # Get unique months and sort them chronologically (descending)
            months = [m for m in filtered_df['month'].unique() if is_valid_month_format(m)]
            months_sorted = sorted(months, key=lambda m: datetime.strptime(m, "%B %Y"), reverse=True)

            if not months_sorted:
                st.info("No valid monthly data found for the selected filter.")
                return

            for month in months_sorted:
                monthly_data = filtered_df[filtered_df['month'] == month]
                
                # Group by currency within each month
                for curr in monthly_data['currency'].unique():
                    currency_data = monthly_data[monthly_data['currency'] == curr]
                    
                    total_currency_monthly = currency_data['amount'].sum()
                    paid_total = currency_data[currency_data['paid']]['amount'].sum()
                    unpaid_total = total_currency_monthly - paid_total
                    
                    # Expander for each month and currency summary
                    with st.expander(f"📅 {month} — {curr} Total: {total_currency_monthly:.2f} | Earned: {paid_total:.2f} | To be Paid: {unpaid_total:.2f}"):
                        days = sorted(currency_data['date'].unique(), reverse=True)
                        if not days:
                            st.info("No entries for this month/currency combination.")
                            continue

                        selected_day = st.selectbox("Select a date to view details", days, key=f"day_select_{month}_{curr}")
                        
                        day_data = currency_data[currency_data['date'] == selected_day]
                        total_day = day_data['amount'].sum()
                        
                        st.markdown(f"### 🗓️ {selected_day} — {len(day_data)} videos — {curr} {total_day:.2f}")
                        
                        # Sort day data by datetime for consistent display
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

        st.write("Edit the table below directly:")
        edited_df = st.data_editor(
            df, 
            key="admin_data_editor",
            column_config={
                # Define column configurations for better user experience in data editor
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
            num_rows="dynamic", # Allows adding/deleting rows
            hide_index=True # Hides the DataFrame index column
        )

        if st.button("Save Changes to Sheet", key="save_admin_changes_btn"):
            try:
                # Ensure data types are consistent before saving back to Google Sheet
                edited_df['paid'] = edited_df['paid'].astype(bool)
                edited_df['amount'] = pd.to_numeric(edited_df['amount'], errors='coerce').fillna(0.0)
                edited_df['length_min'] = pd.to_numeric(edited_df['length_min'], errors='coerce').fillna(0.0)
                
                # Reorder columns to ensure they match the sheet's expected order
                edited_df = edited_df[EXPECTED_HEADERS]

                update_entire_sheet(edited_df)
                st.success("Changes saved successfully!")
                rerun() # Rerun to reflect changes and refresh the display
            except Exception as e:
                st.error(f"Error saving changes: {e}")
                st.warning("Please ensure all entries have valid data types (e.g., numbers for amount/length, correct date formats) and all required columns are present.")


if __name__ == "__main__":
    main()
