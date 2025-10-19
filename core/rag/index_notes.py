import os
import shutil
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from django.conf import settings
from core.models import Note, Video
from .vector_store import get_embeddings

def update_video_notes_index(video_id: int):
    try:
        video = Video.objects.get(id=video_id)
        notes = Note.objects.filter(video=video)

        index_dir = os.path.join(settings.FAISS_INDEX_ROOT, 'notes', video.youtube_id)

        if not notes.exists():
            if os.path.exists(index_dir):
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
                    "timestamp": note.video_timestamp  # <-- THIS IS THE FIX
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

    except Video.DoesNotExist:
        pass
    except Exception as e:
        print(f"Error updating notes index for video {video_id}: {e}")