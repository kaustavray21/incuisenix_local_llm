import os
import logging
from django.conf import settings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain.schema import Document
from core.models import Transcript, OCRTranscript, Video, Course
from .config import get_embeddings

logger = logging.getLogger(__name__)


def perform_course_index_generation(course_id: int):
    """
    Generates both Standard and OCR FAISS indexes for all videos in a course.
    """
    logger.info(f"--- Starting FAISS index generation for course ID: {course_id} ---")
    try:
        course = Course.objects.get(id=course_id)
        videos = Video.objects.filter(course=course)
        
        if not videos.exists():
            logger.warning(f"No videos found for course '{course.title}'. Nothing to index.")
            return "No Videos", "No videos found."

        logger.info(f"Found {videos.count()} videos to index for course '{course.title}'.")
        
        success_count = 0
        fail_count = 0

        for video in videos:
            try:
                # 1. Create Standard Transcript Index
                create_index_for_single_video(video)
                
                # 2. Create OCR Index (Try, but don't fail the whole loop if just OCR fails)
                try:
                    create_ocr_index_for_single_video(video)
                except Exception as ocr_e:
                    logger.warning(f"OCR Index generation failed for video {video.id}: {ocr_e}")
                
                success_count += 1
            except Exception as e:
                # Logs failure for the main video index
                logger.error(f"Failed to index video {video.id} ('{video.title}'): {e}")
                fail_count += 1
        
        logger.info(f"--- Completed indexing for course {course_id}. Success: {success_count}, Failed: {fail_count} ---")
        return "Generated", f"Indexed {success_count} videos. Failed {fail_count}."

    except Exception as e:
        logger.error(f"FATAL: Course index generation crashed for course {course_id}: {e}", exc_info=True)
        return "Error", str(e)


def _process_and_save_index(docs, platform_id, video, subfolder_name, status_field):
    """
    Helper function to process documents, create embeddings, and save the FAISS index.
    
    Args:
        docs: List of Langchain Documents.
        platform_id: The folder name (video ID).
        video: The Video model instance.
        subfolder_name: 'transcripts' or 'ocr'.
        status_field: 'index_status' or 'ocr_index_status'.
    """
    try:
        if not docs:
            logger.warning(f"No documents to index for video {platform_id} ({subfolder_name}).")
            setattr(video, status_field, 'complete') # Empty is valid if source was empty but valid
            video.save(update_fields=[status_field])
            return

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
        split_docs = text_splitter.split_documents(docs)
        logger.info(f"Split into {len(split_docs)} chunks for embedding ({subfolder_name}).")

        if not split_docs:
            logger.warning(f"Text splitting resulted in zero chunks for video {platform_id}. Marking complete.")
            setattr(video, status_field, 'complete')
            video.save(update_fields=[status_field])
            return

        embedding_function = get_embeddings()

        logger.info(f"Creating FAISS index from {len(split_docs)} chunks for video {platform_id} ({subfolder_name})...")
        vector_store = FAISS.from_documents(split_docs, embedding_function)

        index_path = os.path.join(settings.FAISS_INDEX_ROOT, subfolder_name, platform_id)
        os.makedirs(index_path, exist_ok=True)

        vector_store.save_local(index_path)
        logger.info(f"Successfully saved FAISS index for video {platform_id} to {index_path}")

        setattr(video, status_field, 'complete')
        video.save(update_fields=[status_field])
        logger.info(f"Video {video.id} {status_field} updated to 'complete'.")

    except Exception as e:
        logger.error(f"Failed to create {subfolder_name} index for video {video.id}: {e}", exc_info=True)
        setattr(video, status_field, 'failed')
        video.save(update_fields=[status_field])
        raise e


def create_index_for_single_video(video: Video):
    """Creates the Standard FAISS index from Audio Transcripts."""
    logger.info(f"Creating Standard (Transcript) vector store for video: '{video.title}' (ID: {video.id})")
    
    video.index_status = 'indexing'
    video.save(update_fields=['index_status'])

    platform_id = video.youtube_id or video.vimeo_id
    if not platform_id:
        video.index_status = 'failed'
        video.save(update_fields=['index_status'])
        raise ValueError(f"Video {video.id} has no platform_id.")

    transcripts = Transcript.objects.filter(video=video).order_by('start')

    if not transcripts.exists():
        if video.transcript_status == 'complete':
            logger.warning(f"No transcripts found for video {platform_id} but status is complete.")
            video.index_status = 'complete'
            video.save(update_fields=['index_status'])
        else:
            logger.warning(f"No transcripts found for video {platform_id}. Status: {video.transcript_status}.")
            video.index_status = 'failed'
            video.save(update_fields=['index_status'])
        return

    docs = []
    for t in transcripts:
        docs.append(Document(
            page_content=t.content,
            metadata={
                'start_time': t.start,
                'video_title': video.title,
                'video_id': platform_id,
                'course_title': video.course.title,
                'course_id': video.course.id,
                'type': 'transcript'
            }
        ))
    
    _process_and_save_index(docs, platform_id, video, 'transcripts', 'index_status')


def create_ocr_index_for_single_video(video: Video):
    """Creates the OCR FAISS index from OCRTranscripts."""
    logger.info(f"Creating OCR vector store for video: '{video.title}' (ID: {video.id})")
    
    video.ocr_index_status = 'indexing'
    video.save(update_fields=['ocr_index_status'])

    platform_id = video.youtube_id or video.vimeo_id
    if not platform_id:
        video.ocr_index_status = 'failed'
        video.save(update_fields=['ocr_index_status'])
        raise ValueError(f"Video {video.id} has no platform_id.")

    ocr_transcripts = OCRTranscript.objects.filter(video=video).order_by('start')

    if not ocr_transcripts.exists():
        if video.ocr_transcript_status == 'complete':
            logger.warning(f"No OCR transcripts found for {platform_id} but status is complete.")
            video.ocr_index_status = 'complete'
            video.save(update_fields=['ocr_index_status'])
        else:
            logger.warning(f"No OCR transcripts found for {platform_id}. Status: {video.ocr_transcript_status}.")
            video.ocr_index_status = 'failed'
            video.save(update_fields=['ocr_index_status'])
        return

    docs = []
    for t in ocr_transcripts:
        docs.append(Document(
            page_content=t.content,
            metadata={
                'start_time': t.start,
                'video_title': video.title,
                'video_id': platform_id,
                'course_title': video.course.title,
                'course_id': video.course.id,
                'type': 'ocr'
            }
        ))
    
    _process_and_save_index(docs, platform_id, video, 'ocr', 'ocr_index_status')