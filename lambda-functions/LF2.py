import json, boto3, random, os, urllib.request, urllib.parse
import base64
from urllib.error import URLError

sqs      = boto3.client('sqs',      region_name='us-east-1')
dynamodb = boto3.resource('dynamodb',region_name='us-east-1')
ses      = boto3.client('ses',       region_name='us-east-1')

SQS_URL    = os.environ.get('SQS_QUEUE_URL', '')
ES_HOST    = os.environ.get('ES_HOST', '')
ES_USER    = os.environ.get('ES_USER', 'admin')
ES_PASS    = os.environ.get('ES_PASS', '')
FROM_EMAIL = os.environ.get('FROM_EMAIL', '')

def es_search(cuisine):
    url = f'{ES_HOST}/restaurants/_search'
    query = json.dumps({'query': {'match': {'Cuisine': cuisine}}, 'size': 50}).encode()
    credentials = base64.b64encode(f'{ES_USER}:{ES_PASS}'.encode()).decode()
    req = urllib.request.Request(url, data=query,
        headers={'Content-Type': 'application/json', 'Authorization': f'Basic {credentials}'},
        method='GET')
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
    hits = result.get('hits', {}).get('hits', [])
    ids = [h['_source']['RestaurantID'] for h in hits]
    return random.sample(ids, min(3, len(ids)))

def get_details(biz_id):
    table = dynamodb.Table('yelp-restaurants')
    resp = table.get_item(Key={'BusinessID': biz_id})
    return resp.get('Item', {})

def send_email(to, cuisine, num, dining_date, time, restaurants):
    lines = [f'{i+1}. {r.get("Name","?")}, located at {r.get("Address","?")}' 
             for i, r in enumerate(restaurants)]
    
    # Format time nicely e.g. "7:00 PM"
    try:
        from datetime import datetime
        pretty_time = datetime.strptime(time, '%H:%M').strftime('%I:%M %p')
    except Exception:
        pretty_time = time

    # Format date nicely e.g. "March 5, 2026"
    try:
        from datetime import datetime
        pretty_date = datetime.strptime(dining_date, '%Y-%m-%d').strftime('%B %d, %Y')
    except Exception:
        pretty_date = dining_date

    body = (
        f'Hello!\n\n'
        f'Here are my top {cuisine} restaurant suggestions '
        f'for {num} people on {pretty_date} at {pretty_time}:\n\n'
        + '\n'.join(lines) +
        '\n\nEnjoy your meal!'
    )

    ses.send_email(
        Source=FROM_EMAIL,
        Destination={'ToAddresses': [to]},
        Message={
            'Subject': {'Data': f'{cuisine} Restaurant Suggestions'},
            'Body':    {'Text': {'Data': body}}
        }
    )

def lambda_handler(event, context):
    resp = sqs.receive_message(QueueUrl=SQS_URL, MaxNumberOfMessages=1)
    msgs = resp.get('Messages', [])
    if not msgs:
        return {'statusCode': 200, 'body': 'No messages'}
    
    msg  = msgs[0]
    body = json.loads(msg['Body'])
    
    cuisine     = body.get('Cuisine', '')
    email       = body.get('Email', '')
    num         = body.get('NumberOfPeople', '2')
    dining_date = body.get('DiningDate', '')
    time        = body.get('DiningTime', 'your requested time')

    ids   = es_search(cuisine)
    rests = [get_details(i) for i in ids]
    rests = [r for r in rests if r]

    if rests and email:
        send_email(email, cuisine, num, dining_date, time, rests)
        print(f'Email sent to {email}')

    sqs.delete_message(QueueUrl=SQS_URL, ReceiptHandle=msg['ReceiptHandle'])
    return {'statusCode': 200, 'body': 'Done'}