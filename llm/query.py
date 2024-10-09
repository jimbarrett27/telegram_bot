import requests 
from util.constants import LLM_SERVER_ADDRESS, GRAMMAR_DIR
from telegram_bot.messaging import send_message_to_me

from pathlib import Path

def format_prompt_for_llama_completion(
        main_prompt: str, 
        system_prompt: str = "You are a helpful AI assistant"
):
    
    return f"""
    <|begin_of_text|><|start_header_id|>system<|end_header_id|>
    {system_prompt}<|eot_id|>
    <|start_header_id|>user<|end_header_id|>
    {main_prompt}
    <|eot_id|><|start_header_id|>assistant<|end_header_id|>
    """
    
def get_completion_from_llama_cpp(prompt, grammar_file: Path = None):

    request_content = {
        "prompt": prompt
    }

    if grammar_file is not None:
        request_content["grammar"] = grammar_file.read_text()

    resp = requests.post(
        f'{LLM_SERVER_ADDRESS}/completion',
        json=request_content
    )

    return resp.json()["content"]

def get_a_poem(topic: str):

    prompt = format_prompt_for_llama_completion(
        f"Write me a fun limerick about {topic}.",
        system_prompt="You are a funny and creative AI who loves to write things for people"
    )

    print(get_completion_from_llama_cpp(prompt))


def is_this_paper_interesting(abstract: str):

    prompt = f"""
    I am a data scientist working in the field of pharmacovigilance. I am interested in any paper
    that is talking about AI or machine learning applied to pharmacovigilance data. I am also interested
    in novel visualisations of adverse event data.

    I have a paper with the following abstract;

    {abstract}

    Do you think I would be interested in this paper?
    """

    prompt = format_prompt_for_llama_completion(prompt)

    grammar_file = GRAMMAR_DIR / "yes_or_no.gbnf"

    print(get_completion_from_llama_cpp(prompt, grammar_file))

def rate_this_paper(abstract: str):

    prompt = f"""
    I am a data scientist working in the field of pharmacovigilance. I am interested in any paper
    that is talking about AI or machine learning applied to pharmacovigilance data. I am also interested
    in novel visualisations of adverse event data.

    I have a paper with the following abstract;

    {abstract}

    On a scale of 1 to 10, how interesting do you think I'd find this paper?
    """

    prompt = format_prompt_for_llama_completion(prompt)

    grammar_file = GRAMMAR_DIR / "1_to_10.gbnf"

    rating = int(get_completion_from_llama_cpp(prompt, grammar_file))

    return rating
          