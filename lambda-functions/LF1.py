import json
import boto3
import os
import re
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

sqs = boto3.client('sqs', region_name='us-east-1')
SQS_QUEUE_URL = os.environ.get('SQS_QUEUE_URL', '')

EST = ZoneInfo('America/New_York')

VALID_EMAIL_DOMAINS = [
    'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'icloud.com',
    'aol.com', 'protonmail.com', 'nyu.edu', 'hotmail.co.uk', 'yahoo.co.uk',
    'live.com', 'msn.com', 'me.com', 'mac.com', 'googlemail.com'
]

VALID_LOCATIONS = ['manhattan', 'new york', 'nyc', 'new york city', 'ny']
VALID_CUISINES = ['chinese', 'italian', 'japanese', 'mexican', 'indian']

def close(session_attrs, intent_name, fulfillment_state, message):
    return {
        'sessionState': {
            'sessionAttributes': session_attrs,
            'dialogAction': {'type': 'Close'},
            'intent': {'name': intent_name, 'state': fulfillment_state}
        },
        'messages': [{'contentType': 'PlainText', 'content': message}]
    }

def elicit_slot(session_attrs, intent_name, slots, slot_to_elicit, message):
    return {
        'sessionState': {
            'sessionAttributes': session_attrs,
            'dialogAction': {'type': 'ElicitSlot', 'slotToElicit': slot_to_elicit},
            'intent': {'name': intent_name, 'slots': slots}
        },
        'messages': [{'contentType': 'PlainText', 'content': message}]
    }

def delegate(session_attrs, intent_name, slots):
    return {
        'sessionState': {
            'sessionAttributes': session_attrs,
            'dialogAction': {'type': 'Delegate'},
            'intent': {'name': intent_name, 'slots': slots}
        }
    }

def get_slot_value(slots, name):
    s = slots.get(name)
    if s and s.get('value') and s['value'].get('interpretedValue'):
        return s['value']['interpretedValue']
    return None

def validate_email(email):
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        return False, "That doesn't look like a valid email address. Please enter a valid one."
    domain = email.split('@')[1].lower()
    if domain not in VALID_EMAIL_DOMAINS:
        return False, f"I don't recognize '{domain}' as a valid email domain."
    return True, None

def validate_date(value):
    """Returns (is_valid, error_message, parsed_date)"""
    value_lower = value.lower().strip()
    today = datetime.now(EST).date()

    if value_lower == 'today':
        return True, None, today
    elif value_lower == 'tomorrow':
        return True, None, today + timedelta(days=1)
    elif value_lower in ['yesterday', 'last week', 'last month']:
        return False, "Sorry, I can't make reservations for past dates.", None

    
    try:
        parsed = datetime.strptime(value, '%Y-%m-%d').date()
        if parsed < today:
            return False, "Sorry, I can't make reservations for past dates.", None
        return True, None, parsed
    except ValueError:
        pass

    
    for fmt in ['%B %d', '%b %d', '%d %B', '%d %b', '%m/%d/%Y', '%m/%d/%y', '%B %d %Y', '%b %d %Y', '%d %B %Y', '%d %b %Y']:
        try:
            parsed = datetime.strptime(value, fmt).date()
            if fmt in ['%B %d', '%b %d', '%d %B', '%d %b']:
                parsed = parsed.replace(year=today.year)
                if parsed < today:
                    return False, f"Sorry, '{value}' is a past date. Please enter a future date.", None
            if parsed < today:
                return False, "Sorry, I can't make reservations for past dates.", None
            return True, None, parsed
        except ValueError:
            continue

    return False, f"Sorry, '{value}' is not a valid date. Please enter a valid date.", None

def parse_time_input(value):
    """Convert natural language time to HH:MM format"""
    value = value.lower().strip()

    
    if re.match(r'^\d{1,2}:\d{2}$', value):
        return value

    
    match = re.match(r'^(\d{1,2})(?::(\d{2}))?\s*(am|pm)$', value)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2)) if match.group(2) else 0
        period = match.group(3)
        if period == 'pm' and hour != 12:
            hour += 12
        elif period == 'am' and hour == 12:
            hour = 0
        return f"{hour:02d}:{minute:02d}"

    
    match = re.match(r'^(\d{1,2})$', value)
    if match:
        hour = int(match.group(1))
        if 1 <= hour <= 9:
            hour += 12
        return f"{hour:02d}:00"

    return None

