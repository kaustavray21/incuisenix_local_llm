import logging
from langchain_community.vectorstores import FAISS
from langchain.retrievers import EnsembleRetriever
from .config import get_embeddings
from .loader import get_transcript_vector_store, get_note_vector_store

logger = logging.getLogger(__name__)


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
        # Create a dummy retriever to prevent crashes
        return FAISS.from_texts(
            ["No context available for this video."], 
            get_embeddings()
        ).as_retriever(search_kwargs={"k": 1})

    if len(retrievers) == 1:
        logger.info(f"Using single retriever for video {video_id}")
        return retrievers[0]

    logger.info(f"Using EnsembleRetriever (transcripts+notes) for video {video_id}")
    return EnsembleRetriever(
        retrievers=retrievers,
        weights=[0.6, 0.4]
    )