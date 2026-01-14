import json
import random
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

from swedish.database import (
    get_all_words,
    add_card,
    get_due_cards,
    get_card,
    update_card as db_update_card,
    get_next_due_card,
)
from swedish.flash_card import WordType
from swedish.fsrs import update_card as fsrs_update_card, Grade, log_fsrs_update
from util.logging_util import setup_logger
from util.constants import REPO_ROOT
from llm.llm_util import get_llm_response

logger = setup_logger(__name__)

# Conversation states
AWAITING_PRACTICE_ANSWER = 0
AWAITING_WORD_TYPE = 1
AWAITING_WORD = 2

# Main menu keyboard (imported where needed)
MAIN_MENU_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["🇸🇪 Practise", "📝 Add Word"],
        ["📚 Papers Status", "🔍 Scan Papers"],
        ["❓ Help"],
    ],
    resize_keyboard=True,
)

WORD_TYPE_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("🔤 Noun", callback_data="add_noun"),
        InlineKeyboardButton("🏃 Verb", callback_data="add_verb"),
    ],
    [
        InlineKeyboardButton("✨ Adjective", callback_data="add_adj"),
        InlineKeyboardButton("🤖 Auto-detect", callback_data="add_auto"),
    ],
    [InlineKeyboardButton("❌ Cancel", callback_data="add_cancel")],
])

WORD_TYPE_STR_TO_ENUM = {
    "noun": WordType.NOUN,
    "verb": WordType.VERB,
    "adj": WordType.ADJECTIVE,
    "auto": WordType.UNKNOWN,
}

WORD_TYPE_STR_TO_VERBOSE = {
    "noun": "noun",
    "verb": "verb",
    "adj": "adjective",
}


def get_llm_prompt_template(filename: str):
    return (REPO_ROOT / "swedish/prompts") / filename


async def start_practice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start a practice session - present a word to translate."""
    due_cards = get_due_cards()
    if not due_cards:
        chosen_card = get_next_due_card()
    else:
        chosen_card = random.choice(due_cards)

    if not chosen_card:
        await update.message.reply_text(
            "No flashcards available yet. Add some words first!",
            reply_markup=MAIN_MENU_KEYBOARD,
        )
        return ConversationHandler.END

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
        logger.error(f"Error modifying word form: {e}. Using original word.")

    # Store context for answer handling
    context.user_data["practice_word_to_learn"] = chosen_card.word_to_learn
    context.user_data["practice_shown_word"] = word_to_show

    await update.message.reply_text(
        f"Give a definition for the word:\n\n**{word_to_show}**",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(
            [["🚫 Cancel Practice"]],
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
    )

    return AWAITING_PRACTICE_ANSWER


async def handle_practice_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the user's answer to a practice question."""
    message = update.message.text

    # Check for cancel
    if message == "🚫 Cancel Practice":
        await update.message.reply_text(
            "Practice cancelled.",
            reply_markup=MAIN_MENU_KEYBOARD,
        )
        return ConversationHandler.END

    shown_word = context.user_data.get("practice_shown_word")
    word_to_learn = context.user_data.get("practice_word_to_learn")

    try:
        response = get_llm_response(
            str(get_llm_prompt_template("grade_translation.jinja2")),
            {"swedish_word": shown_word, "user_translation": message},
        )
        clean_response = response.replace("```json", "").replace("```", "").strip()
        result = json.loads(clean_response)

        grade_str = result.get("grade", "FORGOT")
        try:
            grade = Grade[grade_str]
        except KeyError:
            grade = Grade.FORGOT

        is_correct = grade != Grade.FORGOT

        if is_correct:
            response_text = f"✅ Correct! ({grade.name})\n{result.get('feedback')}"
        else:
            response_text = f"❌ Incorrect.\nCorrect translation: {result.get('correct_translation')}\nFeedback: {result.get('feedback')}"

        await update.message.reply_text(response_text, reply_markup=MAIN_MENU_KEYBOARD)

        # Update FSRS state
        card = get_card(word_to_learn)
        if card:
            new_card = fsrs_update_card(card, grade)
            db_update_card(new_card)
            log_fsrs_update(logger, card, new_card, grade)

    except Exception as e:
        logger.error(f"Error grading answer: {e}")
        await update.message.reply_text(
            f"Error grading answer: {e}",
            reply_markup=MAIN_MENU_KEYBOARD,
        )

    return ConversationHandler.END


async def cancel_practice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the practice conversation."""
    await update.message.reply_text(
        "Practice cancelled.",
        reply_markup=MAIN_MENU_KEYBOARD,
    )
    return ConversationHandler.END


async def start_add_word(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the add word flow - show word type selection."""
    await update.message.reply_text(
        "What type of word do you want to add?",
        reply_markup=WORD_TYPE_KEYBOARD,
    )
    return AWAITING_WORD_TYPE


