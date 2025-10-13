import os
import re
import pandas as pd
from django.conf import settings
from langchain_community.document_loaders import DataFrameLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
# from langchain_core.runnables import RunnablePassthrough
from core.models import Transcript
from langchain.schema import StrOutputParser

# --- Constants ---
FAISS_INDEX_PATH = os.path.join(settings.BASE_DIR, 'faiss_index')
TRANSCRIPTS_PATH = os.path.join(settings.MEDIA_ROOT, 'transcripts')
EMBEDDING_MODEL = "models/text-embedding-004"
LLM_MODEL = "gemini-2.5-flash"

# --- Global variable ---
vector_store = None

def get_vector_store():
    """Loads the FAISS index from disk if it exists, otherwise returns None."""
    global vector_store
    if vector_store is None:
        embedding_function = GoogleGenerativeAIEmbeddings(
            model=EMBEDDING_MODEL,
            google_api_key=settings.GEMINI_API_KEY
        )
        if os.path.exists(FAISS_INDEX_PATH):
            print("Loading existing FAISS index from disk...")
            vector_store = FAISS.load_local(
                FAISS_INDEX_PATH,
                embedding_function,
                allow_dangerous_deserialization=True
            )
            print("FAISS index loaded.")
        else:
            print("No FAISS index found. It will be created during the ingestion process.")
    return vector_store

def create_or_update_vector_store():
    """
    Loads transcripts directly from the database and creates/updates the FAISS vector store.
    This ensures the metadata uses the correct YouTube ID from the database records.
    """
    print("Loading transcripts from the database...")
    # Query all transcript objects and prefetch the related video
    transcripts = Transcript.objects.all().select_related('video')
    if not transcripts.exists():
        print("No transcripts found in the database. Run 'populate_transcripts' first.")
        return

    # Convert the queryset to a list of dictionaries for the DataFrame
    transcript_data = [
        {
            'text': t.content,
            'start': t.start,
            # CRITICAL: Use the YouTube ID from the related Video object
            'video_id': t.video.youtube_id
        }
        for t in transcripts
    ]
    
    df = pd.DataFrame(transcript_data)

    # Load the data into LangChain documents, the 'text' column becomes the content
    loader = DataFrameLoader(df, page_content_column='text')
    documents = loader.load()

    # Split the documents into smaller, more manageable chunks
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    docs = text_splitter.split_documents(documents)

    # Create the embedding function
    embedding_function = GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        google_api_key=settings.GEMINI_API_KEY
    )

    # Create the FAISS vector store from the documents
    print(f"Creating FAISS index from {len(docs)} document chunks...")
    vector_store = FAISS.from_documents(docs, embedding_function)

    # Save the new, correct FAISS index to disk
    vector_store.save_local(FAISS_INDEX_PATH)
    print(f"Successfully saved FAISS index to {FAISS_INDEX_PATH}")


def parse_timestamp_from_query(query):
    """Finds a timestamp in formats like HH:MM:SS or MM:SS and converts it to seconds."""
    match = re.search(r'(\d{1,2}):(\d{1,2}):(\d{1,2})|(\d{1,2}):(\d{1,2})', query)
    if not match:
        return None
    time_parts_str = [p for p in match.groups() if p is not None]
    time_parts = [int(p) for p in time_parts_str]
    seconds = 0
    if len(time_parts) == 3:
        seconds = time_parts[0] * 3600 + time_parts[1] * 60 + time_parts[2]
    elif len(time_parts) == 2:
        seconds = time_parts[0] * 60 + time_parts[1]
    return seconds if seconds > 0 else None

# --- AI Chains ---

def get_general_chain():
    """Chain for general knowledge questions."""
    prompt = PromptTemplate.from_template("You are a helpful AI assistant. Answer the following question to the best of your ability.\nQuestion: {question}")
    llm = ChatGoogleGenerativeAI(model=LLM_MODEL, google_api_key=settings.GEMINI_API_KEY)
    return prompt | llm | StrOutputParser()

def get_rag_chain():
    """Chain for answering based on retrieved context."""
    prompt = PromptTemplate.from_template(
        "You are an expert AI assistant. Your goal is to provide accurate answers based on the provided video transcript CONTEXT.\n"
        "Answer the user's QUESTION using ONLY the CONTEXT below. If the context is not sufficient, say so.\n"
        "CONTEXT:\n{context}\n\nQUESTION:\n{question}"
    )
    llm = ChatGoogleGenerativeAI(model=LLM_MODEL, google_api_key=settings.GEMINI_API_KEY)
    return prompt | llm | StrOutputParser()

