import streamlit as st
import pandas as pd
import datetime
import smtplib
from email.message import EmailMessage
import gspread
from google.oauth2.service_account import Credentials

# -------- Google Sheets Setup --------
GSHEET_URL = "https://docs.google.com/spreadsheets/d/143qPp6BdeGu9qgjMMqZgVmOwqGLablvjw5axtDdWIxQ"
SHEET_NAME = "Daily Data Analysis"

# Load credentials and create client
@st.cache_resource(ttl=3600)
def get_gsheet_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    # Load credentials from Streamlit secrets instead of file
    creds_info = st.secrets["GOOGLE_CREDENTIALS"]
    import json
    creds_dict = json.loads(creds_info)
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    return client

def load_video_data():
    client = get_gsheet_client()
    sheet = client.open_by_url(GSHEET_URL).worksheet(SHEET_NAME)
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    if df.empty:
        df = pd.DataFrame(columns=["Date", "Video", "Amount", "Currency", "Paid", "Email"])
    return df

def save_video_entry(entry):
    client = get_gsheet_client()
    sheet = client.open_by_url(GSHEET_URL).worksheet(SHEET_NAME)
    new_row = [
        entry.get("Date", ""),
        entry.get("Video", ""),
        entry.get("Amount", ""),
        entry.get("Currency", ""),
        entry.get("Paid", False),
        entry.get("Email", "")
    ]
    sheet.append_row(new_row, value_input_option='USER_ENTERED')

def update_entire_sheet(df):
    client = get_gsheet_client()
    sheet = client.open_by_url(GSHEET_URL).worksheet(SHEET_NAME)
    sheet.clear()
    sheet.update([df.columns.values.tolist()] + df.values.tolist())

# -------- Email sending setup --------
EMAIL_ADDRESS = "jxrjaxib@gmail.com"
EMAIL_PASSWORD = "euwc leab esxk vcmx"

def send_notification_email(to_email, subject, body):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = to_email
    msg.set_content(body)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        smtp.send_message(msg)

# -------- Your Streamlit App --------
def main():
    st.title("Video Tracking App")

    # Load data from Google Sheets
    df = load_video_data()

    # Add new entry form
    with st.form("Add New Video Entry"):
        video = st.text_input("Video Name")
        amount = st.number_input("Amount", min_value=0)
        currency = st.selectbox("Currency", ["PKR", "USD"])
        paid = st.checkbox("Paid")
        email = st.text_input("Your Email")
        submitted = st.form_submit_button("Add Entry")

        if submitted:
            entry = {
                "Date": datetime.date.today().strftime("%Y-%m-%d"),
                "Video": video,
                "Amount": amount,
                "Currency": currency,
                "Paid": paid,
                "Email": email
            }
            save_video_entry(entry)
            st.success("Entry added!")

            # Send notification email (example, customize as needed)
            subject = "New Video Entry Added"
            body = f"""A new video entry was added:
Date: {entry['Date']}
Video: {entry['Video']}
Amount: {entry['Amount']}
Currency: {entry['Currency']}
Paid: {entry['Paid']}
Added by: {entry['Email']}
"""
            try:
                send_notification_email(EMAIL_ADDRESS, subject, body)
            except Exception as e:
                st.warning(f"Failed to send notification email: {e}")

    # Show data table
    st.subheader("Current Video Entries")
    st.dataframe(df)

    # Admin: Edit entries section
    st.subheader("Admin: Edit Entries")
    edited_df = st.experimental_data_editor(df, num_rows="dynamic")

    if st.button("Save Changes"):
        update_entire_sheet(edited_df)
        st.success("Data updated successfully!")
        st.experimental_rerun()

if __name__ == "__main__":
    main()
