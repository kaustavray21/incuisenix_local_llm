import logging
from .transcript_service.orchestrator import generate_transcript_for_video
from .rag.vector_store import perform_course_index_generation, create_index_for_single_video
from .rag.index_notes import update_video_notes_index
from core.models import Note, Video
from django.contrib.auth.models import User
from django.db.models import Q 

logger = logging.getLogger(__name__)

def task_process_new_video(video_id: int):
    logger.info(f"Django-Q: Starting NEW VIDEO pipeline for video {video_id}")
    
    try:
        video = Video.objects.get(id=video_id)
        
        logger.info(f"Pipeline: 1. Generating transcript for video {video_id}")
        status, log = generate_transcript_for_video(video_id)
        
        if status == "Error":
            raise Exception(f"Transcript generation failed. Log: {log}")
            
        logger.info(f"Pipeline: 2. Creating FAISS index for video {video_id}")
        create_index_for_single_video(video)
        
        logger.info(f"Django-Q: NEW VIDEO pipeline SUCCESS for video {video_id}.")
        
    except Exception as e:
        logger.error(f"Django-Q: NEW VIDEO pipeline FAILED for video {video_id}. Error: {e}", exc_info=True)
        if 'video' in locals() and video:
            video.transcript_status = 'failed'
            video.save(update_fields=['transcript_status'])

def task_generate_transcript(video_id: int):
    logger.info(f"Django-Q: Starting transcript task for video {video_id}")
    status, log = generate_transcript_for_video(video_id)
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
    try:
        logger.info(f"Djang-Q : Starting note index update for user {user_id}, video {video_id}")
        user  = User.objects.get(id=user_id)
        video = Video.objects.get( Q(youtube_id = video_id) | Q(vimeo_id = video_id))

        notes_to_process = Note.objects.filter(user = user, video = video)
        notes_to_process.update(index_status = 'processing')

        update_video_notes_index(video, user)

        notes_to_process.update(index_status = 'complete')

    except Video.DoesNotExist:
        logger.error(f"Django-Q: Failed note index task for platform_id {video_id} for user {user_id}")
    except User.DoesNotExist:
        logger.error(f"Django-Q: Failed note index. User not found with id {user_id} for video {video_id}")
    except Exception as e:
        logger.error(f"Django-Q: FAILED note index task for user {user_id}, video {video_id}: {e}", exc_info=True)

        try:
            if 'video' in locals() and 'user' in locals():
                Note.objects.filter(user = user, video = video, index_status = 'processing').update(index_status = 'failed')
        except Exception as e_update:
            logger.error(f"Django-Q: Could not even set status to 'failed' for user {user_id}, video {video_id}: {e_update}")