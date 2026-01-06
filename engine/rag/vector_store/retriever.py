import logging
from langchain_community.vectorstores import FAISS
from langchain.retrievers import EnsembleRetriever
from .config import get_embeddings
# Added get_ocr_vector_store to the imports
from .loader import get_transcript_vector_store, get_note_vector_store, get_ocr_vector_store

logger = logging.getLogger(__name__)


def get_retriever(video_id: str, user_id: int | None):
    logger.debug(f"Getting retriever for video_id: {video_id}, user_id: {user_id}")

    retrievers = []
    weights = []

    # 1. Transcript Retriever (Audio) - Weight: 0.5
    transcript_store = get_transcript_vector_store(video_id)
    if transcript_store:
        transcript_retriever = transcript_store.as_retriever(search_type="similarity", search_kwargs={"k": 3})
        retrievers.append(transcript_retriever)
        weights.append(0.5)
        logger.info(f"Loaded transcript retriever for video {video_id}")
    
    # 2. OCR Retriever (Visual) - Weight: 0.2
    # This captures code on screen or slides that wasn't spoken aloud
    ocr_store = get_ocr_vector_store(video_id)
    if ocr_store:
        ocr_retriever = ocr_store.as_retriever(search_type="similarity", search_kwargs={"k": 3})
        retrievers.append(ocr_retriever)
        weights.append(0.2)
        logger.info(f"Loaded OCR retriever for video {video_id}")

    # 3. Note Retriever (User Personal) - Weight: 0.3
    if user_id is not None:
        note_store = get_note_vector_store(video_id, user_id)
        if note_store:
            note_retriever = note_store.as_retriever(
                search_type="similarity",
                search_kwargs={"k": 5}
            )
            retrievers.append(note_retriever)
            weights.append(0.3)
            logger.info(f"Loaded note retriever for video {video_id} for user {user_id}")

    # --- Fallback & Return Logic ---

    if not retrievers:
        logger.warning(f"Could not load any retrievers for video {video_id}. RAG will have no context.")
        # Create a dummy retriever to prevent crashes
        return FAISS.from_texts(["No context available for this video."], get_embeddings()).as_retriever(search_kwargs={"k": 1})

    if len(retrievers) == 1:
        logger.info(f"Using single retriever for video {video_id}")
        return retrievers[0]

    logger.info(f"Using EnsembleRetriever with {len(retrievers)} sources (Weights: {weights}) for video {video_id}")
    # Hybrid Search: Combines results using Reciprocal Rank Fusion (RRF) based on the weights provided
    return EnsembleRetriever(retrievers=retrievers, weights=weights)