import streamlit as st
import pandas as pd
import os
from datetime import datetime

DATA_FILE = "daily_videos.csv"

def load_video_data():
    if os.path.exists(DATA_FILE):
        df = pd.read_csv(DATA_FILE)
        # Make sure columns exist or add defaults
        if 'date' not in df.columns:
            df['date'] = "Unknown"
        if 'datetime' not in df.columns:
            df['datetime'] = df['date'] + " 00:00:00"
        if 'client' not in df.columns:
            df['client'] = "Unknown"
        if 'currency' not in df.columns:
            df['currency'] = "USD"
        if 'paid' not in df.columns:
            df['paid'] = False
        if 'video_name' not in df.columns:
            df['video_name'] = ""
        if 'length_min' not in df.columns:
            df['length_min'] = 0.0
        df['paid'] = df['paid'].astype(bool)
        return df
    else:
        return pd.DataFrame(columns=["date", "datetime", "amount", "currency", "client", "paid", "video_name", "length_min"])

def save_video_entry(amount, currency, client, paid, video_name, length_min):
    df = load_video_data()
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    new_entry = pd.DataFrame([{
        "date": today,
        "datetime": timestamp,
        "amount": amount,
        "currency": currency,
        "client": client if client else "Unknown",
        "paid": paid if currency == "PKR" else False,
        "video_name": video_name if currency == "PKR" else "",
        "length_min": length_min if currency == "PKR" else 0.0
    }])
    df = pd.concat([df, new_entry], ignore_index=True)
    df.to_csv(DATA_FILE, index=False)

def mark_as_paid(indexes):
    df = load_video_data()
    df.loc[indexes, 'paid'] = True
    df.to_csv(DATA_FILE, index=False)

def get_month_name(date_str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%B %Y")
    except Exception:
        return "Unknown"

def main():
    st.set_page_config(layout="wide")
    st.title("🎬 Buraaq Studios Analysis")

    # Initialize session state flags for rerun workaround
    if 'refresh' not in st.session_state:
        st.session_state.refresh = False

    if st.session_state.refresh:
        st.session_state.refresh = False

    df = load_video_data()
    unpaid_pkr = df[(df['currency'] == "PKR") & (~df['paid'])]

    with st.sidebar:
        st.header("🧾 Unpaid PKR Videos")
        if unpaid_pkr.empty:
            st.info("All PKR videos are marked as paid.")
        else:
            st.write("✅ Check videos that are now paid:")
            paid_indexes = []
            for i, row in unpaid_pkr.iterrows():
                label = f"{row['date']} | 🎞️ {row['amount']} PKR | Client: {row['client']} | Video: {row['video_name']} | Length: {row['length_min']} min"
                if st.checkbox(label, key=f"sidebar_unpaid_{i}"):
                    paid_indexes.append(i)
            if paid_indexes:
                if st.button("Mark Selected as Paid"):
                    mark_as_paid(paid_indexes)
                    st.success("Marked as paid.")
                    st.session_state.refresh = True
                    st.stop()

    menu = ["Submit Video", "View Monthly Breakdown"]
    choice = st.selectbox("Menu", menu)

    if choice == "Submit Video":
        st.subheader("Add Video Earning")

        currency = st.selectbox("Select Currency", ["USD", "PKR"])
        client = st.text_input("Enter Client Name (optional)")

        paid = False
        video_name = ""
        length_min = 0.0
        amount = 0.0

        if currency == "PKR":
            paid = st.checkbox("Mark as Paid")
            video_name = st.text_input("Enter Video Name")
            length_min = st.number_input("Enter Video Length (minutes)", min_value=0.0, step=0.1)
            pkr_per_minute = st.number_input("Enter PKR per minute rate (optional)", min_value=0.0, step=0.1)

            if pkr_per_minute > 0:
                amount = length_min * pkr_per_minute
                st.markdown(f"**Calculated Video Amount:** {amount:.2f} PKR")
            else:
                amount = st.number_input("Enter Video Amount (PKR)", min_value=0.0, step=0.01)

        else:
            amount = st.number_input("Enter Video Amount", min_value=0.0, step=0.01)

        if st.button("Add Entry"):
            if currency == "PKR":
                if length_min <= 0:
                    st.error("Please enter video length greater than zero.")
                    st.stop()
                if amount <= 0:
                    st.error("Please enter a valid amount (either calculate or enter manually).")
                    st.stop()
                if not video_name.strip():
                    st.error("Please enter the video name.")
                    st.stop()

            save_video_entry(amount, currency, client, paid, video_name, length_min)
            st.success("Video entry added successfully!")
            st.session_state.refresh = True
            st.stop()

    elif choice == "View Monthly Breakdown":
        st.subheader("📆 Monthly Video & Earnings Breakdown")

        if df.empty:
            st.info("No video data submitted yet.")
        else:
            # Add month column
            df['month'] = df['date'].apply(get_month_name)

            # Client dropdown for filtering
            clients = sorted(df['client'].dropna().unique())
            selected_client = st.selectbox("Filter by Client", ["All"] + clients)

            # Filter dataframe by client
            if selected_client != "All":
                filtered_df = df[df['client'] == selected_client]
            else:
                filtered_df = df

            # Filter out invalid months
            def is_valid_month(m):
                try:
                    datetime.strptime(m, "%B %Y")
                    return True
                except Exception:
                    return False

            months = [m for m in filtered_df['month'].unique() if is_valid_month(m)]

            for month in sorted(months, key=lambda m: datetime.strptime(m, "%B %Y"), reverse=True):
                monthly_data = filtered_df[filtered_df['month'] == month]
                currencies = monthly_data['currency'].unique()

                for curr in currencies:
                    currency_data = monthly_data[monthly_data['currency'] == curr]
                    total_currency_monthly = currency_data['amount'].sum()

                    with st.expander(f"📅 {month} — {curr} Total: {total_currency_monthly:.2f}"):
                        days = sorted(currency_data['date'].unique(), reverse=True)
                        selected_day = st.selectbox("Select a date", days, key=f"day_select_{month}_{curr}")
                        day_data = currency_data[currency_data['date'] == selected_day]
                        total_day = day_data['amount'].sum()

                        st.markdown(f"### 🗓️ {selected_day} — {len(day_data)} videos — {curr} {total_day:.2f}")
                        for i, row in day_data.iterrows():
                            try:
                                time_only = datetime.strptime(row['datetime'], "%Y-%m-%d %H:%M:%S").strftime("%H:%M:%S")
                            except Exception:
                                time_only = "Unknown time"
                            paid_status = "✅ Paid" if row.get('paid', False) else "❌ Not Paid" if row['currency'] == "PKR" else ""
                            extra_info = ""
                            if row['currency'] == "PKR":
                                extra_info = f" | Video: {row['video_name']} | Length: {row['length_min']} min"
                            st.write(f"- 🎞️ Video {i+1} at {time_only} | Client: {row['client']} | {curr} {row['amount']:.2f} {paid_status}{extra_info}")

if __name__ == "__main__":
    main()
