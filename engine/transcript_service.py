import os
import re
import csv
import whisper
import yt_dlp
import vimeo
import pandas as pd
import logging
from django.conf import settings
from core.models import Video, Transcript
from youtube_transcript_api import YouTubeTranscriptApi

logger = logging.getLogger(__name__)

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

    download_url = video.video_url
    log_list.append(f'  -> Using video_url from database: {download_url}')
    
    if video.vimeo_id:
        vimeo_username = os.getenv('VIMEO_USERNAME')
        vimeo_password = os.getenv('VIMEO_PASSWORD')
        
        if vimeo_username and vimeo_password:
            log_list.append('  -> VIMEO_USERNAME and VIMEO_PASSWORD found.')
            ydl_opts['username'] = vimeo_username
            ydl_opts['password'] = vimeo_password
        else:
            log_list.append('  -> WARNING: VIMEO_USERNAME or VIMEO_PASSWORD not set in .env.')
            
        headers = {'Referer': 'https://vimeo.com/'}
        log_list.append(f'  -> Adding base Referer header: https://vimeo.com/')
        ydl_opts['http_headers'] = headers
    
    elif video.youtube_id:
        log_list.append(f'  -> This is a YouTube video.')
    
    if not download_url:
         log_list.append('  -> ERROR: video_url is empty.')
         return None

    try:
        log_list.append('  -> Initializing yt_dlp...')
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            log_list.append(f'  -> Calling ydl.download()...')
            ydl.download([download_url])
            
            if os.path.exists(final_filepath):
                log_list.append(f'  -> SUCCESS: Audio downloaded: {os.path.basename(final_filepath)}')
                return final_filepath
            else:
                log_list.append('  -> ERROR: ydl.download() completed but file not found at expected path.')
                return None
    except yt_dlp.utils.DownloadError as de:
        log_list.append(f'  -> ERROR: yt_dlp DownloadError: {de}')
        return None
    except Exception as e:
        log_list.append(f'  -> ERROR: General error downloading audio: {e}')
        return None

def _transcribe_with_whisper(audio_path, model, log_list):
    log_list.append(f'  -> Transcribing "{os.path.basename(audio_path)}" with Whisper...')
    try:
        log_list.append(f'  -> Calling model.transcribe()... (This may take a while)')
        result = model.transcribe(audio_path, fp16=False) 
        log_list.append('  -> model.transcribe() finished.')
        
        segments = result.get('segments', [])
        num_segments = len(segments)

        if num_segments > 0:
            log_list.append(f'  -> SUCCESS: Whisper transcription successful. Found {num_segments} segments.')
        else:
            log_list.append('  -> WARNING: Whisper transcription complete but found 0 segments.')
            
        return segments
    except Exception as e:
        log_list.append(f'  -> ERROR: Error during Whisper transcription: {e}')
        return None

def _perform_transcript_generation(video_id: int):
    log_list = []
    video = None
    
    try:
        video = Video.objects.get(id=video_id)
        log_list.append(f'--- Processing video ID: {video.id} ("{video.title}") ---')

        platform = "Unknown"
        platform_id = None

        if video.youtube_id:
            platform = "YouTube"
            platform_id = video.youtube_id
        elif video.vimeo_id:
            platform = "Vimeo"
            platform_id = video.vimeo_id
        else:
            raise Exception(f'Video {video.id} has no youtube_id or vimeo_id.')
            
        course_dir_safe = sanitize_filename(video.course.title)
        transcript_dir = os.path.join(settings.MEDIA_ROOT, 'transcripts', course_dir_safe)
        os.makedirs(transcript_dir, exist_ok=True)
        transcript_path = os.path.join(transcript_dir, f"{platform_id}.csv")

        transcript_data = None
        use_whisper = False

        whisper_model = whisper.load_model("base")
        log_list.append("Whisper model loaded successfully.")

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
                raise Exception("Skipping CSV save due to audio download failure.")

        if transcript_data:
            df = pd.DataFrame(transcript_data)
            df = df[['start', 'content']] 
            df.to_csv(transcript_path, index=False, quoting=csv.QUOTE_ALL)
            log_list.append(f'  -> SUCCESS: Successfully saved transcript CSV: {transcript_path}')

            log_list.append('  -> Populating database...')
            Transcript.objects.filter(video=video).delete()
            log_list.append('  -> Old database entries cleared.')

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
            
            video.transcript_status = 'complete'
            video.save()
            log_list.append(f'--- Finished. Set video {video.id} status to "complete" ---')
            return "Generated", log_list
            
        else:
             raise Exception("No transcript data was generated to save.")

    except Exception as e:
        logger.error(f"Failed to generate transcript for video {video_id}: {e}", exc_info=True)
        log_list.append(f'  -> FATAL ERROR: {e}')
        
        if video:
            video.transcript_status = 'failed'
            video.save()
            log_list.append(f'--- Finished. Set video {video.id} status to "failed" ---')
            
        return "Error", log_list