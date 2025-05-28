import streamlit as st
import pandas as pd
import smtplib
from email.message import EmailMessage
from datetime import datetime
import gspread
import json
from google.oauth2.service_account import Credentials

# Google Sheets setup
GSHEET_URL = "https://docs.google.com/spreadsheets/d/143qPp6BdeGu9qgjMMqZgVmOwqGLablvjw5axtDdWIxQ/edit?gid=0#gid=0"
SHEET_NAME = "DailyData"

@st.cache_resource(ttl=3600)
def get_gsheet_client():
    scopes = ['https://www.googleapis.com/auth/spreadsheets',
              'https://www.googleapis.com/auth/drive']
    
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    return gspread.authorize(creds)
    
@st.cache_data(ttl=3600)
def load_video_data():
    try:
        client = get_gsheet_client()
        sheet = client.open_by_url(GSHEET_URL).worksheet(SHEET_NAME)
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        df['paid'] = df['paid'].astype(bool)
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0.0)
        df['length_min'] = pd.to_numeric(df['length_min'], errors='coerce').fillna(0.0)
        return df
    except:
        return pd.DataFrame(columns=['date', 'datetime', 'amount', 'currency', 'client', 'paid',
                                     'video_name', 'length_min', 'initial_date', 'deadline'])

def save_video_entry(amount, currency, client, paid, video_name, length_min, initial_date, deadline):
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
        "length_min": length_min if currency == "PKR" else 0.0,
        "initial_date": initial_date,
        "deadline": deadline
    }

    client_gs = get_gsheet_client()
    spreadsheet = client_gs.open_by_url(GSHEET_URL)
    sheet = spreadsheet.worksheet(SHEET_NAME)
    sheet.append_row(list(new_entry.values()), value_input_option='USER_ENTERED')

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

# Email setup
ADMIN_PASSWORD = "Scorpio143"
SENDER_EMAIL = "jxrjaxib@gmail.com"
SENDER_PASS = "fqkr ekzp ocfz sgpy"
RECEIVER_EMAIL = "hafizjazib6@gmail.com"

def send_notification_email(subject, content):
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
        print(f"Email sending failed: {e}")