async def handle_word_type_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the word type button selection."""
    query = update.callback_query
    await query.answer()

    callback_data = query.data

    if callback_data == "add_cancel":
        await query.edit_message_text("Word addition cancelled.")
        return ConversationHandler.END

    # Parse word type from callback
    word_type = callback_data.replace("add_", "")
    context.user_data["add_word_type"] = word_type

    type_display = WORD_TYPE_STR_TO_VERBOSE.get(word_type, word_type)
    await query.edit_message_text(f"Adding a {type_display}. Type the word now:")

    return AWAITING_WORD


async def handle_word_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the actual word input."""
    word = update.message.text.strip()
    word_type = context.user_data.get("add_word_type", "auto")

    success = await _add_word_internal(update, word_type, word)

    return ConversationHandler.END


async def _add_word_internal(update: Update, word_type_str: str, word: str) -> bool:
    """Internal function to add a word to the database."""
    if word_type_str not in WORD_TYPE_STR_TO_ENUM:
        await update.message.reply_text(
            f"Word type must be one of {list(WORD_TYPE_STR_TO_ENUM)}",
            reply_markup=MAIN_MENU_KEYBOARD,
        )
        return False

    all_words = set(get_all_words())
    if word in all_words:
        await update.message.reply_text(
            "Word already in dictionary",
            reply_markup=MAIN_MENU_KEYBOARD,
        )
        return True

    # Validate word with LLM
    try:
        response = get_llm_response(
            str(get_llm_prompt_template("validate_word.jinja2")),
            {"word": word, "word_type": WORD_TYPE_STR_TO_VERBOSE.get(word_type_str, word_type_str)},
        )
        clean_response = response.replace("```json", "").replace("```", "").strip()
        validation_result = json.loads(clean_response)

        if not validation_result.get("valid", False):
            await update.message.reply_text(
                f"Logic says no: {validation_result.get('reasoning', 'No reason provided')}",
                reply_markup=MAIN_MENU_KEYBOARD,
            )
            return False

    except Exception as e:
        await update.message.reply_text(
            f"Error validating word: {e}",
            reply_markup=MAIN_MENU_KEYBOARD,
        )
        return False

    await update.message.reply_text(
        f'Adding the word "{word}" as a {word_type_str}',
        reply_markup=MAIN_MENU_KEYBOARD,
    )
    add_card(word, WORD_TYPE_STR_TO_ENUM[word_type_str])

    return True


async def cancel_add_word(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the add word conversation."""
    await update.message.reply_text(
        "Word addition cancelled.",
        reply_markup=MAIN_MENU_KEYBOARD,
    )
    return ConversationHandler.END


def get_practice_conversation_handler() -> ConversationHandler:
    """Create the conversation handler for practice sessions."""
    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(r"^🇸🇪 Practise$"), start_practice),
        ],
        states={
            AWAITING_PRACTICE_ANSWER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_practice_answer),
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex(r"^🚫 Cancel"), cancel_practice),
        ],
        name="practice_conversation",
        persistent=False,
    )


def get_add_word_conversation_handler() -> ConversationHandler:
    """Create the conversation handler for adding words."""
    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(r"^📝 Add Word$"), start_add_word),
        ],
        states={
            AWAITING_WORD_TYPE: [
                CallbackQueryHandler(handle_word_type_selection, pattern=r"^add_"),
            ],
            AWAITING_WORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_word_input),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(handle_word_type_selection, pattern=r"^add_cancel$"),
        ],
        name="add_word_conversation",
        persistent=False,
        per_message=False,
    )


async def handle_text_command_async(
    update: Update, context: ContextTypes.DEFAULT_TYPE, command: str
) -> None:
    """Handle text-based commands (sv add ..., sv practise, etc.)."""
    if not command.strip():
        await _show_help(update)
        return

    parts = command.split()
    cmd = parts[0].lower()

    if cmd == "help":
        await _show_help(update)
    elif cmd == "practise":
        # Start practice directly via text command
        await start_practice(update, context)
    elif cmd == "add":
        if len(parts) < 3:
            await update.message.reply_text(
                "Usage: sv add <type> <word>\nTypes: noun, verb, adj, auto",
                reply_markup=MAIN_MENU_KEYBOARD,
            )
            return
        word_type = parts[1].lower()
        word = " ".join(parts[2:])
        await _add_word_internal(update, word_type, word)
    else:
        await _show_help(update)


async def _show_help(update: Update) -> None:
    """Show help message for Swedish bot commands."""
    await update.message.reply_text(
        """Swedish learning commands:
sv add <type> <word> - Add a word (type: noun, verb, adj, auto)
sv practise - Practice a random flashcard

Or use the menu buttons!""",
        reply_markup=MAIN_MENU_KEYBOARD,
    )
