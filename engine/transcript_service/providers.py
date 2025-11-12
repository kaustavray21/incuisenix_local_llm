import os
import vimeo
import logging
from youtube_transcript_api import YouTubeTranscriptApi

logger = logging.getLogger(__name__)

def initialize_vimeo_client():
    """
    Initializes and returns a Vimeo client if credentials are set.
    """
    VIMEO_TOKEN = os.getenv('VIMEO_TOKEN')
    VIMEO_KEY = os.getenv('VIMEO_KEY')
    VIMEO_SECRET = os.getenv('VIMEO_SECRET')
    if VIMEO_TOKEN and VIMEO_KEY and VIMEO_SECRET:
        try:
            client = vimeo.VimeoClient(token=VIMEO_TOKEN, key=VIMEO_KEY, secret=VIMEO_SECRET)
            logger.info("Vimeo client initialized.")
            return client
        except Exception as e:
            logger.error(f"Failed to initialize Vimeo client: {e}")
    else:
        logger.warning("VIMEO .env credentials missing. Skipping Vimeo API checks.")
    return None

def get_api_transcript(video, log_list):
    """
    Tries to fetch a pre-existing transcript from an API.

    Returns a tuple: (transcript_data, use_whisper)
    - (data, False) if successful (e.g., YouTube)
    - (None, True) if an API is unavailable, fails, or it's a platform
      that requires Whisper (e.g., Vimeo).
    """
    if video.youtube_id:
        log_list.append('  -> Trying YouTube Transcript API...')
        try:
            api_transcript = YouTubeTranscriptApi.get_transcript(video.youtube_id)
            transcript_data = [{'start': item['start'], 'content': item['text']} for item in api_transcript]
            log_list.append('  -> SUCCESS: Successfully fetched from YouTube API.')
            return transcript_data, False
        
        except Exception as e_api:
            log_list.append(f'  -> API method failed ({e_api}). Using Whisper fallback.')
            return None, True

    elif video.vimeo_id:
        vimeo_client = initialize_vimeo_client()
        if vimeo_client:
            log_list.append('  -> Checking Vimeo API for text tracks...')
            api_path = f'/videos/{video.vimeo_id}/texttracks'
            try:
                response = vimeo_client.get(api_path)
                if response.status_code == 200 and response.json().get('data'):
                    log_list.append("  -> Found Vimeo text tracks. Download not implemented. Using Whisper.")
                else:
                    log_list.append('  -> No pre-made Vimeo text tracks. Using Whisper.')
            except Exception as e:
                log_list.append(f'  -> Vimeo API check failed: {e}. Using Whisper.')
        else:
            log_list.append('  -> No Vimeo client. Using Whisper.')
        
        return None, True

    else:
         log_list.append('  -> Unknown platform. Using Whisper.')
         return None, True