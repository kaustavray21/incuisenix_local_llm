import logging
from .transcript_service import _perform_transcript_generation
from .rag.vector_store import perform_course_index_generation
from .rag.index_notes import update_video_notes_index
from core.models import Note, Video
from django.contrib.auth.models import User
from django.db.models import Q 

logger = logging.getLogger(__name__)

def task_generate_transcript(video_id: int):
    logger.info(f"Django-Q: Starting transcript task for video {video_id}")
    status, log = _perform_transcript_generation(video_id)
    if status == "Error":
        logger.error(f"Django-Q: Transcript task FAILED for video {video_id}. Log: {log}")
    else:
        logger.info(f"Django-Q: Transcript task SUCCESS for video {video_id}.")

def task_generate_index(course_id: int):
    logger.info(f"Django-Q: Starting index task for course {course_id}")
    status, log = perform_course_index_generation(course_id)
    if status == "Error":
        logger.error(f"Django-Q: Index task FAILED for course {course_id}. Log: {log}")
    else:
        logger.info(f"Django-Q: Index task SUCCESS for course {course_id}.")

def task_update_note_index(user_id: int, video_id: str):
    """
    Asynchronous task to rebuild the note index for a specific user and video.
    This task is triggered by signals when a new video is saved or deleted

    Args:
        user_id: The ID of the User whose notes are being indexed.
        video_id: The platform_id (youtube_id or vimeo_id) of the Video.
    """
    try:
        logger.info(f"Djang-Q : Starting note index update for user {user_id}, video {video_id}")
        user  = User.objects.get(id=user_id)
        video = Video.objects.get( Q(youtube_id = video_id) | Q(vimeo_id = video_id))

        notes_to_process = Note.objects.filter(user = user, video = video)
        notes_to_process.update(index_status = 'processing')

        update_video_notes_index(video, user)

        notes_to_process.update(index_status = 'complete')

        logger.info(f"Django-Q: Starting note index update for user {user_id}, video {video_id}")

    except Video.DoesNotExist:
        logger.error(f"Django-Q: Failed note index task for platform_id {video_id} for user {user_id}")
    except User.DoesNotExist:
        logger.error(f"Django-Q: Failed note index. User not found with id {user_id} for video {video_id}")
    except Exception as e:
        logger.error(f"Django-Q: FAILED note index task for user {user_id}, video {video_id}: {e}", exc_info=True)

        try:
            if 'video' in locals() and 'user' in locals():
                Note.objects,filter(user = user, video = video, index_status = 'processing').update(index_status = 'failed')
        except Exception as e_update:
            logger.error(f"Django-Q: Could not even set status to 'failed' for user {user_id}, video {video_id}: {e_update}")