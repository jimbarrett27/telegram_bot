from telegram_bot.telegram_bot import send_message
from swedish.database import get_all_words, add_card, get_due_cards
from swedish.flash_card import WordType
import random

def handle_message(message: str, chat_id: str):

    command = message.split()[0]

    if command not in COMMAND_TO_MESSAGE_HANDLER:
        send_message(chat_id, f"Unrecognised command: {command}")
    else:
        command_to_send = (' '.join(message.split()[1:])).strip()
        COMMAND_TO_MESSAGE_HANDLER[command](command_to_send, chat_id)

def add_word(message: str, chat_id: str):

    splitted_message = message.split()
    word_type_str = splitted_message[0]
    word = (' '.join(splitted_message[1:]))

    if word_type_str not in WORD_TYPE_STR_TO_ENUM:
        send_message(chat_id, f"Word type must be one of {list(WORD_TYPE_STR_TO_ENUM)}")
        return False

    all_words = set(get_all_words())
    if word in all_words:
        send_message(chat_id, "Word already in dictionary")
        return True

    # TODO: validate word

    send_message(chat_id, f'Adding the word "{word}" as a {word_type_str}')
    add_card(word, WORD_TYPE_STR_TO_ENUM[word_type_str])

    return True

def practise_random_word(_, chat_id):
    
    print('here?')

    due_cards = get_due_cards()
    chosen_card = random.choice(due_cards)

    # TODO: modify word form

    send_message(chat_id, f"Give a definition for the word;\n{chosen_card.word_to_learn}")

    # TODO: grade the definition
    # TODO: update score

COMMAND_TO_MESSAGE_HANDLER = {
    "add": add_word,
    "practise": practise_random_word
}

WORD_TYPE_STR_TO_ENUM = {
    'noun': WordType.NOUN,
    'verb': WordType.VERB,
    'adj': WordType.ADJECTIVE,
    'auto': WordType.UNKNOWN
}