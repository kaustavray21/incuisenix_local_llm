import logging
from .transcript_service import _perform_transcript_generation
from .rag.vector_store import perform_course_index_generation

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