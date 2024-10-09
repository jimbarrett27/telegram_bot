from telegram_bot.messaging import send_message_to_me

def bot_entrypoint(request_data: dict):
    """
    Simple hello world route to act as a webhook for my telegram bot.
    Simply echos the message I send it back to me
    """

    request_data = {"message": {"text": "echo is it working buddyboy?"}}
    # request_data = request.get_json()
    message = request_data["message"]

    handle_bot_request(message["text"].lower())

    return ""


def handle_bot_request(message: str):
    """
    Given a message sent to the telegram bot,
    parse it, and perform the appropriate action
    """

    split_message = message.split(" ")
    command = split_message[0]
    body = " ".join(split_message[1:])

    if command == "echo":
        send_message_to_me(body)
    else:
        send_message_to_me(f"'{command}' is an unknown command. Try again 😇")
