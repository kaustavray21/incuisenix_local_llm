import os
import logging
from django.conf import settings
from langchain_community.vectorstores import FAISS
from .config import get_embeddings

logger = logging.getLogger(__name__)


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