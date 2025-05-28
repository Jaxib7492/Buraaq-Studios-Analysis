import streamlit as st
import pandas as pd
import smtplib
from email.message import EmailMessage
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# Google Sheets setup
GSHEET_URL = "https://docs.google.com/spreadsheets/d/143qPp6BdeGu9qgjMMqZgVmOwqGLablvjw5axtDdWIxQ/edit?gid=0#gid=0"
SHEET_NAME = "DailyData"

@st.cache_resource(ttl=3600)
def get_gsheet_client():
    scopes = ['https://www.googleapis.com/auth/spreadsheets',
              'https://www.googleapis.com/auth/drive']
    
    # Ensure 'gcp_service_account' is correctly configured in Streamlit secrets
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    return gspread.authorize(creds)

def load_video_data():
    """Loads video data from Google Sheet into a pandas DataFrame."""
    try:
        client = get_gsheet_client()
        sheet = client.open_by_url(GSHEET_URL).worksheet(SHEET_NAME)
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        # Convert data types safely
        df['paid'] = df['paid'].astype(bool)
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0.0)
        df['length_min'] = pd.to_numeric(df['length_min'], errors='coerce').fillna(0.0)
        
        return df
    except Exception as e:
        st.error(f"Error loading video data from Google Sheet. Please check credentials, sheet URL, and permissions: {e}")
        # Return an empty DataFrame with expected columns to prevent downstream errors
        return pd.DataFrame(columns=['date', 'datetime', 'amount', 'currency', 'client', 'paid',
                                     'video_name', 'length_min', 'initial_date', 'deadline'])

