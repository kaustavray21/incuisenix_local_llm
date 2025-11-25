import os
import logging
from django.conf import settings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain.schema import Document
from core.models import Transcript, Video, Course
from .config import get_embeddings

logger = logging.getLogger(__name__)


def perform_course_index_generation(course_id: int):
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
                # We delegate the work AND the status updates to the single video function
                create_index_for_single_video(video)
                success_count += 1
            except Exception as e:
                # create_index_for_single_video handles setting status='failed',
                # we just log here and continue the loop
                logger.error(f"Failed to index video {video.id} ('{video.title}'): {e}")
                fail_count += 1
        
        logger.info(f"--- Completed indexing for course {course_id}. Success: {success_count}, Failed: {fail_count} ---")
        return "Generated", f"Indexed {success_count} videos. Failed {fail_count}."

    except Exception as e:
        logger.error(f"FATAL: Course index generation crashed for course {course_id}: {e}", exc_info=True)
        return "Error", str(e)


def create_index_for_single_video(video: Video):
    logger.info(f"Creating vector store for video: '{video.title}' (ID: {video.id})")

    try:
        # 1. Set status to indexing (cover re-indexing cases)
        video.index_status = 'indexing'
        video.save(update_fields=['index_status'])

        platform_id = video.youtube_id or video.vimeo_id
        if not platform_id:
            raise ValueError(f"Video {video.id} (DB) has no platform_id.")

        transcripts = Transcript.objects.filter(video=video).order_by('start')

        if not transcripts.exists():
            if video.transcript_status == 'complete':
                logger.warning(f"No transcripts found for video: {platform_id} but transcript status is complete. Marking index complete (empty transcript).")
                video.index_status = 'complete'
                video.save(update_fields=['index_status'])
            else:
                logger.warning(f"No transcripts found for video: {platform_id} and transcript status is '{video.transcript_status}'. Marking index as failed.")
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
                    'course_id': video.course.id
                }
            ))
        logger.info(f"Loaded {len(docs)} transcript segments as Langchain Documents.")

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
        split_docs = text_splitter.split_documents(docs)
        logger.info(f"Split into {len(split_docs)} chunks for embedding.")

        if not split_docs:
            logger.warning(f"Text splitting resulted in zero documents for video {platform_id}. Skipping.")
            video.index_status = 'complete'
            video.save(update_fields=['index_status'])
            return

        embedding_function = get_embeddings()

        logger.info(f"Creating FAISS index from {len(split_docs)} document chunks for video {platform_id}...")
        vector_store = FAISS.from_documents(split_docs, embedding_function)

        index_path = os.path.join(settings.FAISS_INDEX_ROOT, 'transcripts', platform_id)
        os.makedirs(index_path, exist_ok=True)

        vector_store.save_local(index_path)
        logger.info(f"Successfully saved FAISS index for video {platform_id} to {index_path}")

        # 2. Success! Update status on the VIDEO object
        video.index_status = 'complete'
        video.save(update_fields=['index_status'])
        logger.info(f"Video {video.id} status updated to 'complete'.")

    except Exception as e:
        logger.error(f"Failed to create index for video {video.id}: {e}", exc_info=True)
        
        # 3. Failure! Update status on the VIDEO object
        video.index_status = 'failed'
        video.save(update_fields=['index_status'])
        raise e  # Re-raise so the caller knows it failed