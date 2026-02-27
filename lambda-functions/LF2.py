import json, boto3, random, os, urllib.request, urllib.parse
import base64
from urllib.error import URLError
 
sqs      = boto3.client('sqs',      region_name='us-east-1')
dynamodb = boto3.resource('dynamodb',region_name='us-east-1')
ses      = boto3.client('ses',       region_name='us-east-1')
 
SQS_URL  = os.environ['SQS_QUEUE_URL']
ES_HOST  = os.environ['ES_HOST']          # your OpenSearch domain endpoint
ES_USER  = os.environ['ES_USER']
ES_PASS  = os.environ['ES_PASS']
FROM_EMAIL = os.environ['FROM_EMAIL']
 
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
 
def send_email(to, cuisine, num, time, restaurants):
    lines = [f'{i+1}. {r.get("Name","?")}, located at {r.get("Address","?")}' for i,r in enumerate(restaurants)]
    body = f'Hello!\n\nHere are my {cuisine} restaurant suggestions for {num} people at {time}:\n\n'
    body += '\n'.join(lines) + '\n\nEnjoy your meal!'
    ses.send_email(
        Source=FROM_EMAIL,
        Destination={'ToAddresses': [to]},
        Message={'Subject': {'Data': f'{cuisine} Restaurant Suggestions'},
                 'Body':    {'Text': {'Data': body}}}
    )
 
def lambda_handler(event, context):
    resp = sqs.receive_message(QueueUrl=SQS_URL, MaxNumberOfMessages=1)
    msgs = resp.get('Messages', [])
    if not msgs:
        return {'statusCode': 200, 'body': 'No messages'}
    msg = msgs[0]
    body = json.loads(msg['Body'])
    cuisine = body.get('Cuisine','')
    email   = body.get('Email','')
    num     = body.get('NumberOfPeople','2')
    time    = body.get('DiningTime','your requested time')
    ids = es_search(cuisine)
    rests = [get_details(i) for i in ids]
    rests = [r for r in rests if r]
    if rests and email:
        send_email(email, cuisine, num, time, rests)
        print(f'Email sent to {email}')
    sqs.delete_message(QueueUrl=SQS_URL, ReceiptHandle=msg['ReceiptHandle'])
    return {'statusCode': 200, 'body': 'Done'}
