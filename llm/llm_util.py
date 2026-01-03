from langchain_mistralai import ChatMistralAI
from langchain_core.prompts import PromptTemplate
from gcp_util.secrets import get_mistral_api_key

def get_llm_response(template_path: str, params: dict, model_name: str = "mistral-small-latest") -> str:
    """
    Generates a response from the LLM based on a Jinja2 template file and parameters.

    Args:
        template_path: The absolute path to the Jinja2 template file.
        params: A dictionary of parameters to populate the template.
        model_name: The name of the Mistral model to use. Defaults to "mistral-small-latest".

    Returns:
        The string response from the LLM.
    """
    api_key = get_mistral_api_key()
    
    llm = ChatMistralAI(
        model=model_name,
        mistral_api_key=api_key
    )

    with open(template_path, "r") as f:
        template_content = f.read()

    # Create a prompt template that treats the input as a Jinja2 template
    prompt = PromptTemplate.from_template(template_content, template_format="jinja2")
    chain = prompt | llm

    response = chain.invoke(params)
    
    # LangChain Chat models return an AIMessage, we want the content string
    return response.content