def get_classifier_chain():
    """Classifies a query as 'Video-Specific' or 'General Knowledge'."""
    prompt = PromptTemplate.from_template(
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
    prompt = PromptTemplate.from_template(
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
    prompt = PromptTemplate.from_template(prompt_template)
    llm = ChatGoogleGenerativeAI(model=LLM_MODEL, google_api_key=settings.GEMINI_API_KEY)
    
    return prompt | llm | StrOutputParser()

# --- The Main Query Router ---

# Replace the existing query_router in core/rag_utils.py with this new version

def query_router(query, video_id=None, video_title=None, timestamp=0):
    """
    Routes the query to the correct chain using a robust, multi-step process.
    Includes special handling for summarization requests.
    """
    store = get_vector_store()
    if not store:
        print("FAISS index not found. Routing to general chain.")
        return get_general_chain().invoke({"question": query})

    # --- Priority 1: Handle Time-Sensitive Queries ---
    # (This logic remains the same)
    query_timestamp = parse_timestamp_from_query(query)
    effective_timestamp = query_timestamp if query_timestamp is not None else timestamp
    time_keywords = ['this moment', 'right now', 'at this time', 'what is he saying', 'what does this mean', 'what did he just say']
    is_time_sensitive = query_timestamp is not None or \
                        (any(keyword in query.lower() for keyword in time_keywords) and effective_timestamp > 1)

    if video_id and is_time_sensitive:
        print(f"Time-sensitive query detected for timestamp: {effective_timestamp}s")
        # This is a highly accurate method for specific moments, so we keep it.
        retriever = store.as_retriever(search_kwargs={'k': 300, 'filter': {'video_id': str(video_id)}})
        all_video_docs = retriever.get_relevant_documents("")
        target_doc = next((doc for doc in all_video_docs if doc.metadata.get('start', 0) <= effective_timestamp < doc.metadata.get('end', 0)), None)
        
        if target_doc:
            context = target_doc.page_content
            question_with_context = (
                f"The user is watching a video titled '{video_title}'. "
                f"At {int(effective_timestamp // 60)}m {int(effective_timestamp % 60)}s, the transcript says: '{context}'. "
                f"Based only on this, answer the user's question: '{query}'"
            )
            return get_general_chain().invoke({"question": question_with_context})
        else:
            return "I couldn't find the specific part of the transcript for that time."

    # --- NEW: Priority 2: Handle Summarization and Video-Wide Queries ---
    summarization_keywords = ['summarize', 'summary', 'overview', 'what is this video about', 'key points', 'give me a tldr']
    if video_id and any(keyword in query.lower() for keyword in summarization_keywords):
        print(f"Summarization query detected for video_id: {video_id}")
        
        # Force retrieval of the entire transcript for this video
        retriever = store.as_retriever(search_kwargs={'k': 300, 'filter': {'video_id': str(video_id)}})
        # Use an empty query to get all documents matching the filter
        all_video_docs = retriever.get_relevant_documents("")
        
        if not all_video_docs:
            print("Could not retrieve transcript for summarization.")
            return "I'm sorry, I couldn't retrieve the transcript to create a summary."

        # Combine all retrieved chunks into a single context
        full_transcript_context = "\n\n".join([doc.page_content for doc in all_video_docs])
        
        summarizer_chain = get_summarizer_chain()
        return summarizer_chain.invoke({
            "context": full_transcript_context,
            "question": query  # Pass the original query (e.g., "summarize the key points")
        })

    # --- Priority 3: Handle All Other Video-Specific Queries with the Decider ---
    if video_id:
        print("Standard video-specific query detected. Using Decider-based RAG.")
        classifier_chain = get_classifier_chain()
        category = classifier_chain.invoke({"question": query})
        print(f"Query classified as: {category}")

        if "Video-Specific" in category:
            print("Attempting to answer from video context...")
            retriever = store.as_retriever(search_kwargs={'k': 5, 'filter': {'video_id': str(video_id)}})
            docs = retriever.get_relevant_documents(query)
            context = "\n\n".join([doc.page_content for doc in docs])

            decider_chain = get_decider_chain()
            decision = decider_chain.invoke({"context": context, "question": query})
            print(f"Decider chose: {decision}")

            if "RAG" in decision and context:
                rag_chain = get_rag_chain()
                return rag_chain.invoke({"context": context, "question": query})

    # --- Priority 4: Default to General Knowledge ---
    print("Routing to general knowledge chain (default).")
    return get_general_chain().invoke({"question": query})
