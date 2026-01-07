from telegram_bot.telegram_bot import send_message
from swedish.database import get_all_words, add_card, get_due_cards, get_card, update_card as db_update_card, get_next_due_card
from swedish.flash_card import WordType
from swedish.fsrs import update_card as fsrs_update_card, Grade, log_fsrs_update
from util.logging_util import setup_logger
import random
from util.constants import REPO_ROOT
import json
from llm.llm_util import get_llm_response
from enum import Enum, auto

class ConversationState(Enum):
    IDLE = auto()
    AWAITING_PRACTICE_ANSWER = auto()

# Map<chat_id, {state: ConversationState, context: dict}>
USER_STATES = {}

logger = setup_logger(__name__)

def get_llm_prompt_template(filename: str):

    return (REPO_ROOT / "swedish/prompts") / filename

def handle_message(message: str, chat_id: str):
    
    # Check for active conversation state
    if chat_id in USER_STATES and USER_STATES[chat_id]['state'] != ConversationState.IDLE:
        current_state_info = USER_STATES[chat_id]
        if current_state_info['state'] == ConversationState.AWAITING_PRACTICE_ANSWER:
            handle_practice_answer(message, chat_id, current_state_info['context'])
        return

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

    # Validate word with LLM
    try:
        response = get_llm_response(
            str(get_llm_prompt_template("validate_word.jinja2")),
            {"word": word, "word_type": WORD_TYPE_STR_TO_VERBOSE_WORD_TYPE.get(word_type_str, word_type_str)}
        )
        # Clean up code blocks if present
        clean_response = response.replace("```json", "").replace("```", "").strip()
        validation_result = json.loads(clean_response)
        
        if not validation_result.get("valid", False):
            send_message(chat_id, f"Logic says no: {validation_result.get('reasoning', 'No reason provided')}")
            return False

    except Exception as e:
        send_message(chat_id, f"Error validating word: {e}")
        return False

    send_message(chat_id, f'Adding the word "{word}" as a {word_type_str}')
    add_card(word, WORD_TYPE_STR_TO_ENUM[word_type_str])

    return True

def handle_practice_answer(message: str, chat_id: str, context: dict):
    shown_word = context.get('shown_word')
    
    try:
        response = get_llm_response(
            str(get_llm_prompt_template("grade_translation.jinja2")),
            {"swedish_word": shown_word, "user_translation": message}
        )
        clean_response = response.replace("```json", "").replace("```", "").strip()
        result = json.loads(clean_response)
        
        grade_str = result.get('grade', 'FORGOT')
        try:
            grade = Grade[grade_str]
        except KeyError:
            grade = Grade.FORGOT

        is_correct = grade != Grade.FORGOT
        
        if is_correct:
            send_message(chat_id, f"✅ Correct! ({grade.name})\n{result.get('feedback')}")
        else:
            send_message(chat_id, f"❌ Incorrect.\nCorrect translation: {result.get('correct_translation')}\nFeedback: {result.get('feedback')}")

        # Update FSRS state
        word_to_learn = context.get('word_to_learn')
        card = get_card(word_to_learn)
        if card:
            new_card = fsrs_update_card(card, grade)
            db_update_card(new_card)
            
            log_fsrs_update(logger, card, new_card, grade)

    except Exception as e:
        send_message(chat_id, f"Error grading answer: {e}")
    
    # Reset state to IDLE
    USER_STATES[chat_id] = {'state': ConversationState.IDLE, 'context': {}}

def practise_random_word(_, chat_id):
    
    due_cards = get_due_cards()
    if not due_cards:
        chosen_card = get_next_due_card()
    else:
        chosen_card = random.choice(due_cards)

    # Modify word form using LLM
    word_to_show = chosen_card.word_to_learn
    try:
        template = None
        params = {}
        
        if chosen_card.word_type == WordType.NOUN:
            template = "modify_noun_form.jinja2"
            params = {"noun": chosen_card.word_to_learn}
        elif chosen_card.word_type == WordType.VERB:
            template = "modify_verb_form.jinja2"
            params = {"verb": chosen_card.word_to_learn}
        elif chosen_card.word_type == WordType.ADJECTIVE:
            template = "modify_adjective_form.jinja2"
            params = {"adjective": chosen_card.word_to_learn}
            
        if template:
            response = get_llm_response(str(get_llm_prompt_template(template)), params)
            clean_response = response.replace("```json", "").replace("```", "").strip()

            forms = json.loads(clean_response)
            
            if forms:
                form_type, modified_word = random.choice(list(forms.items()))
                word_to_show = f"{modified_word}"

    except Exception as e:
        send_message(chat_id, f"Error modifying word form: {e}. Falling back to original word.")
        # Fallback to original word

    send_message(chat_id, f"Give a definition for the word;\n{word_to_show}")
    
    # Set state
    USER_STATES[chat_id] = {
        'state': ConversationState.AWAITING_PRACTICE_ANSWER,
        'context': {
            'word_to_learn': chosen_card.word_to_learn,
            'shown_word': word_to_show,
        }
    }

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

WORD_TYPE_STR_TO_VERBOSE_WORD_TYPE = {
    'noun': "noun",
    'verb': "verb",
    'adj': "adjective"
}