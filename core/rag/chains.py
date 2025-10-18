from django.conf import settings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from operator import itemgetter  # Import itemgetter to select items from the input dict
from .vector_store import get_retriever

# --- Constants ---
LLM_MODEL = "gemini-2.5-flash"  # Your preferred model

# --- Main RAG Chain (Corrected) ---

def get_rag_chain(video_id: str):
    """
    Creates a RAG chain that correctly pipes the question to the retriever
    and passes all context (retrieved docs, chat history, notes) to the prompt.
    """
    retriever = get_retriever(video_id)

    prompt_template = """
    You are a helpful AI assistant for the InCuiseNix e-learning platform.
    Your goal is to provide accurate and helpful answers based on the user's question and the context provided.

    Use the following sources to answer the user's question:
    1.  **Video Context**: Key information retrieved from the video transcript.
    2.  **Chat History**: The ongoing conversation between you and the user.
    3.  **User's Notes**: Notes the user has taken on the current video.

    CONTEXT:
    {context}

    CHAT HISTORY:
    {chat_history}

    USER'S NOTES:
    {notes}

    QUESTION:
    {question}
    """
    
    prompt = ChatPromptTemplate.from_template(prompt_template)
    llm = ChatGoogleGenerativeAI(model=LLM_MODEL, google_api_key=settings.GEMINI_API_KEY)

    # This structure fixes the TypeError by ensuring the retriever only gets the 'question' string.
    rag_chain = (
        {
            "context": itemgetter("question") | retriever,
            "question": itemgetter("question"),
            "chat_history": itemgetter("chat_history"),
            "notes": itemgetter("notes"),
        }
        | prompt
        | llm
        | StrOutputParser()
    )

    return rag_chain

# --- Specialized and Utility Chains ---

def get_general_chain():
    """Chain for general knowledge questions."""
    prompt = ChatPromptTemplate.from_template(
        "You are a helpful AI assistant. Answer the following question to the best of your ability.\nQuestion: {question}"
    )
    llm = ChatGoogleGenerativeAI(model=LLM_MODEL, google_api_key=settings.GEMINI_API_KEY)
    return prompt | llm | StrOutputParser()

def get_classifier_chain():
    """Classifies a query as 'Video-Specific' or 'General Knowledge'."""
    prompt = ChatPromptTemplate.from_template(
        "Classify the user's question into one of two categories: 'Video-Specific' or 'General Knowledge'.\n"
        "A 'Video-Specific' question asks about the content of the video they are watching.\n"
        "A 'General Knowledge' question asks for information not specific to the video.\n"
        "Respond with ONLY the category name.\n\nQuestion: {question}\nCategory:"
    )
    llm = ChatGoogleGenerativeAI(model=LLM_MODEL, google_api_key=settings.GEMINI_API_KEY, temperature=0)
    return prompt | llm | StrOutputParser()

def get_decider_chain():
    """
    Decides whether to answer from context or use general knowledge.
    """
    prompt = ChatPromptTemplate.from_template(
        "You are a helpful routing assistant. Your job is to decide the best way to answer a user's question.\n"
        "You have been given a user's QUESTION and a CONTEXT retrieved from a video transcript.\n"
        "Your options are:\n"
        "1. 'RAG': If the CONTEXT is sufficient to answer the QUESTION, choose this.\n"
        "2. 'General': If the CONTEXT is empty or does not contain the information needed to answer the QUESTION, choose this.\n\n"
        "Respond with ONLY the word 'RAG' or 'General'.\n\n"
        "CONTEXT:\n{context}\n\nQUESTION:\n{question}\n\nDecision:"
    )
    llm = ChatGoogleGenerativeAI(model=LLM_MODEL, google_api_key=settings.GEMINI_API_KEY, temperature=0)
    return prompt | llm | StrOutputParser()

def get_summarizer_chain():
    """
    Creates a chain specifically for summarizing a large context.
    """
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
    """
    Creates a chain specifically for answering questions about a specific timestamp.
    """
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