def save_video_entry(amount, currency, client, paid, video_name, length_min, initial_date, deadline):
    """Saves a new video entry to the Google Sheet and sends an email notification."""
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    
    new_entry = {
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
        
        # Append the new entry as a row
        sheet.append_row(list(new_entry.values()), value_input_option='USER_ENTERED')
        
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

# Email setup
ADMIN_PASSWORD = "Scorpio143"  # Consider using Streamlit secrets for this as well
SENDER_EMAIL = "jxrjaxib@gmail.com"
SENDER_PASS = "fqkr ekzp ocfz sgpy" # This is an App Password, not your regular Gmail password.
RECEIVER_EMAIL = "hafizjazib6@gmail.com"

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
        st.warning(f"Email sending failed: {e}. Please check SENDER_EMAIL, SENDER_PASS, and internet connection.")

# Utility Functions
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
    """Forces Streamlit to rerun the script."""
    st.session_state["__rerun_flag__"] = not st.session_state.get("__rerun_flag__", False)
    st.experimental_rerun() # Use experimental_rerun for immediate rerun

def format_text(date, amount, currency, client, video_name, length_min, paid, initial, deadline, time_str):
    """Formats video entry details for display."""
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

def update_entire_sheet(df_to_update):
    """Updates the entire Google Sheet with the content of a DataFrame."""
    try:
        client = get_gsheet_client()
        sheet = client.open_by_url(GSHEET_URL).worksheet(SHEET_NAME)
        
        # Clear existing data and then write the updated DataFrame
        # This is a full overwrite, use with caution for large sheets
        sheet.clear()
        sheet.update([df_to_update.columns.values.tolist()] + df_to_update.values.tolist())
        st.success("Sheet updated successfully (paid status changes applied).")
    except Exception as e:
        st.error(f"Failed to update Google Sheet: {e}")

# Main App
def main():
    st.set_page_config(layout="wide", page_title="Buraaq Studios Analysis")
    st.title("🎬 Buraaq Studios Analysis")

    # Initialize session states
    if 'admin_mode' not in st.session_state:
        st.session_state.admin_mode = False
    if 'edit_index' not in st.session_state:
        st.session_state.edit_index = None
    if '__rerun_flag__' not in st.session_state: # Used for general rerunning
        st.session_state['__rerun_flag__'] = False

    # Load data at the beginning of the script run
    df = load_video_data()

    # --- Sidebar for Unpaid Videos and Admin Login ---
    with st.sidebar:
        st.header("🧾 Unpaid PKR Videos")
        unpaid_pkr = df[(df['currency'] == "PKR") & (~df['paid'])]
        paid_changed = False
        if unpaid_pkr.empty:
            st.info("All PKR videos are marked as paid.")
        else:
            for i, row in unpaid_pkr.iterrows():
                label = f"{row['date']} | {row['amount']} PKR | Client: {row['client']} | Video: {row['video_name']} | Length: {row['length_min']} min"
                # Use a unique key for each checkbox
                paid_new = st.checkbox(label, value=False, key=f"unpaid_paid_chk_pkr_{row.name}") 
                if paid_new:
                    # Update the DataFrame directly
                    df.at[row.name, 'paid'] = True 
                    paid_changed = True

        st.header("💵 Unpaid USD Videos")
        unpaid_usd = df[(df['currency'] == "USD") & (~df['paid'])]
        if unpaid_usd.empty:
            st.info("All USD videos are marked as paid.")
        else:
            for i, row in unpaid_usd.iterrows():
                label = f"{row['date']} | ${row['amount']:.2f} | Client: {row['client']} | Video: {row['video_name']}"
                # Use a unique key for each checkbox
                paid_new = st.checkbox(label, value=False, key=f"unpaid_paid_chk_usd_{row.name}")
                if paid_new:
                    # Update the DataFrame directly
                    df.at[row.name, 'paid'] = True
                    paid_changed = True

        # If any paid status changed, update the sheet and rerun
        if paid_changed:
            update_entire_sheet(df)
            rerun() # Rerun to refresh the data displayed

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

    # --- Main content area ---
    menu_options = ["Submit Video", "View Monthly Breakdown"]
    if st.session_state.admin_mode:
        menu_options.append("Admin: Edit Entries")
    
    choice = st.selectbox("Menu", menu_options, key="main_menu_select")

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
            deadline = st.date_input("Deadline", value=today_date, key="deadline_date_input") # Set a default for deadline too

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
                if currency == "PKR" and (length_min <= 0 or amount <= 0 or not video_name.strip()):
                    if length_min <= 0:
                        st.error("For PKR videos, please enter video length greater than zero.")
                    if amount <= 0:
                        st.error("For PKR videos, please enter a valid amount (either calculate or enter manually).")
                    if not video_name.strip():
                        st.error("Please enter the video name.")
                    return # Stop execution if validation fails
                
                if currency == "USD" and (amount <= 0 or not video_name.strip()):
                    if amount <= 0:
                        st.error("For USD videos, please enter an amount greater than zero.")
                    if not video_name.strip():
                        st.warning("It's recommended to enter a video name for USD entries.")
                        # Allow submission but warn

                # If all validations pass or it's a USD with no video name
                save_video_entry(amount, currency, client, paid, video_name, length_min,
                                 initial_date.strftime("%Y-%m-%d"), deadline.strftime("%Y-%m-%d"))
                # Rerun is called inside save_video_entry upon success

    elif choice == "View Monthly Breakdown":
        st.subheader("📆 Monthly Video & Earnings Breakdown")
        if df.empty:
            st.info("No video data submitted yet. Please add entries via 'Submit Video'.")
        else:
            # Add 'month' column for grouping
            df['month'] = df['date'].apply(get_month_name)
            
            # Client Filter
            clients = sorted(df['client'].dropna().unique().tolist()) # .tolist() to ensure it's a list for selectbox
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

    elif choice == "Admin: Edit Entries":
        if not st.session_state.admin_mode:
            st.warning("Please log in as admin to access this section.")
            return

        st.subheader("⚙️ Admin: Edit Video Entries")
        if df.empty:
            st.info("No video data available to edit.")
            return

        # Display data in a DataFrame for easy editing.
        # This requires Streamlit's data editor, which provides interactive editing.
        st.write("Edit the table below directly:")
        edited_df = st.data_editor(
            df, 
            key="admin_data_editor",
            column_config={
                "date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
                "datetime": st.column_config.DatetimeColumn("Timestamp", format="YYYY-MM-DD HH:mm:ss"),
                "amount": st.column_config.NumberColumn("Amount", format="%.2f"),
                "currency": st.column_config.SelectboxColumn("Currency", options=["PKR", "USD"]),
                "client": st.column_config.TextColumn("Client"),
                "paid": st.column_config.CheckboxColumn("Paid"),
                "video_name": st.column_config.TextColumn("Video Name"),
                "length_min": st.column_config.NumberColumn("Length (min)", format="%.1f"),
                "initial_date": st.column_config.DateColumn("Initial Date", format="YYYY-MM-DD"),
                "deadline": st.column_config.DateColumn("Deadline", format="YYYY-MM-DD")
            },
            num_rows="dynamic", # Allows adding/deleting rows if needed
            hide_index=True # Hides the DataFrame index
        )

        if st.button("Save Changes to Sheet", key="save_admin_changes_btn"):
            try:
                # Ensure data types are consistent before saving back to Google Sheet
                edited_df['paid'] = edited_df['paid'].astype(bool)
                edited_df['amount'] = pd.to_numeric(edited_df['amount'], errors='coerce').fillna(0.0)
                edited_df['length_min'] = pd.to_numeric(edited_df['length_min'], errors='coerce').fillna(0.0)
                
                update_entire_sheet(edited_df)
                st.success("Changes saved successfully!")
                rerun() # Rerun to reflect changes and refresh the display
            except Exception as e:
                st.error(f"Error saving changes: {e}")
                st.warning("Please ensure all entries have valid data types (e.g., numbers for amount/length, correct date formats).")


if __name__ == "__main__":
    main()