def validate_time(value, dining_date=None):
    """Returns (is_valid, error_message)"""
    try:
        parts = value.split(':')
        if len(parts) != 2:
            raise ValueError
        hour = int(parts[0])
        minute = int(parts[1])

        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            raise ValueError

        if 2 <= hour <= 6:
            return False, "Sorry, I can't make reservations between 2 AM and 6 AM. Please enter a valid dining time."

        if dining_date:
            try:
                now_est = datetime.now(EST)
                today_est = now_est.date()
                parsed_date = datetime.strptime(dining_date, '%Y-%m-%d').date()
                if parsed_date == today_est:
                    if hour < now_est.hour or (hour == now_est.hour and minute <= now_est.minute):
                        return False, "Sorry, that time has already passed today. Please enter a future time."
            except ValueError:
                pass

        return True, None
    except (ValueError, AttributeError):
        return False, f"Sorry, '{value}' is not a valid time."

def validate_num_people(value):
    """Returns (is_valid, error_message)"""
    try:
        n = int(float(value))
        if n < 1:
            return False, "Sorry, I can't fulfill a reservation for less than 1 person. How many people will be dining?"
        if n > 20:
            return False, "Sorry, I can't fulfill reservations for more than 20 people. How many people will be dining?"
        return True, None
    except (ValueError, TypeError):
        return False, f"Sorry, '{value}' is not a valid number."

def handle_greeting(event):
    return close({}, 'GreetingIntent', 'Fulfilled', 'Hi there, how can I help?')

def handle_thankyou(event):
    return close({}, 'ThankYouIntent', 'Fulfilled', "You're welcome! Have a great day!")

