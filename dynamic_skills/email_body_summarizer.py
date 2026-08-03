import json

def execute(arguments):
    # This is a mock implementation for the sandbox test.
    # In a real scenario, this would integrate with an email API
    # to fetch the body and then use a summarization model.
    
    email_id = arguments.get("email_id", "19f55b7d7a9b85b7") # Example Ollama email ID
    
    # Mock email bodies based on context
    mock_emails = {
        "19f55b7d7a9b85b7": {
            "subject": "Ollama session usage at 90%",
            "body": "Hello Bob, This is an alert to inform you that your Ollama session usage has reached 90% of your allocated limit. To avoid interruption of service, please consider upgrading your plan or optimizing your current usage. If you have any questions or feel free to reach out, we're here to help - The Ollama team."
        }
    }
    
    email = mock_emails.get(email_id)
    
    if email:
        summary = f"Summary of '{email['subject']}': {email['body']}"
        return summary
    else:
        return f"Email with ID {email_id} not found."

if __name__ == "__main__":
    print(execute({"email_id": "19f55b7d7a9b85b7"}))