import os
import pandas as pd
from django.conf import settings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import DataFrameLoader
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain.retrievers import EnsembleRetriever
from core.models import Transcript

EMBEDDING_MODEL = "models/text-embedding-004"

def get_embeddings():
    return GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        google_api_key=settings.GEMINI_API_KEY
    )

def get_transcript_vector_store(video_id: str):
    index_path = os.path.join(settings.FAISS_INDEX_ROOT, video_id)
    if not os.path.exists(index_path):
        return None

    try:
        return FAISS.load_local(
            index_path,
            get_embeddings(),
            allow_dangerous_deserialization=True
        )
    except Exception as e:
        print(f"Error loading transcript index for video {video_id}: {e}")
        return None

def get_note_vector_store(video_id: str):
    index_path = os.path.join(settings.FAISS_INDEX_ROOT, 'notes', video_id)
    if not os.path.exists(index_path):
        return None
    
    try:
        return FAISS.load_local(
            index_path,
            get_embeddings(),
            allow_dangerous_deserialization=True
        )
    except Exception as e:
        print(f"Error loading notes index for video {video_id}: {e}")
        return None

def get_retriever(video_id: str, user_id: int):
    transcript_store = get_transcript_vector_store(video_id)
    note_store = get_note_vector_store(video_id)

    retrievers = []
    
    if transcript_store:
        transcript_retriever = transcript_store.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 3}
        )
        retrievers.append(transcript_retriever)
        print(f"Loaded transcript retriever for video {video_id}")

    if note_store:
        note_retriever = note_store.as_retriever(
            search_type="similarity",
            search_kwargs={
                "k": 2,
                "filter": {"user_id": user_id}
            }
        )
        retrievers.append(note_retriever)
        print(f"Loaded note retriever for video {video_id} for user {user_id}")

    if not retrievers:
        raise Exception(f"Could not load any retrievers for video {video_id}.")
    
    if len(retrievers) == 1:
        return retrievers[0]

    return EnsembleRetriever(
        retrievers=retrievers,
        weights=[0.6, 0.4]
    )

def create_vector_store_for_video(video_id: str):
    print(f"Creating vector store for video_id: {video_id}")
    transcripts = Transcript.objects.filter(video__youtube_id=video_id).select_related('video').order_by('start')
    
    if not transcripts.exists():
        print(f"No transcripts found for video_id: {video_id}")
        return

    transcript_data = [
        {'text': t.content, 'start': t.start, 'video_id': t.video.youtube_id}
        for t in transcripts
    ]
    df = pd.DataFrame(transcript_data)
    
    loader = DataFrameLoader(df, page_content_column='text')
    documents = loader.load()

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    docs = text_splitter.split_documents(documents)

    embedding_function = get_embeddings()

    print(f"Creating FAISS index from {len(docs)} document chunks for video {video_id}...")
    vector_store = FAISS.from_documents(docs, embedding_function)

    index_path = os.path.join(settings.FAISS_INDEX_ROOT, video_id)
    os.makedirs(index_path, exist_ok=True)

    vector_store.save_local(index_path)
    print(f"Successfully saved FAISS index for video {video_id} to {index_path}")