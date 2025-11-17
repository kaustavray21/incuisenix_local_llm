from django.conf import settings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from operator import itemgetter 
from .vector_store.retriever import get_retriever


LLM_MODEL = "gemini-2.5-flash" 

# --- NEW: A more advanced classifier ---
def get_query_type_classifier_chain():
    """
    Classifies the user's question into one of three categories:
    1.  Fetch_Notes: A request to list, summarize, or get all notes.
    2.  RAG: A specific question about the video content that requires context.
    3.  General: A general knowledge question not related to the video.
    """
    prompt = ChatPromptTemplate.from_template(
        "Classify the user's question into one of three categories: 'Fetch_Notes', 'RAG', or 'General'.\n"
        "1.  'Fetch_Notes' questions are requests to list, see, or get all personal notes. "
        "    Examples: 'show me all my notes', 'what notes do I have?', 'list my notes for this video'.\n"
        "2.  'RAG' questions ask something specific about the video content, the user's notes, or the transcript. "
        "    Examples: 'what did the video say about variables?', 'explain my note on functions', 'what is a decorator?'.\n"
        "3.  'General' questions are for information not in the video or notes. "
        "    Examples: 'hello', 'who are you?', 'what is the capital of France?'.\n\n"
        "Respond with ONLY the category name ('Fetch_Notes', 'RAG', or 'General').\n\n"
        "Question: {question}\nCategory:"
    )
    llm = ChatGoogleGenerativeAI(model=LLM_MODEL, google_api_key=settings.GEMINI_API_KEY, temperature=0)
    return prompt | llm | StrOutputParser()
# --- END NEW ---


def get_rag_chain(video_id: str, user_id: int | None):
    retriever = get_retriever(video_id, user_id=user_id)

    prompt_template = """
    You are a helpful AI assistant for the InCuiseNix e-learning platform.
    Your goal is to provide accurate and helpful answers based on the user's question and the context provided.

    Use the following sources to answer the user's question:
    1.  **Video Context**: Key information retrieved from the video transcript and the user's personal notes.
    2.  **Chat History**: The ongoing conversation between you and the user.

    CONTEXT:
    {context}

    CHAT HISTORY:
    {chat_history}

    QUESTION:
    {question}
    """
    
    prompt = ChatPromptTemplate.from_template(prompt_template)
    llm = ChatGoogleGenerativeAI(model=LLM_MODEL, google_api_key=settings.GEMINI_API_KEY)

    rag_chain = (
        {
            "context": itemgetter("question") | retriever,
            "question": itemgetter("question"),
            "chat_history": itemgetter("chat_history"),
        }
        | prompt
        | llm
        | StrOutputParser()
    )

    return rag_chain


def get_general_chain():
    prompt = ChatPromptTemplate.from_template(
        "You are a helpful AI assistant. Answer the following question to the best of your ability.\nQuestion: {question}"
    )
    llm = ChatGoogleGenerativeAI(model=LLM_MODEL, google_api_key=settings.GEMINI_API_KEY)
    return prompt | llm | StrOutputParser()


def get_summarizer_chain():
    prompt_template = """
    You are an expert AI assistant for the InCuiseNix e-learning platform.
    Your task is to provide a concise and helpful summary of the video transcript provided below.
    Based *only* on the following CONTEXT from the video, please answer the user's request.
    
    CONTEXT:
    {context}

    REQUEST:
    {question}
    """
    prompt = ChatPromptTemplate.from_template(prompt_template)
    llm = ChatGoogleGenerativeAI(model=LLM_MODEL, google_api_key=settings.GEMINI_API_KEY)
    return prompt | llm | StrOutputParser()

def get_time_based_chain():
    prompt_template = """
    You are an expert AI assistant for a video learning platform.
    The user has asked what is being discussed at a specific moment in the video.
    The following CONTEXT is the transcript from that exact moment.
    Your task is to carefully analyze this CONTEXT and concisely explain the main topic, concept, or action being discussed.
    Synthesize the information into a clear and helpful summary. Do not state that the context is insufficient.
    
    CONTEXT:
    {context}

    Based *only* on the context provided above, what is being discussed?
    """
    prompt = ChatPromptTemplate.from_template(prompt_template)
    llm = ChatGoogleGenerativeAI(model=LLM_MODEL, google_api_key=settings.GEMINI_API_KEY)
    return prompt | llm | StrOutputParser()