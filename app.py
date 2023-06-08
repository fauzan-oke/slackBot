
import os
import requests
from pathlib import Path
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.signature import SignatureVerifier
from flask import Flask, request


env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

app = Flask(__name__)
signing_secret = os.environ['SLACK_SIGNING_SECRET']
bot_token = os.environ['SLACK_TOKEN']
chatbase_secret = os.environ['CHATBASE_SECRET']
verifier = SignatureVerifier(signing_secret)
slack_client = WebClient(token=bot_token)
BOT_ID = slack_client.api_call("auth.test")['user_id']
chat_id = os.environ['CHATBOT_ID']
api_url = 'https://www.chatbase.co/api/v1/chat'

# Keep track of processed event IDs
processed_event_ids = set()

# def send_message(channel, message):
#     try:
#         response = slack_client.chat_postMessage(channel=channel, text=message)
#         return response["ok"]
#     except Exception as e:
#         print("Error sending message to Slack:", e)
def read_chatbot_reply(messages):
    try:
        headers = {
            'Authorization': f"Bearer {chatbase_secret}",
            'Content-Type': 'application/json'
        }
        
        data = {
            'messages': messages,
            'chatId': chat_id,
            'stream': True,
            'temperature': 0
        }
        
        response = requests.post(api_url, json=data, headers=headers, stream=True)
        response.raise_for_status()
        
        decoder = response.iter_content(chunk_size=None)
        result = ''
        for chunk in decoder:
            chunk_value = chunk.decode('utf-8')
            # print(chunk_value, end='', flush=True)
            result += chunk_value
        
        return result
        
    except requests.exceptions.RequestException as error:
        print('Error:', error)

def send_message(channel, message, thread_ts=None):
    try:
        response = slack_client.chat_postMessage(channel=channel, text=message, thread_ts=thread_ts)
        return response["ok"]
    except Exception as e:
        print("Error sending message to Slack:", e)        

def send_to_chatbase(messages):
    url = "https://www.chatbase.co/api/v1/chat"
    headers = {
        "Authorization": f"Bearer {chatbase_secret}",
        "Content-Type": "application/json"
    }
    payload = {
        "messages": messages,
        "chatId": chat_id,
        "stream": False,
        "temperature": 0.7
    }
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print("Error sending message to Chatbase:", e)
    return None

@app.route("/slack/events", methods=["POST"])
def handle_events():

    # Parse the event payload
    payload = request.get_json()
    event_type = payload.get("type")
    
    if event_type == "url_verification":
        challenge = payload.get("challenge")
        return challenge
    
    # Verify the request signature
    # request_body = request.get_data(as_text=True)
    # timestamp = request.headers.get("X-Slack-Request-Timestamp")
    # signature = request.headers.get("X-Slack-Signature")
    # if not verifier.is_valid_request(request_body, timestamp, signature):
        # return "Invalid request signature", 403

    # Handle message events
    if event_type == "event_callback":
        event = payload.get("event")
        event_id = payload.get("event_id")
        
        if event_id in processed_event_ids:
            # Event already processed, skip
            return "Event already processed"
        
        processed_event_ids.add(event_id)
        
        if event.get("type") == "message" and "text" in event:
            channel_id = event["channel"]
            user_id = event["user"]
            text = event["text"]
            if BOT_ID != user_id:
                # Send message to Chatbase
                chatbase_message = {
                    "content": text,
                    "role": "user"
                }
                chatbase_response = read_chatbot_reply([chatbase_message])
                if chatbase_response:
#                     # Get the response from Chatbase
                    response_message = chatbase_response
#                     # Send the response back to the user in a reply thread
                    send_message(channel_id, response_message, thread_ts=event["ts"])
                else:
                    send_message(channel_id, "Error processing the message.",thread_ts=event["ts"])
    
    return "Event handled"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
