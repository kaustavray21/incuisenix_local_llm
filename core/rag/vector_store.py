import os
import pandas as pd
from django.conf import settings
from langchain_community.document_loaders import DataFrameLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from core.models import Transcript

# --- Constants ---
FAISS_INDEX_PATH = os.path.join(settings.BASE_DIR, 'faiss_indexes')
EMBEDDING_MODEL = "models/text-embedding-004"

def get_vector_store(video_id: str):
    """
    Loads the FAISS index for a specific video from disk.
    If the index doesn't exist, it returns None.
    """
    index_path = os.path.join(FAISS_INDEX_PATH, str(video_id))
    if not os.path.exists(index_path):
        return None

    embedding_function = GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        google_api_key=settings.GEMINI_API_KEY
    )
    
    print(f"Loading FAISS index for video {video_id} from {index_path}...")
    return FAISS.load_local(
        index_path,
        embedding_function,
        allow_dangerous_deserialization=True  # Required for loading FAISS indexes
    )

def create_vector_store_for_video(video_id: str):
    """
    Creates and saves a FAISS vector store for a single video's transcript.
    This function should be run offline, for example, via a Django management command.
    """
    print(f"Creating vector store for video_id: {video_id}")
    transcripts = Transcript.objects.filter(video__youtube_id=video_id).select_related('video').order_by('start')
    
    if not transcripts.exists():
        print(f"No transcripts found for video_id: {video_id}")
        return

    # Prepare transcript data for DataFrame
    transcript_data = [
        {'text': t.content, 'start': t.start, 'video_id': t.video.youtube_id}
        for t in transcripts
    ]

    df = pd.DataFrame(transcript_data)
    
    # Load documents from DataFrame
    loader = DataFrameLoader(df, page_content_column='text')
    documents = loader.load()

    # Split documents into smaller chunks for better retrieval accuracy
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    docs = text_splitter.split_documents(documents)

    # Initialize the embedding function
    embedding_function = GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        google_api_key=settings.GEMINI_API_KEY
    )

    print(f"Creating FAISS index from {len(docs)} document chunks for video {video_id}...")
    vector_store = FAISS.from_documents(docs, embedding_function)

    # Save the index to disk for later use
    index_path = os.path.join(FAISS_INDEX_PATH, str(video_id))
    if not os.path.exists(index_path):
        os.makedirs(index_path)

    vector_store.save_local(index_path)
    print(f"Successfully saved FAISS index for video {video_id} to {index_path}")

def get_retriever(video_id: str):
    """
    Gets the retriever for a given video, creating the vector store if it doesn't exist.
    """
    vector_store = get_vector_store(video_id)
    if vector_store is None:
        # This is a fallback, ideally indexes should be pre-created
        create_vector_store_for_video(video_id)
        vector_store = get_vector_store(video_id)
        
    if vector_store is None:
        raise Exception(f"Could not create or load a vector store for video ID {video_id}.")
        
    return vector_store.as_retriever()