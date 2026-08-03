import requests
import json
import os

def execute(arguments):
    api_key = "ROYRvh0kgo-fjBXp7AyN1sDvjWsGGdk_lnx1h7PKO4mFVBW4TFrIn33_DgVZgmQymZoh9Sq84qIqX5NQUqpsohgE0QRmGY2vizY"
    url = "https://gateway.maton.ai/google-mail/gmail/v1/users/me/drafts"
    
    # Contextual parameters for the reply based on previous attempt
    to = arguments.get("to", "hello@ollama.com")
    subject = arguments.get("subject", "Re: Ollama session usage at 90%")
    body_content = arguments.get("body", "Thank you for the update. I will not be upgrading. I will wait for the reset, kind regards Bob Mcguffie")
    threadId = arguments.get("threadId", "19f55b7d7a9b85b7")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "to": to,
        "subject": subject,
        "body": body_content,
        "threadId": threadId
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        return f"Successfully created real draft: {response.json()}"
    except requests.exceptions.RequestException as e:
        return f"Error creating real draft: {e}"

if __name__ == "__main__":
    print(execute({}))