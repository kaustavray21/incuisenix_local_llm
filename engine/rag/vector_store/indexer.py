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
    course = None
    try:
        course = Course.objects.get(id=course_id)
        videos = Video.objects.filter(course=course)
        
        if not videos.exists():
            logger.warning(f"No videos found for course '{course.title}'. Marking as complete.")
            course.index_status = 'complete'
            course.save()
            return

        logger.info(f"Found {videos.count()} videos to index for course '{course.title}'.")
        
        success_count = 0
        fail_count = 0

        for video in videos:
            try:
                create_index_for_single_video(video)
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to create index for video {video.id} ('{video.title}'): {e}", exc_info=True)
                fail_count += 1
        
        if fail_count > 0:
            raise Exception(f"Failed to index {fail_count} out of {videos.count()} videos.")

        course.index_status = 'complete'
        course.save()
        logger.info(f"--- Successfully completed indexing for course {course_id}. {success_count} videos indexed. ---")
        return "Generated", f"Indexed {success_count} videos."

    except Exception as e:
        logger.error(f"FATAL: Index generation failed for course {course_id}: {e}", exc_info=True)
        if course:
            course.index_status = 'failed'
            course.save()
            logger.info(f"--- Set course {course_id} status to 'failed'. ---")
            
        return "Error", str(e)


def create_index_for_single_video(video: Video):
    logger.info(f"Creating vector store for video: '{video.title}'")

    platform_id = video.youtube_id or video.vimeo_id
    if not platform_id:
        raise ValueError(f"Video {video.id} (DB) has no platform_id.")

    transcripts = Transcript.objects.filter(video=video).order_by('start')

    if not transcripts.exists():
        logger.warning(f"No transcripts found for video: {platform_id}. Skipping index creation.")
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
        return

    embedding_function = get_embeddings()

    logger.info(f"Creating FAISS index from {len(split_docs)} document chunks for video {platform_id}...")
    vector_store = FAISS.from_documents(split_docs, embedding_function)

    index_path = os.path.join(settings.FAISS_INDEX_ROOT, 'transcripts', platform_id)
    os.makedirs(index_path, exist_ok=True)

    vector_store.save_local(index_path)
    logger.info(f"Successfully saved FAISS index for video {platform_id} to {index_path}")