import os
import pandas as pd
import logging
from django.conf import settings
from django.db.models import Q
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import DataFrameLoader
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain.retrievers import EnsembleRetriever
from langchain.schema import Document
from core.models import Transcript, Video

logger = logging.getLogger(__name__)

# Using the correct model that you have a quota for
EMBEDDING_MODEL = "models/text-embedding-004" 

def get_embeddings():
    return GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        google_api_key=settings.GEMINI_API_KEY
    )

def create_vector_store_for_video(video_id: str):
    logger.info(f"Attempting to create vector store for video_id: {video_id}")
    try:
        # We can find the video by any ID
        video = Video.objects.filter(Q(youtube_id=video_id) | Q(vimeo_id=video_id)).select_related('course').first()

        if not video:
            logger.error(f"Video with YouTube/Vimeo ID '{video_id}' not found in database.")
            raise Video.DoesNotExist(f"Video with ID '{video_id}' not found.")

        platform_id = video.youtube_id or video.vimeo_id
        logger.info(f"Found video: '{video.title}' (ID: {platform_id})")

        transcripts = Transcript.objects.filter(video=video).order_by('start')

        if not transcripts.exists():
            logger.warning(f"No transcripts found for video_id: {platform_id}. Skipping index creation.")
            return
            
        # Convert transcripts to Langchain Documents
        docs = []
        for t in transcripts:
            docs.append(Document(
                page_content=t.content,
                metadata={
                    'start_time': t.start,
                    'video_title': video.title,
                    'video_id': platform_id,
                    'course_title': video.course.title,
                    'course_id': video.course.id
                }
            ))
        logger.info(f"Loaded {len(docs)} transcript segments as Langchain Documents.")

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
        split_docs = text_splitter.split_documents(docs)
        logger.info(f"Split into {len(split_docs)} chunks for embedding.")

        if not split_docs:
            logger.warning(f"Text splitting resulted in zero documents for video {platform_id}. Skipping.")
            return

        embedding_function = get_embeddings()

        logger.info(f"Creating FAISS index from {len(split_docs)} document chunks for video {platform_id}...")
        vector_store = FAISS.from_documents(split_docs, embedding_function)

        # --- This is the Corrected Path Logic ---
        # Assumes FAISS_INDEX_ROOT is defined in settings.py
        # e.g., FAISS_INDEX_ROOT = os.path.join(settings.MEDIA_ROOT, 'faiss_indexes')
        index_path = os.path.join(settings.FAISS_INDEX_ROOT, 'transcripts', platform_id)
        os.makedirs(index_path, exist_ok=True)

        vector_store.save_local(index_path)
        logger.info(f"Successfully saved FAISS index for video {platform_id} to {index_path}")

    except Video.DoesNotExist as e:
        logger.error(e)
        raise e
    except Exception as e:
        logger.exception(f"Unexpected error creating vector store for video_id {video_id}: {e}")
        raise e

def get_transcript_vector_store(video_id: str):
    logger.debug(f"Attempting to load transcript vector store for video_id: {video_id}")
    
    # --- This is the Corrected Path Logic ---
    index_path = os.path.join(settings.FAISS_INDEX_ROOT, 'transcripts', video_id)
    
    if not os.path.exists(index_path):
        logger.warning(f"No transcript index directory found for video {video_id} at {index_path}")
        return None

    faiss_file = os.path.join(index_path, "index.faiss")
    if not os.path.exists(faiss_file):
        logger.warning(f"FAISS file 'index.faiss' not found within directory {index_path}")
        return None

    try:
        logger.debug(f"Loading transcript FAISS index from: {index_path}")
        return FAISS.load_local(
            index_path,
            get_embeddings(),
            allow_dangerous_deserialization=True
        )
    except Exception as e:
        logger.exception(f"Error loading transcript index for video {video_id}: {e}")
        return None

def get_note_vector_store(video_id: str, user_id: int):
    logger.debug(f"Attempting to load notes vector store for video_id: {video_id}, user_id: {user_id}")

    index_path = os.path.join(
        settings.FAISS_INDEX_ROOT,
        'notes',
        str(user_id),
        video_id
    )
    if not os.path.exists(index_path):
        logger.warning(f"No note index directory found for video {video_id}, user {user_id} at {index_path}")
        return None

    faiss_file = os.path.join(index_path, "index.faiss")
    if not os.path.exists(faiss_file):
        logger.warning(f"FAISS file 'index.faiss' not found within notes directory {index_path}")
        return None

    try:
        logger.debug(f"Loading notes FAISS index from: {index_path}")
        return FAISS.load_local(
            index_path,
            get_embeddings(),
            allow_dangerous_deserialization=True
        )
    except Exception as e:
        logger.exception(f"Error loading notes index for video {video_id}, user {user_id}: {e}")
        return None

def get_retriever(video_id: str, user_id: int):
    logger.debug(f"Getting retriever for video_id: {video_id}, user_id: {user_id}")

    transcript_store = get_transcript_vector_store(video_id)
    note_store = get_note_vector_store(video_id, user_id)

    retrievers = []

    if transcript_store:
        transcript_retriever = transcript_store.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 3}
        )
        retrievers.append(transcript_retriever)
        logger.info(f"Loaded transcript retriever for video {video_id}")

    if note_store:
        note_retriever = note_store.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 5} # Using 5 as a default, adjust as needed
        )
        retrievers.append(note_retriever)
        logger.info(f"Loaded note retriever for video {video_id} for user {user_id}")

    if not retrievers:
        logger.warning(f"Could not load any retrievers for video {video_id}. RAG will have no context.")
        return FAISS.from_texts(["No context available for this video."], get_embeddings()).as_retriever(search_kwargs={"k": 1})


    if len(retrievers) == 1:
        logger.info(f"Using single retriever for video {video_id}")
        return retrievers[0]

    logger.info(f"Using EnsembleRetriever (transcripts+notes) for video {video_id}")
    return EnsembleRetriever(
        retrievers=retrievers,
        weights=[0.6, 0.4]
    )