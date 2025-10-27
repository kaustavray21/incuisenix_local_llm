import os
import shutil
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from django.conf import settings
from django.contrib.auth.models import User
from core.models import Note, Video
from .vector_store import get_embeddings # Assuming get_embeddings is in this relative path
import logging

logger = logging.getLogger(__name__)

def update_video_notes_index(video: Video, user: User):
    """
    Creates or updates a user-specific FAISS index for their notes
    on a specific video.
    """
    try:
        notes = Note.objects.filter(video=video, user=user)

        # --- THIS IS THE FIX ---
        # Get the actual platform ID (YouTube or Vimeo)
        platform_id = video.youtube_id or video.vimeo_id
        if not platform_id:
             logger.error(f"Video {video.pk} has no youtube_id or vimeo_id. Cannot create notes index.")
             return # Cannot proceed without a platform ID

        # Construct the user-specific path using the platform_id
        index_dir = os.path.join(
            settings.FAISS_INDEX_ROOT,
            'notes',
            str(user.id),
            platform_id # <-- Use the correct platform ID here
        )
        # --- END OF FIX ---

        if not notes.exists():
            if os.path.exists(index_dir):
                logger.info(f"No notes found for user {user.id}, video {platform_id}. Deleting old index at {index_dir}.")
                shutil.rmtree(index_dir)
            else:
                 logger.info(f"No notes found for user {user.id}, video {platform_id}. No index to delete.")
            return # Exit function if no notes

        documents = []
        for note in notes:
            doc = Document(
                page_content=f"Title: {note.title}\nContent: {note.content}",
                metadata={
                    "user_id": note.user.id,
                    "note_id": note.id,
                    "course_id": note.course.id,
                    "video_db_id": video.id, # Keep DB ID for potential internal linking
                    "video_platform_id": platform_id, # Add platform ID for consistency
                    "timestamp": note.video_timestamp
                }
            )
            documents.append(doc)

        # Double check in case notes existed but resulted in no documents somehow
        if not documents:
            if os.path.exists(index_dir):
                 logger.warning(f"Note query returned results but no documents generated for user {user.id}, video {platform_id}. Deleting index.")
                 shutil.rmtree(index_dir)
            return

        os.makedirs(index_dir, exist_ok=True)
        embeddings = get_embeddings()
        vector_store = FAISS.from_documents(documents, embeddings)
        vector_store.save_local(index_dir)
        logger.info(f"Successfully updated notes index for user {user.id}, video {platform_id} at {index_dir}")

    except Exception as e:
        # Try to get platform_id for better logging, fallback to video.id
        p_id = getattr(video, 'youtube_id', None) or getattr(video, 'vimeo_id', video.id)
        logger.error(f"Error updating notes index for user {user.id}, video {p_id}: {e}", exc_info=True)