import os
import json
from collections import defaultdict
from twilio.rest import Client
import requests
from icalendar import Calendar
from datetime import datetime, timedelta
import pytz
import base64
from dotenv import load_dotenv

load_dotenv()

def fetch_ical_data(url):
    response = requests.get(url)
    return response.text

def parse_ical_data(ical_data):
    cal = Calendar.from_ical(ical_data)
    check_out_dates = []
    for component in cal.walk():
        if component.name == "EVENT":
            end_date = component.get('end').dt
            if isinstance(end_date, datetime):
                end_date = end_date.date()
            check_out_dates.append(end_date)
    return sorted(check_out_dates)

def send_sms(to, body, is_test):
    print(f"Sending SMS to {to} with body:\n{body}")

    if is_test:
        print("Skipping sending SMS because this is a test")
        return
    # Your Twilio account SID and auth token
    account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    from_phone_number = os.getenv('FROM_PHONE_NUMBER')

    client = Client(account_sid, auth_token)

    for phone_number in to:
        message = client.messages.create(
            body=body,
            from_=from_phone_number,
            to=phone_number
        )

        print(f"Message sent to {phone_number}, ID: {message.sid}")

def airbnb_automate(event, context):
    # Extract the message from the Pub/Sub event data
    if 'data' in event:
        message = base64.b64decode(event['data']).decode('utf-8')
    else:
        message = ''

    print(f"Received message: {message}")

    # Run the script, send real SMS if the message is "production"
    is_test = (message != "production")
    get_checkouts_and_send_sms(is_test)
    return 'Function executed', 200

def get_checkouts_and_send_sms(is_test=False):
    calendars = json.loads(os.getenv('CALENDARS'))
    to_phone_numbers = json.loads(os.getenv('TO_PHONE_NUMBERS'))
    checkouts_by_date = defaultdict(list)
    pst = pytz.timezone('America/Los_Angeles')
    now_pst = datetime.now(pst).date()
    for calendar_name, url in calendars.items():
        ical_data = fetch_ical_data(url)
        check_out_dates = parse_ical_data(ical_data)
        next_two_weeks = now_pst + timedelta(days=14)
        check_out_dates_next_two_weeks = [date for date in check_out_dates if now_pst < date <= next_two_weeks]
        for date in check_out_dates_next_two_weeks:
            checkouts_by_date[date.strftime('%A %B %d %Y')].append(calendar_name)
    if checkouts_by_date:
        messages = []
        for date in sorted(checkouts_by_date.keys(), key=lambda date: datetime.strptime(date, '%A %B %d %Y')):
            locations = checkouts_by_date[date]
            locations_str = "\n".join(locations)
            message = f"{date} checkouts:\n{locations_str}"
            messages.append(message)
        sms_message = "\n\n".join(messages)
        send_sms(to_phone_numbers, sms_message, is_test)

def main():
    get_checkouts_and_send_sms(True)

main()
