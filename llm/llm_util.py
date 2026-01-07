from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from gcp_util.secrets import get_gemini_api_key
from util.logging_util import setup_logger, log_llm_interaction
import time

logger = setup_logger(__name__)

def get_llm_response(template_path: str, params: dict, model_name: str = "gemini-3-flash-preview") -> str:
    """
    Generates a response from the LLM based on a Jinja2 template file and parameters.

    Args:
        template_path: The absolute path to the Jinja2 template file.
        params: A dictionary of parameters to populate the template.
        model_name: The name of the Gemini model to use. Defaults to "gemini-3-flash-preview".

    Returns:
        The string response from the LLM.
    """
    start_time = time.time()
    
    api_key = get_gemini_api_key()
    
    llm = ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=api_key
    )

    with open(template_path, "r") as f:
        template_content = f.read()

    # Create a prompt template that treats the input as a Jinja2 template
    prompt = PromptTemplate.from_template(template_content, template_format="jinja2")
    chain = prompt | llm

    response = chain.invoke(params)
    
    # LangChain Chat models return an AIMessage, we want the content string
    # Gemini returns content as a list of parts, extract the text
    response_content = response.content
    
    # If response is a list of content parts, extract the text
    if isinstance(response_content, list):
        text_parts = [part.get('text', '') for part in response_content if isinstance(part, dict) and 'text' in part]
        response_content = ''.join(text_parts)
    
    # Log the interaction
    duration_ms = (time.time() - start_time) * 1000
    log_llm_interaction(logger, template_path, params, response_content, model_name, duration_ms)
    
    return response_content