def handle_dining(event):
    intent_name = event['sessionState']['intent']['name']
    slots = event['sessionState']['intent']['slots']
    session_attrs = event['sessionState'].get('sessionAttributes', {})
    source = event.get('invocationSource', '')
    user_input = event.get('inputTranscript', '').strip()

    
    confirmed_location = session_attrs.get('confirmedLocation')
    confirmed_cuisine  = session_attrs.get('confirmedCuisine')
    confirmed_date     = session_attrs.get('confirmedDate')
    confirmed_time     = session_attrs.get('confirmedTime')
    confirmed_people   = session_attrs.get('confirmedPeople')
    confirmed_email    = session_attrs.get('confirmedEmail')

    
    if not confirmed_location:
        collecting = 'Location'
    elif not confirmed_cuisine:
        collecting = 'Cuisine'
    elif not confirmed_date:
        collecting = 'DiningDate'
    elif not confirmed_time:
        collecting = 'DiningTime'
    elif not confirmed_people:
        collecting = 'NumberOfPeople'
    elif not confirmed_email:
        collecting = 'Email'
    else:
        collecting = None

    if collecting and source == 'DialogCodeHook':

        if collecting == 'Location':
            trigger_words = ['nearby', 'places', 'restaurant', 'food', 'eat',
                           'dine', 'dinner', 'lunch', 'breakfast', 'suggestions',
                           'help', 'hungry', 'recommend']
            if any(word in user_input.lower() for word in trigger_words):
                return elicit_slot(session_attrs, intent_name, slots, 'Location',
                    "Where would you like to dine?")
            elif user_input.lower() in VALID_LOCATIONS:
                session_attrs['confirmedLocation'] = user_input
            else:
                return elicit_slot(session_attrs, intent_name, slots, 'Location',
                    f"Sorry, I can't fulfill requests for {user_input}. "
                    f"Please enter a valid location.")

        elif collecting == 'Cuisine':
            if user_input.lower() in VALID_CUISINES:
                session_attrs['confirmedCuisine'] = user_input.capitalize()
            else:
                return elicit_slot(session_attrs, intent_name, slots, 'Cuisine',
                    f"Sorry, I don't have suggestions for {user_input} cuisine. "
                    f"I support Chinese, Italian, Japanese, Mexican, and Indian. "
                    f"Which would you like?")

        elif collecting == 'DiningDate':
            slot_date = get_slot_value(slots, 'DiningDate')
            date_to_validate = slot_date if slot_date else user_input
            is_valid, error_msg, parsed_date = validate_date(date_to_validate)
            if is_valid:
                session_attrs['confirmedDate'] = parsed_date.strftime('%Y-%m-%d')
                session_attrs['displayDate'] = user_input
            else:
                if slot_date and slot_date != user_input:
                    is_valid2, error_msg2, parsed_date2 = validate_date(user_input)
                    if is_valid2:
                        session_attrs['confirmedDate'] = parsed_date2.strftime('%Y-%m-%d')
                        session_attrs['displayDate'] = user_input
                    else:
                        return elicit_slot(session_attrs, intent_name, slots, 'DiningDate', error_msg)
                else:
                    return elicit_slot(session_attrs, intent_name, slots, 'DiningDate', error_msg)

        elif collecting == 'DiningTime':
            slot_time = get_slot_value(slots, 'DiningTime')
            if slot_time:
                time_to_validate = slot_time
            else:
                time_to_validate = parse_time_input(user_input)

            if not time_to_validate:
                return elicit_slot(session_attrs, intent_name, slots, 'DiningTime',
                    f"Sorry, '{user_input}' is not a valid time. "
                    f"Please enter a valid time.")

            is_valid, error_msg = validate_time(time_to_validate, session_attrs.get('confirmedDate'))
            if is_valid:
                session_attrs['confirmedTime'] = time_to_validate
            else:
                return elicit_slot(session_attrs, intent_name, slots, 'DiningTime', error_msg)

        elif collecting == 'NumberOfPeople':
            is_valid, error_msg = validate_num_people(user_input)
            if is_valid:
                session_attrs['confirmedPeople'] = str(int(float(user_input)))
            else:
                return elicit_slot(session_attrs, intent_name, slots, 'NumberOfPeople', error_msg)

        elif collecting == 'Email':
            is_valid, error_msg = validate_email(user_input)
            if is_valid:
                session_attrs['confirmedEmail'] = user_input.lower()
            else:
                return elicit_slot(session_attrs, intent_name, slots, 'Email', error_msg)

    
    all_confirmed = all([
        session_attrs.get('confirmedLocation'),
        session_attrs.get('confirmedCuisine'),
        session_attrs.get('confirmedDate'),
        session_attrs.get('confirmedTime'),
        session_attrs.get('confirmedPeople'),
        session_attrs.get('confirmedEmail')
    ])

    if all_confirmed:
        if SQS_QUEUE_URL:
            try:
                sqs.send_message(
                    QueueUrl=SQS_QUEUE_URL,
                    MessageBody=json.dumps({
                        'Location':       session_attrs['confirmedLocation'],
                        'Cuisine':        session_attrs['confirmedCuisine'],
                        'DiningDate':     session_attrs['confirmedDate'],
                        'DiningTime':     session_attrs['confirmedTime'],
                        'NumberOfPeople': session_attrs['confirmedPeople'],
                        'Email':          session_attrs['confirmedEmail']
                    })
                )
            except Exception as e:
                print(f'SQS error: {str(e)}')
                return close(session_attrs, intent_name, 'Failed',
                    "I'm sorry, something went wrong. Please try again in a moment.")

        
        try:
            pretty_time = datetime.strptime(
                session_attrs['confirmedTime'], '%H:%M').strftime('%I:%M %p')
        except Exception:
            pretty_time = session_attrs['confirmedTime']

        display_date = session_attrs.get('displayDate', session_attrs['confirmedDate'])

        return close(session_attrs, intent_name, 'Fulfilled',
            f"Perfect! I'll send {session_attrs['confirmedCuisine']} restaurant "
            f"suggestions for {session_attrs['confirmedPeople']} people for "
            f"{display_date} at {pretty_time} "
            f"to {session_attrs['confirmedEmail']}. Enjoy your meal!")

    
    if not session_attrs.get('confirmedLocation'):
        return elicit_slot(session_attrs, intent_name, slots, 'Location',
            "Where would you like to dine?")
    elif not session_attrs.get('confirmedCuisine'):
        return elicit_slot(session_attrs, intent_name, slots, 'Cuisine',
            "What cuisine are you in the mood for? "
            "I support Chinese, Italian, Japanese, Mexican, and Indian.")
    elif not session_attrs.get('confirmedDate'):
        return elicit_slot(session_attrs, intent_name, slots, 'DiningDate',
            "When would you like the reservation for?")
    elif not session_attrs.get('confirmedTime'):
        return elicit_slot(session_attrs, intent_name, slots, 'DiningTime',
            "What time would you like to dine?")
    elif not session_attrs.get('confirmedPeople'):
        return elicit_slot(session_attrs, intent_name, slots, 'NumberOfPeople',
            "How many people will be dining?")
    elif not session_attrs.get('confirmedEmail'):
        return elicit_slot(session_attrs, intent_name, slots, 'Email',
            "Almost done! What email should I send the suggestions to?")

    return delegate(session_attrs, intent_name, slots)

def lambda_handler(event, context):
    print('Event:', json.dumps(event))
    try:
        intent = event['sessionState']['intent']['name']
        if intent == 'GreetingIntent':
            return handle_greeting(event)
        elif intent == 'ThankYouIntent':
            return handle_thankyou(event)
        elif intent == 'DiningSuggestionsIntent':
            return handle_dining(event)
        elif intent == 'FallbackIntent':
            return close({}, 'FallbackIntent', 'Fulfilled',
                "Sorry, I didn't understand that. Type 'Hello' to get started!")
        return close({}, intent, 'Fulfilled', 'How can I help you?')
    except Exception as e:
        print(f'Unhandled error: {str(e)}')
        return {
            'sessionState': {
                'dialogAction': {'type': 'Close'},
                'intent': {'name': 'FallbackIntent', 'state': 'Fulfilled'}
            },
            'messages': [{'contentType': 'PlainText',
                'content': "I'm sorry, something unexpected happened. Please try again."}]
        }