import os
import yt_dlp
import logging
from django.conf import settings
from .utils import sanitize_filename

logger = logging.getLogger(__name__)

def download_audio(video, log_list):
    """
    Downloads the audio for a given Video object using yt-dlp.
    Returns the final file path on success, or None on failure.
    """
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
        logger.error(f"yt_dlp DownloadError for video {video_id}: {de}")
        return None
    except Exception as e:
        log_list.append(f'  -> ERROR: General error downloading audio: {e}')
        logger.error(f"General error downloading audio for video {video_id}: {e}", exc_info=True)
        return None