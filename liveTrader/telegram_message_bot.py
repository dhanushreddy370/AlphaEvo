
import requests

def send_telegram_message(message, bot_token, chat_id):
    """
    Sends a message using a specific bot token and chat ID.
    
    Args:
        message (str): The text message to send.
        bot_token (str): The API token of the bot that will send the message.
        chat_id (str or int): The ID of the chat to send the message to.
    """
    if not bot_token or not chat_id:
        print("Telegram Error: Bot Token or Chat ID is missing.")
        return
        
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    try:
        response = requests.post(url, data=payload)
        if response.status_code != 200:
            print(f"Telegram message failed for bot token ...{bot_token[-4:]}: {response.text}")
    except Exception as e:
        print(f"Telegram error: {e}")
