import requests
import json

MATON_API_KEY = 'ROYRvh0kgo-fjBXp7AyN1sDvjWsGGdk_lnx1h7PKO4mFVBW4TFrIn33_DgVZgmQymZoh9Sq84qIqX5NQUqpsohgE0QRmGY2vizY'
BASE_URL = 'https://gateway.maton.ai/google-mail/gmail/v1/users/me/messages'

def gmail_metadata_resolver():
    headers = {
        'Authorization': f'Bearer {MATON_API_KEY}'
    }
    
    try:
        response = requests.get(f'{BASE_URL}?maxResults=20', headers=headers)
        response.raise_for_status()
        messages_list = response.json().get('messages', [])
    except requests.RequestException as e:
        return f"Error fetching message list: {e}"

    if not messages_list:
        return "No recent messages found."

    metadata = []
    for msg in messages_list:
        msg_id = msg['id']
        try:
            msg_response = requests.get(f'{BASE_URL}/{msg_id}', headers=headers)
            msg_response.raise_for_status()
            msg_data = msg_response.json()
            
            headers_list = msg_data.get('payload', {}).get('headers', [])
            subject = next((h['value'] for h in headers_list if h['name'] == 'Subject'), 'N/A')
            from_header = next((h['value'] for h in headers_list if h['name'] == 'From'), 'N/A')
            
            metadata.append({'id': msg_id, 'subject': subject, 'from': from_header})
        except requests.RequestException as e:
            metadata.append({'id': msg_id, 'error': f'Could not fetch details: {e}'})
            
    return json.dumps(metadata, indent=2)

if __name__ == "__main__":
    print(gmail_metadata_resolver())