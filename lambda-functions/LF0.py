import json
import boto3
import os

lex = boto3.client('lexv2-runtime', region_name='us-east-1')

BOT_ID       = os.environ.get('BOT_ID', '')
BOT_ALIAS_ID = os.environ.get('BOT_ALIAS_ID', '')
LOCALE_ID    = 'en_US'

def lambda_handler(event, context):
    print('Event:', json.dumps(event))
    body = event.get('body', '{}')
    if isinstance(body, str):
        body = json.loads(body)

    messages = body.get('messages', [])
    user_text = 'Hello'
    if messages:
        msg = messages[0]
        user_text = msg.get('unstructured', {}).get('text', 'Hello')

    session_id = 'user-session-001'

    lex_resp = lex.recognize_text(
        botId=BOT_ID, botAliasId=BOT_ALIAS_ID,
        localeId=LOCALE_ID, sessionId=session_id, text=user_text
    )

    bot_messages = lex_resp.get('messages', [])
    bot_text = "I'm still working on it. Please try again."
    if bot_messages:
        bot_text = bot_messages[0].get('content', bot_text)

    return {
        'statusCode': 200,
        'headers': {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
        },
        'body': json.dumps({
            'messages': [{'type': 'unstructured', 'unstructured': {'text': bot_text}}]
        })
    }