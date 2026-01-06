import logging
from .transcript_service.orchestrator import generate_transcript_for_video
from .transcript_service.ocr_service.video_ocr_service import VideoOCRService
from .rag.vector_store.indexer import (
    perform_course_index_generation, 
    create_index_for_single_video,
    create_ocr_index_for_single_video
)
from .rag.index_notes import update_video_notes_index
from core.models import Note, Video
from django.contrib.auth.models import User
from django.db.models import Q

logger = logging.getLogger(__name__)

def task_process_new_video(vimeo_id: str):
    """
    Orchestrates the pipeline for a newly uploaded video using its Vimeo ID.
    Pipeline: Audio Transcript -> OCR Transcript -> FAISS Index (Standard) -> FAISS Index (OCR)
    """
    logger.info(f"Django-Q: Starting NEW VIDEO pipeline for Vimeo ID {vimeo_id}")
    
    video = None
    try:
        # 1. Retrieve the video using the Vimeo ID
        video = Video.objects.get(vimeo_id=vimeo_id)
        
        # --- Step 1: Audio Transcript ---
        logger.info(f"Pipeline: 1. Generating AUDIO transcript for video {video.id}")
        status, log = generate_transcript_for_video(video.id)
        
        if status == "Error":
            raise Exception(f"Audio Transcript generation failed. Log: {log}")

        # --- Step 2: OCR Transcript (NEW) ---
        logger.info(f"Pipeline: 2. Generating OCR transcript for video {video.id}")
        
        ocr_service = VideoOCRService(sample_rate=2)
        ocr_success = ocr_service.process_video(video.id)
        
        if not ocr_success:
            logger.warning(f"Pipeline: OCR generation failed for video {video.id}. Proceeding to standard indexing...")
            if video.ocr_transcript_status != 'failed':
                video.ocr_transcript_status = 'failed'
                video.save(update_fields=['ocr_transcript_status'])
        else:
             logger.info(f"Pipeline: OCR generation SUCCESS for video {video.id}")

        # --- Step 3: Indexing (Standard) ---
        logger.info(f"Pipeline: 3a. Creating Standard FAISS index for video {video.id}")
        try:
            create_index_for_single_video(video)
        except Exception as e:
            logger.error(f"Pipeline: Standard indexing failed for video {video.id}: {e}")

        # --- Step 4: Indexing (OCR) (NEW) ---
        if ocr_success:
            logger.info(f"Pipeline: 3b. Creating OCR FAISS index for video {video.id}")
            try:
                create_ocr_index_for_single_video(video)
            except Exception as e:
                logger.error(f"Pipeline: OCR indexing failed for video {video.id}: {e}")

        logger.info(f"Django-Q: NEW VIDEO pipeline FINISHED for video {video.id}.")
        
    except Video.DoesNotExist:
        logger.error(f"CRITICAL: Could not find video with Vimeo ID {vimeo_id} in the database.")

    except Exception as e:
        logger.error(f"Django-Q: NEW VIDEO pipeline FAILED for Vimeo ID {vimeo_id}. Error: {e}", exc_info=True)
        if video:
            # Mark critical statuses as failed
            if video.transcript_status != 'complete':
                video.transcript_status = 'failed'
            if video.index_status != 'complete':
                video.index_status = 'failed'
            # Also mark OCR statuses if they were pending/processing
            if video.ocr_transcript_status in ['pending', 'processing']:
                video.ocr_transcript_status = 'failed'
            if video.ocr_index_status in ['indexing', 'pending']:
                video.ocr_index_status = 'failed'
                
            video.save(update_fields=[
                'transcript_status', 'index_status', 
                'ocr_transcript_status', 'ocr_index_status'
            ])

def task_generate_transcript(video_id: int):
    logger.info(f"Django-Q: Starting transcript task for video {video_id}")
    status, log = generate_transcript_for_video(video_id)
    if status == "Error":
        logger.error(f"Django-Q: Transcript task FAILED for video {video_id}. Log: {log}")
        _safe_update_status(video_id, 'transcript_status', 'failed')
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
        logger.info(f"Django-Q : Starting note index update for user {user_id}, video {video_id}")
        user  = User.objects.get(id=user_id)
        video = Video.objects.get(Q(youtube_id=video_id) | Q(vimeo_id=video_id))

        notes_to_process = Note.objects.filter(user=user, video=video)
        notes_to_process.update(index_status='processing')

        update_video_notes_index(video, user)

        notes_to_process.update(index_status='complete')

    except Video.DoesNotExist:
        logger.error(f"Django-Q: Failed note index task for platform_id {video_id} for user {user_id}")
    except User.DoesNotExist:
        logger.error(f"Django-Q: Failed note index. User not found with id {user_id} for video {video_id}")
    except Exception as e:
        logger.error(f"Django-Q: FAILED note index task for user {user_id}, video {video_id}: {e}", exc_info=True)
        try:
            if 'video' in locals() and 'user' in locals():
                Note.objects.filter(user=user, video=video, index_status='processing').update(index_status='failed')
        except Exception:
            pass

# --- NEW OCR SPECIFIC TASKS ---

def task_process_video_ocr(video_id: int):
    """Standalone task to run OCR on a specific video."""
    logger.info(f"Django-Q: Starting OCR task for video {video_id}")
    try:
        service = VideoOCRService(sample_rate=2)
        success = service.process_video(video_id)
        
        if success:
            logger.info(f"Django-Q: OCR task SUCCESS for video {video_id}. Triggering Indexing.")
            # Automatically trigger indexing if OCR succeeds
            task_generate_ocr_index(video_id)
        else:
            logger.error(f"Django-Q: OCR task FAILED for video {video_id}")
            _safe_update_status(video_id, 'ocr_transcript_status', 'failed')
    except Exception as e:
        logger.exception(f"Django-Q: OCR task exception for video {video_id}")
        _safe_update_status(video_id, 'ocr_transcript_status', 'failed')

def task_generate_ocr_index(video_id: int):
    """Generates OCR index for a SINGLE video."""
    logger.info(f"Django-Q: Starting OCR index task for video {video_id}")
    try:
        video = Video.objects.get(id=video_id)
        create_ocr_index_for_single_video(video)
        logger.info(f"Django-Q: OCR Index task SUCCESS for video {video_id}")
    except Exception as e:
        logger.error(f"Django-Q: OCR Index task FAILED for video {video_id}: {e}")
        _safe_update_status(video_id, 'ocr_index_status', 'failed')

def _safe_update_status(video_id, field, status):
    """Helper to update video status safely without crashing if video missing"""
    try:
        v = Video.objects.get(id=video_id)
        # Only update if not already complete to avoid overwriting race conditions
        if getattr(v, field) != 'complete':
            setattr(v, field, status)
            v.save(update_fields=[field])
    except Exception:
        pass