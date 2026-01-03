from langchain_mistralai import ChatMistralAI
from langchain_core.prompts import PromptTemplate
from gcp_util.secrets import get_mistral_api_key

def get_llm_response(template: str, params: dict, model_name: str = "mistral-large-latest") -> str:
    """
    Generates a response from the LLM based on a template and parameters.

    Args:
        template: The prompt template string.
        params: A dictionary of parameters to populate the template.
        model_name: The name of the Mistral model to use. Defaults to "mistral-large-latest".

    Returns:
        The string response from the LLM.
    """
    api_key = get_mistral_api_key()
    
    llm = ChatMistralAI(
        model=model_name,
        mistral_api_key=api_key
    )

    prompt = PromptTemplate.from_template(template)
    chain = prompt | llm

    response = chain.invoke(params)
    
    # LangChain Chat models return an AIMessage, we want the content string
    return response.content
