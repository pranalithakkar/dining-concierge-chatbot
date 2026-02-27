import boto3
import requests
import json
import os
from requests.auth import HTTPBasicAuth

ENDPOINT = os.environ.get('OS_ENDPOINT', '')
USER     = 'admin'
PASS     = os.environ.get('OS_PASS', '')

auth     = HTTPBasicAuth(USER, PASS)
headers  = {'Content-Type': 'application/json'}

index_mapping = {
    'mappings': {
        'properties': {
            'RestaurantID': {'type': 'keyword'},
            'Cuisine':      {'type': 'keyword'}
        }
    }
}
r = requests.put(f'{ENDPOINT}/restaurants', auth=auth, headers=headers, json=index_mapping)
print('Create index:', r.status_code, r.text)

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
table = dynamodb.Table('yelp-restaurants')

response = table.scan()
items = response['Items']
while 'LastEvaluatedKey' in response:
    response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
    items.extend(response['Items'])

print(f'Uploading {len(items)} restaurants to OpenSearch...')
ok = 0
for item in items:
    doc = {
        'RestaurantID': item['BusinessID'],
        'Cuisine': item.get('Cuisine', '')
    }
    r = requests.post(
        f'{ENDPOINT}/restaurants/_doc',
        auth=auth,
        headers=headers,
        json=doc
    )
    if r.status_code in [200, 201]:
        ok += 1

print(f'Done! {ok}/{len(items)} loaded.')