def get_month_name(date_str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%B %Y")
    except:
        return "Unknown"

def extract_time(datetime_str):
    try:
        dt = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%I:%M%p").lower().lstrip("0")
    except:
        return "Time Unknown"

def rerun():
    st.session_state["__rerun_flag__"] = not st.session_state.get("__rerun_flag__", False)

def format_text(date, amount, currency, client, video_name, length_min, paid, initial, deadline, time_str):
    client_fmt = f"<b style='color: lightgreen;'>{client}</b>"
    video_fmt = f"<b style='color: deepskyblue;'>{video_name}</b>"
    amount_fmt = f"<b style='color: #FFD700;'>{currency} {amount:.2f}</b>"
    length_fmt = f"{length_min:.1f} min" if length_min else ""
    paid_status = "✅ Paid" if paid else "❌ Not Paid"
    return f"""
    <div style='line-height: 1.6;'>
        <b style='color: lightgrey;'>{time_str}</b> | {amount_fmt} | Client: {client_fmt} | Video: {video_fmt} | Length: <span style='color: silver;'>{length_fmt}</span> | {paid_status} <br>
        <small style='color: grey;'>Initial: {initial} | Deadline: {deadline}</small>
    </div>
    """

def update_entire_sheet(df):
    # Utility to update the whole sheet if needed, assume implemented elsewhere
    client_gs = get_gsheet_client()
    spreadsheet = client_gs.open_by_url(GSHEET_URL)
    sheet = spreadsheet.worksheet(SHEET_NAME)
    sheet.clear()
    sheet.update([df.columns.values.tolist()] + df.values.tolist(), value_input_option='USER_ENTERED')

def main():
    st.set_page_config(layout="wide")
    st.title("🎬 Buraaq Studios Analysis")

    if 'admin_mode' not in st.session_state:
        st.session_state.admin_mode = False
    if 'edit_index' not in st.session_state:
        st.session_state.edit_index = None
    if '__rerun_flag__' not in st.session_state:
        st.session_state['__rerun_flag__'] = False

    # --- LOAD AND CLEAN DATA ---
    df = load_video_data()
    st.write("Loaded Data Preview:", df.head())  # <--- Add this here for debugging
    df['date'] = df['date'].fillna('')  # Fix: replace NaN dates with empty string
    df = df[df['date'] != '']            # Fix: remove rows where date is empty

    unpaid_pkr = df[(df['currency'] == "PKR") & (~df['paid'])]
    st.sidebar.header("🧾 Unpaid PKR Videos")
    paid_changed = False
    if unpaid_pkr.empty:
        st.sidebar.info("All PKR videos are marked as paid.")
    else:
        for i, row in unpaid_pkr.iterrows():
            label = f"{row['date']} | {row['amount']} PKR | Client: {row['client']} | Video: {row['video_name']} | Length: {row['length_min']} min"
            paid_new = st.sidebar.checkbox(label, value=False, key=f"unpaid_paid_chk_pkr_{i}")
            if paid_new:
                df.at[i, 'paid'] = True
                paid_changed = True

    unpaid_usd = df[(df['currency'] == "USD") & (~df['paid'])]
    st.sidebar.header("💵 Unpaid USD Videos")
    if unpaid_usd.empty:
        st.sidebar.info("All USD videos are marked as paid.")
    else:
        for i, row in unpaid_usd.iterrows():
            label = f"{row['date']} | ${row['amount']:.2f} | Client: {row['client']} | Video: {row['video_name']}"
            paid_new = st.sidebar.checkbox(label, value=False, key=f"unpaid_paid_chk_usd_{i}")
            if paid_new:
                df.at[i, 'paid'] = True
                paid_changed = True

    if paid_changed:
        update_entire_sheet(df)
        rerun()

    with st.sidebar.expander("🔐 Admin Login"):
        if not st.session_state.admin_mode:
            pwd = st.text_input("Enter admin password to edit details:", type="password")
            if st.button("Login as Admin"):
                if pwd == ADMIN_PASSWORD:
                    st.session_state.admin_mode = True
                    st.success("Logged in as admin.")
                    rerun()
                else:
                    st.error("Incorrect password.")
        else:
            if st.button("Logout Admin"):
                st.session_state.admin_mode = False
                st.session_state.edit_index = None
                st.success("Logged out.")
                rerun()

    menu = ["Submit Video", "View Monthly Breakdown"]
    if st.session_state.admin_mode:
        menu.append("Admin: Edit Entries")
    choice = st.selectbox("Menu", menu)

 if choice == "Submit Video":
    st.subheader("Add Video Earning")
    currency = st.selectbox("Select Currency", ["USD", "PKR"])
    client = st.text_input("Enter Client Name (optional)")
    paid = st.checkbox("Mark as Paid")
    video_name = st.text_input("Enter Video Name (optional)" if currency == "USD" else "Enter Video Name")
    today_date = datetime.today().date()
    initial_date = st.date_input("Initial Date", value=today_date)
    deadline = st.date_input("Deadline")
    length_min = 0.0
    amount = 0.0

    if currency == "PKR":
        length_min = st.number_input("Enter Video Length (minutes)", min_value=0.0, step=0.1)
        pkr_per_minute = st.number_input("Enter PKR per minute rate (optional)", min_value=0.0, step=0.1)
        if pkr_per_minute > 0:
            amount = length_min * pkr_per_minute
            st.markdown(f"**Calculated Video Amount:** {amount:.2f} PKR")
        else:
            amount = st.number_input("Enter Video Amount (PKR)", min_value=0.0, step=0.01)
    else:
        amount = st.number_input("Enter Video Amount (USD)", min_value=0.0, step=0.01)

    if st.button("Add Entry"):
        if currency == "PKR":
            if length_min <= 0:
                st.error("Please enter video length greater than zero.")
                return
            if amount <= 0:
                st.error("Please enter a valid amount (either calculate or enter manually).")
                return
            if not video_name.strip():
                st.error("Please enter the video name.")
                return

        save_video_entry(
            amount, currency, client, paid, video_name, length_min,
            initial_date.strftime("%Y-%m-%d"), deadline.strftime("%Y-%m-%d")
        )

        load_video_data.clear()
        get_gsheet_client.clear()
        st.success("Video entry added successfully!")
        rerun()

elif choice == "View Monthly Breakdown":
        st.subheader("📆 Monthly Video & Earnings Breakdown")
        if df.empty:
            st.info("No video data submitted yet.")
        else:
            df['month'] = df['date'].apply(get_month_name)
            clients = sorted(df['client'].dropna().unique())
            selected_client = st.selectbox("Filter by Client", ["All"] + clients)
            filtered_df = df[df['client'] == selected_client] if selected_client != "All" else df

            def is_valid_month(m):
                try:
                    datetime.strptime(m, "%B %Y")
                    return True
                except:
                    return False

            months = [m for m in filtered_df['month'].unique() if is_valid_month(m)]

            for month in sorted(months, key=lambda m: datetime.strptime(m, "%B %Y"), reverse=True):
                monthly_data = filtered_df[filtered_df['month'] == month]
                for curr in monthly_data['currency'].unique():
                    currency_data = monthly_data[monthly_data['currency'] == curr]
                    total_currency_monthly = currency_data['amount'].sum()
                    paid_total = currency_data[currency_data['paid']]['amount'].sum()
                    unpaid_total = total_currency_monthly - paid_total
                    with st.expander(f"📅 {month} — {curr} Total: {total_currency_monthly:.2f} | Earned: {paid_total:.2f} | To be Paid: {unpaid_total:.2f}"):
                        days = sorted(currency_data['date'].unique(), reverse=True)
                        selected_day = st.selectbox("Select a date", days, key=f"day_select_{month}_{curr}")
                        day_data = currency_data[currency_data['date'] == selected_day]
                        total_day = day_data['amount'].sum()
                        st.markdown(f"### 🗓️ {selected_day} — {len(day_data)} videos — {curr} {total_day:.2f}")
                        for i, row in day_data.iterrows():
                            time_str = extract_time(row['datetime'])
                            formatted = format_text(row['date'], row['amount'], row['currency'], row['client'], row['video_name'],
                                                    row['length_min'], row['paid'], row['initial_date'], row['deadline'], time_str)
                            st.markdown(formatted, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
