from telegram_bot.messaging import send_message_to_me
from llm.query import get_a_poem, is_this_paper_interesting, rate_this_paper
from util.arxiv import get_latest_ids_and_abstracts, make_link_to_arxiv

ids_and_abstracts = get_latest_ids_and_abstracts()

print(len(ids_and_abstracts))


breakpoint()