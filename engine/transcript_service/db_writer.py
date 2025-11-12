import os
import csv
import pandas as pd
import logging
from django.conf import settings
from core.models import Transcript
from .utils import sanitize_filename

logger = logging.getLogger(__name__)

def save_and_populate_transcript(video, transcript_data, log_list):
    """
    Saves the given transcript data to a CSV and populates the
    Transcript model in the database.
    """
    if not transcript_data:
        log_list.append('  -> ERROR: No transcript data received. Cannot save or populate.')
        raise Exception("No transcript data was provided to save_and_populate.")

    platform_id = video.youtube_id or video.vimeo_id
    if not platform_id:
        log_list.append(f'  -> ERROR: Video {video.id} has no platform_id.')
        raise Exception(f'Video {video.id} has no youtube_id or vimeo_id.')

    # --- 1. Save to CSV File ---
    try:
        course_dir_safe = sanitize_filename(video.course.title)
        transcript_dir = os.path.join(settings.MEDIA_ROOT, 'transcripts', course_dir_safe)
        os.makedirs(transcript_dir, exist_ok=True)
        transcript_path = os.path.join(transcript_dir, f"{platform_id}.csv")
        
        df = pd.DataFrame(transcript_data)
        df = df[['start', 'content']] 
        df.to_csv(transcript_path, index=False, quoting=csv.QUOTE_ALL)
        log_list.append(f'  -> SUCCESS: Successfully saved transcript CSV: {transcript_path}')
    except Exception as e:
        log_list.append(f'  -> ERROR: Failed to save transcript CSV: {e}')
        logger.error(f"Failed to save CSV for video {platform_id}: {e}", exc_info=True)
        # We don't raise an exception here, as DB population is more critical.
        
    # --- 2. Populate Database ---
    try:
        log_list.append('  -> Populating database...')
        
        # Clear old entries for this video
        Transcript.objects.filter(video=video).delete()
        log_list.append('  -> Old database entries cleared.')

        # Prepare new entries
        transcripts_to_create = [
            Transcript(
                video=video,
                course=video.course,
                youtube_id=video.youtube_id,
                vimeo_id=video.vimeo_id,
                start=row['start'],
                content=row['content']
            ) for row in transcript_data
        ]
        
        # Bulk create new entries
        Transcript.objects.bulk_create(transcripts_to_create)
        log_list.append(f'  -> SUCCESS: Populated database with {len(transcripts_to_create)} lines.')
        
    except Exception as e:
        log_list.append(f'  -> ERROR: Failed to populate database: {e}')
        logger.error(f"Failed to populate Transcript DB for video {platform_id}: {e}", exc_info=True)
        raise Exception(f"Failed to populate database: {e}")