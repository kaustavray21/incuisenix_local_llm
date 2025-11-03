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
from core.models import Transcript, Video, Course

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "models/text-embedding-004" 

def get_embeddings():
    return GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        google_api_key=settings.GEMINI_API_KEY
    )

def perform_course_index_generation(course_id: int):
    logger.info(f"--- Starting FAISS index generation for course ID: {course_id} ---")
    course = None
    try:
        course = Course.objects.get(id=course_id)
        videos = Video.objects.filter(course=course)
        
        if not videos.exists():
            logger.warning(f"No videos found for course '{course.title}'. Marking as complete.")
            course.index_status = 'complete'
            course.save()
            return

        logger.info(f"Found {videos.count()} videos to index for course '{course.title}'.")
        
        success_count = 0
        fail_count = 0

        for video in videos:
            try:
                _create_index_for_single_video(video)
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to create index for video {video.id} ('{video.title}'): {e}", exc_info=True)
                fail_count += 1
        
        if fail_count > 0:
            raise Exception(f"Failed to index {fail_count} out of {videos.count()} videos.")

        course.index_status = 'complete'
        course.save()
        logger.info(f"--- Successfully completed indexing for course {course_id}. {success_count} videos indexed. ---")
        return "Generated", f"Indexed {success_count} videos."

    except Exception as e:
        logger.error(f"FATAL: Index generation failed for course {course_id}: {e}", exc_info=True)
        if course:
            course.index_status = 'failed'
            course.save()
            logger.info(f"--- Set course {course_id} status to 'failed'. ---")
            
        return "Error", str(e)


def _create_index_for_single_video(video: Video):
    logger.info(f"Creating vector store for video: '{video.title}'")

    platform_id = video.youtube_id or video.vimeo_id
    if not platform_id:
        raise ValueError(f"Video {video.id} (DB) has no platform_id.")

    transcripts = Transcript.objects.filter(video=video).order_by('start')

    if not transcripts.exists():
        logger.warning(f"No transcripts found for video: {platform_id}. Skipping index creation.")
        return
        
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

    index_path = os.path.join(settings.FAISS_INDEX_ROOT, 'transcripts', platform_id)
    os.makedirs(index_path, exist_ok=True)

    vector_store.save_local(index_path)
    logger.info(f"Successfully saved FAISS index for video {platform_id} to {index_path}")


def get_transcript_vector_store(video_id: str):
    logger.debug(f"Attempting to load transcript vector store for video_id: {video_id}")
    
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
            search_kwargs={"k": 5}
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