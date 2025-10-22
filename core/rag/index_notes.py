import os
import shutil
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from django.conf import settings
from django.contrib.auth.models import User # <-- Import User
from core.models import Note, Video
from .vector_store import get_embeddings
import logging # <-- Import logging

logger = logging.getLogger(__name__)

# --- UPDATED FUNCTION SIGNATURE ---
def update_video_notes_index(video: Video, user: User):
    """
    Creates or updates a user-specific FAISS index for their notes
    on a specific video.
    """
    try:
        # --- UPDATED: Filter notes by *both* video and user ---
        notes = Note.objects.filter(video=video, user=user)

        # --- UPDATED: Create a user-specific path ---
        index_dir = os.path.join(
            settings.FAISS_INDEX_ROOT, 
            'notes', 
            str(user.id),  # <-- This is the crucial fix
            video.youtube_id
        )

        if not notes.exists():
            if os.path.exists(index_dir):
                logger.info(f"No notes found for user {user.id}, video {video.youtube_id}. Deleting old index.")
                shutil.rmtree(index_dir)
            return

        documents = []
        for note in notes:
            doc = Document(
                page_content=f"Title: {note.title}\nContent: {note.content}",
                metadata={
                    "user_id": note.user.id,
                    "note_id": note.id,
                    "course_id": note.course.id,
                    "video_id": video.id,
                    "timestamp": note.video_timestamp
                }
            )
            documents.append(doc)

        if not documents:
            if os.path.exists(index_dir):
                shutil.rmtree(index_dir)
            return
            
        os.makedirs(index_dir, exist_ok=True)
        embeddings = get_embeddings()
        vector_store = FAISS.from_documents(documents, embeddings)
        vector_store.save_local(index_dir)
        logger.info(f"Successfully updated notes index for user {user.id}, video {video.youtube_id} at {index_dir}")

    except Exception as e:
        logger.error(f"Error updating notes index for user {user.id}, video {video.id}: {e}", exc_info=True)