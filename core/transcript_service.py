# core/transcript_service.py

import os
import re
import csv
import whisper
import yt_dlp
import vimeo
import pandas as pd
import logging
from django.conf import settings
from .models import Video, Transcript # <-- ADDED Transcript
from youtube_transcript_api import YouTubeTranscriptApi

logger = logging.getLogger(__name__)

# --- Helper Functions (Refactored from command) ---

def sanitize_filename(title):
    return re.sub(r'[\\/*?:"<>|]', "", title)

def _initialize_vimeo_client():
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

def _download_audio(video, log_list):
    log_list.append('  -> Downloading audio for Whisper...')
    video_id = video.youtube_id or video.vimeo_id
    course_dir = sanitize_filename(video.course.title)
    download_dir = os.path.join(settings.MEDIA_ROOT, 'temp_audio', course_dir)
    os.makedirs(download_dir, exist_ok=True)
    
    output_template = os.path.join(download_dir, f'{video_id}.%(ext)s')
    final_filepath = os.path.join(download_dir, f'{video_id}.mp3')

    if os.path.exists(final_filepath):
         log_list.append(f'  -> Reusing existing audio file: {os.path.basename(final_filepath)}')
         return final_filepath

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': output_template,
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}],
        'quiet': True,
    }

    if video.vimeo_id and os.getenv('VIMEO_TOKEN'):
         ydl_opts['http_headers'] = {'Authorization': f'bearer {os.getenv("VIMEO_TOKEN")}'}

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video.video_url])
            if os.path.exists(final_filepath):
                log_list.append(f'  -> SUCCESS: Audio downloaded: {os.path.basename(final_filepath)}')
                return final_filepath
            else:
                log_list.append('  -> ERROR: Downloaded audio file not found at expected path.')
                return None
    except Exception as e:
        log_list.append(f'  -> ERROR: Error downloading audio: {e}')
        return None

def _transcribe_with_whisper(audio_path, model, log_list):
    log_list.append(f'  -> Transcribing "{os.path.basename(audio_path)}" with Whisper...')
    try:
        result = model.transcribe(audio_path, fp16=False) 
        log_list.append('  -> SUCCESS: Whisper transcription successful.')
        return result.get('segments', [])
    except Exception as e:
        log_list.append(f'  -> ERROR: Error during Whisper transcription: {e}')
        return None

# --- Main Public Function ---

def generate_transcript_for_video(video: Video, force_generation: bool = False):
    """
    Generates a transcript CSV for a single video.
    Saves to CSV AND populates the database Transcript model.
    Returns a tuple: (status_message, log_list)
    """
    log_list = []
    
    platform = "Unknown"
    video_id = None

    if video.youtube_id:
        platform = "YouTube"
        video_id = video.youtube_id
    elif video.vimeo_id:
        platform = "Vimeo"
        video_id = video.vimeo_id
    else:
        log_list.append(f'ERROR: Video "{video.title}" has no ID. Skipping.')
        return "Error", log_list
        
    course_dir_safe = sanitize_filename(video.course.title)
    transcript_dir = os.path.join(settings.MEDIA_ROOT, 'transcripts', course_dir_safe)
    os.makedirs(transcript_dir, exist_ok=True)
    transcript_path = os.path.join(transcript_dir, f"{video_id}.csv")

    if os.path.exists(transcript_path) and not force_generation:
        log_list.append(f'Transcript CSV for "{video.title}" already exists. Skipping.')
        return "Skipped (exists)", log_list

    log_list.append(f'--- Processing video: "{video.title}" ({platform}) ---')
    transcript_data = None # This will be a list of dicts
    use_whisper = False

    # --- Load Whisper Model ---
    try:
        whisper_model = whisper.load_model("base")
        log_list.append("Whisper model loaded successfully.")
    except Exception as e:
        log_list.append(f"ERROR: Failed to load Whisper model: {e}")
        return "Error", log_list

    # --- Attempt Faster Transcript Methods ---
    try:
        if platform == "YouTube":
            log_list.append('  -> Trying YouTube Transcript API...')
            api_transcript = YouTubeTranscriptApi.get_transcript(video.youtube_id)
            transcript_data = [{'start': item['start'], 'content': item['text']} for item in api_transcript]
            log_list.append('  -> SUCCESS: Successfully fetched from YouTube API.')
        
        elif platform == "Vimeo":
            vimeo_client = _initialize_vimeo_client()
            if vimeo_client:
                log_list.append('  -> Checking Vimeo API for text tracks...')
                api_path = f'/videos/{video.vimeo_id}/texttracks'
                response = vimeo_client.get(api_path)
                if response.status_code == 200 and response.json().get('data'):
                     log_list.append("  -> Found Vimeo text tracks. Download not implemented. Using Whisper.")
                     use_whisper = True
                else:
                     log_list.append('  -> No pre-made Vimeo text tracks. Using Whisper.')
                     use_whisper = True
            else:
                log_list.append('  -> No Vimeo client. Using Whisper.')
                use_whisper = True
        else:
             use_whisper = True
    
    except Exception as e_api:
        log_list.append(f'  -> API method failed ({e_api}). Using Whisper fallback.')
        use_whisper = True

    # --- Whisper Fallback ---
    if use_whisper:
        audio_path = _download_audio(video, log_list)
        if audio_path:
            whisper_segments = _transcribe_with_whisper(audio_path, whisper_model, log_list)
            if whisper_segments:
                 transcript_data = [{'start': seg['start'], 'content': seg['text']} for seg in whisper_segments]
            
            try:
                os.remove(audio_path)
                log_list.append(f'  -> SUCCESS: Cleaned up audio file: {os.path.basename(audio_path)}')
            except OSError as e:
                log_list.append(f'  -> WARNING: Could not remove audio file: {e}')
        else:
            log_list.append('  -> ERROR: Skipping CSV save due to download failure.')
            transcript_data = None

    # --- Save Transcript to CSV and Database ---
    if transcript_data:
        # --- 1. Save to CSV File ---
        try:
            df = pd.DataFrame(transcript_data)
            df = df[['start', 'content']] 
            df.to_csv(transcript_path, index=False, quoting=csv.QUOTE_ALL)
            log_list.append(f'  -> SUCCESS: Successfully saved transcript CSV: {transcript_path}')
        except Exception as e:
            log_list.append(f'  -> ERROR: Failed to save CSV file: {e}')
            return "Error", log_list # Return early if CSV fails

        # --- 2. Save to Database (NEW LOGIC) ---
        try:
            log_list.append('  -> Populating database...')
            # Delete old entries for this video
            Transcript.objects.filter(video=video).delete()
            log_list.append('  -> Old database entries cleared.')

            # Create new entries
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
            Transcript.objects.bulk_create(transcripts_to_create)
            log_list.append(f'  -> SUCCESS: Populated database with {len(transcripts_to_create)} lines.')
            
            return "Generated", log_list
            
        except Exception as e:
            log_list.append(f'  -> ERROR: Failed to populate database: {e}')
            return "Error", log_list
            
    else:
         log_list.append('  -> ERROR: No transcript data was generated to save.')
         return "Error", log_list