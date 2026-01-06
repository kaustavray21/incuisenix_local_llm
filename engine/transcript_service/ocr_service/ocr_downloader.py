import os
import glob
import yt_dlp
import uuid
import logging
import time
import random
import subprocess
from django.conf import settings

logger = logging.getLogger(__name__)

class VideoDownloader:
    def __init__(self):
        self.temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp_videos')
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)

    def _clean_url(self, url: str) -> str:
        if "player.vimeo.com/video/" in url:
            video_id = url.split('player.vimeo.com/video/')[-1].split('?')[0]
            return f"https://vimeo.com/{video_id}"
        
        if "vimeo.com/" in url and "player." not in url:
            return url.split('?')[0]

        if "youtube.com/embed/" in url:
            video_id = url.split("youtube.com/embed/")[-1].split('?')[0]
            return f"https://www.youtube.com/watch?v={video_id}"
            
        if "youtu.be/" in url:
             video_id = url.split("youtu.be/")[-1].split('?')[0]
             return f"https://www.youtube.com/watch?v={video_id}"

        if "youtube.com/watch" in url:
            if "&" in url:
                return url.split('&')[0]
            return url
            
        return url

    def _transcode_to_h264(self, input_path: str) -> str:
        """
        Manually runs FFmpeg to force re-encoding to H.264.
        OPTIMIZATION: Removes audio (-an) since OCR doesn't need it.
        """
        base_name, _ = os.path.splitext(input_path)
        temp_output = f"{base_name}_fixed.mp4"
        
        cmd = [
            'ffmpeg', '-y', 
            '-i', input_path,
            '-c:v', 'libx264', # Force H.264 Video
            '-an',             # Remove Audio (Faster, smaller file)
            '-preset', 'fast',
            '-crf', '23',
            temp_output
        ]
        
        logger.info(f"Downloader: Transcoding to video-only H.264: {input_path} -> {temp_output}")
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            
            if os.path.exists(input_path):
                os.remove(input_path)
            return temp_output
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Downloader: FFmpeg transcoding failed: {e.stderr.decode() if e.stderr else 'Unknown error'}")
            return input_path
        except Exception as e:
            logger.error(f"Downloader: Transcoding error: {e}")
            return input_path

    def download_video(self, url: str) -> str:
        sleep_time = random.uniform(2, 5)
        logger.info(f"Downloader: Sleeping for {sleep_time:.2f}s...")
        time.sleep(sleep_time)

        cleaned_url = self._clean_url(url)
        unique_name = str(uuid.uuid4())
        output_template = os.path.join(self.temp_dir, f"{unique_name}.%(ext)s")

        vimeo_referer = os.getenv('VIMEO_REFERER', 'https://vimeo.com/')

        ydl_opts = {
            # OPTIMIZATION: 'bestvideo' ONLY. 
            # We do not download '+bestaudio' because OCR does not need sound.
            'format': 'bestvideo/best', 
            'outtmpl': output_template,
            'quiet': False,
            'no_warnings': False,
            'noplaylist': True,
            'nocheckcertificate': True,
            'sleep_interval': 3,
            'max_sleep_interval': 10,
            'ignoreerrors': False,
        }

        if "vimeo" in cleaned_url:
            ydl_opts['http_headers'] = {
                'Referer': vimeo_referer,
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            }
            vimeo_username = os.getenv('VIMEO_USERNAME')
            vimeo_password = os.getenv('VIMEO_PASSWORD')
            if vimeo_username and vimeo_password:
                ydl_opts['username'] = vimeo_username
                ydl_opts['password'] = vimeo_password

        try:
            logger.info(f"Downloader: Downloading video only (No Audio) from {cleaned_url}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.extract_info(cleaned_url, download=True)
                
                search_pattern = os.path.join(self.temp_dir, f"{unique_name}.*")
                found_files = glob.glob(search_pattern)

                if found_files:
                    actual_file = max(found_files, key=os.path.getsize)
                    
                    if os.path.getsize(actual_file) == 0:
                        logger.error(f"Downloader: Downloaded file is empty: {actual_file}")
                        self.cleanup(actual_file)
                        return None
                    
                    final_file = self._transcode_to_h264(actual_file)
                    
                    logger.info(f"Downloader: Valid file ready at {final_file}")
                    return os.path.abspath(final_file)
                else:
                    logger.error(f"Downloader: No file found for ID {unique_name}")
                    return None

        except Exception as e:
            logger.error(f"Downloader: Failed to download {cleaned_url}. Error: {str(e)}")
            return None

    def cleanup(self, file_path: str):
        if not file_path: return
        
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"Downloader: Deleted {file_path}")
            except Exception as e:
                logger.warning(f"Downloader: Failed to delete {file_path}: {e}")
        
        base = os.path.splitext(file_path)[0]
        if "_fixed" in base:
            clean_base = base.replace("_fixed", "")
            for ext in ['.mp4', '.mkv', '.webm']:
                orig = clean_base + ext
                if os.path.exists(orig):
                    try: os.remove(orig)
                    except: pass