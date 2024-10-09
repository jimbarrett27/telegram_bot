from telegram_bot.messaging import send_message_to_me
from llm.query import get_a_poem, is_this_paper_interesting, rate_this_paper
from util.arxiv import get_latest_ids_and_abstracts, make_link_to_arxiv

ids_and_abstracts = get_latest_ids_and_abstracts()

send_message_to_me(f"Starting to look through {len(ids_and_abstracts)} papers")

paper_id_to_score = {}
for paper_id, abstract in ids_and_abstracts.items():
    abstract_rating = rate_this_paper(abstract) 
    paper_id_to_score[paper_id] = abstract_rating

top_10_papers = sorted(paper_id_to_score.items(), key=lambda x: x[1], reverse=True)

message = ""
for i, (paper, score) in enumerate(top_10_papers):
    message += f"""
    Paper #{i+1}
    {make_link_to_arxiv(paper)}

    {ids_and_abstracts[paper]}

    """

send_message_to_me(message)