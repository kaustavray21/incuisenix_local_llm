import os
import re
import csv
import whisper
import yt_dlp
import vimeo
import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand
from core.models import Video
from youtube_transcript_api import YouTubeTranscriptApi

def sanitize_filename(title):
    """Sanitizes a string for use as a filename/directory."""
    return re.sub(r'[\\/*?:"<>|]', "", title)

class Command(BaseCommand):
    help = 'Generates transcript CSV files for videos (YouTube/Vimeo) that do not have them.'

    def handle(self, *args, **options):
        self.stdout.write('Starting transcript file generation process...')

        # --- Whisper Model Loading ---
        try:
            self.whisper_model = whisper.load_model("base")
            self.stdout.write("Whisper model loaded successfully.")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to load Whisper model: {e}"))
            self.stdout.write(self.style.WARNING("Ensure 'openai-whisper' and ffmpeg are installed."))
            return
            
        # --- Vimeo Client Initialization ---
        self.vimeo_client = self.initialize_vimeo_client()

        # --- Process Videos ---
        videos_to_check = Video.objects.all()
        self.stdout.write(f'Found {videos_to_check.count()} total videos to check.')
        
        for video in videos_to_check:
            platform = "Unknown"
            video_id = None

            if video.youtube_id:
                platform = "YouTube"
                video_id = video.youtube_id
            elif video.vimeo_id:
                platform = "Vimeo"
                video_id = video.vimeo_id
            else:
                self.stdout.write(self.style.ERROR(f'Video "{video.title}" has no ID. Skipping.'))
                continue
                
            course_dir_safe = sanitize_filename(video.course.title)
            transcript_dir = os.path.join(settings.MEDIA_ROOT, 'transcripts', course_dir_safe)
            os.makedirs(transcript_dir, exist_ok=True)
            transcript_path = os.path.join(transcript_dir, f"{video_id}.csv")

            # --- This is the "smart" check from your original file ---
            if os.path.exists(transcript_path):
                self.stdout.write(self.style.NOTICE(f'Transcript CSV for "{video.title}" already exists. Skipping.'))
                continue

            self.stdout.write(f'\n--- Processing video: "{video.title}" ({platform}) ---')
            transcript_data = None
            use_whisper = False

            # --- Attempt Faster Transcript Methods ---
            try:
                if platform == "YouTube":
                    self.stdout.write('  -> Trying YouTube Transcript API...')
                    api_transcript = YouTubeTranscriptApi.get_transcript(video.youtube_id)
                    transcript_data = [{'start': item['start'], 'content': item['text']} for item in api_transcript]
                    self.stdout.write(self.style.SUCCESS('  -> Successfully fetched from YouTube API.'))
                
                elif platform == "Vimeo" and self.vimeo_client:
                    self.stdout.write('  -> Checking Vimeo API for text tracks...')
                    api_path = f'/videos/{video.vimeo_id}/texttracks'
                    response = self.vimeo_client.get(api_path)
                    if response.status_code == 200 and response.json().get('data'):
                         self.stdout.write(self.style.WARNING("  -> Found Vimeo text tracks. Download not implemented. Using Whisper."))
                         use_whisper = True
                    else:
                         self.stdout.write('  -> No pre-made Vimeo text tracks. Using Whisper.')
                         use_whisper = True
                else:
                     use_whisper = True
                     if platform == "Vimeo":
                         self.stdout.write('  -> No Vimeo client. Using Whisper.')
            
            except Exception as e_api:
                self.stdout.write(self.style.WARNING(f'  -> API method failed ({e_api}). Using Whisper fallback.'))
                use_whisper = True

            # --- Whisper Fallback ---
            if use_whisper:
                audio_path = self.download_audio(video)
                if audio_path:
                    whisper_segments = self.transcribe_with_whisper(audio_path, self.whisper_model)
                    if whisper_segments:
                         transcript_data = [{'start': seg['start'], 'content': seg['text']} for seg in whisper_segments]
                    
                    try:
                        os.remove(audio_path)
                        self.stdout.write(self.style.SUCCESS(f'  -> Cleaned up audio file: {os.path.basename(audio_path)}'))
                    except OSError as e:
                        self.stdout.write(self.style.WARNING(f'  -> Could not remove audio file: {e}'))
                else:
                    self.stdout.write(self.style.ERROR('  -> Skipping CSV save due to download failure.'))
                    transcript_data = None

            # --- Save Transcript to CSV File ---
            if transcript_data:
                try:
                    df = pd.DataFrame(transcript_data)
                    # Ensure columns are in the order you expect, matching populate_transcripts
                    df = df[['start', 'content']] 
                    df.to_csv(transcript_path, index=False, quoting=csv.QUOTE_ALL)
                    self.stdout.write(self.style.SUCCESS(f'  -> Successfully saved transcript CSV: {transcript_path}'))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  -> Failed to save CSV file: {e}'))
            else:
                 self.stdout.write(self.style.ERROR('  -> No transcript data was generated to save.'))

        self.stdout.write(self.style.SUCCESS('\nFinished transcript file generation.'))

    def initialize_vimeo_client(self):
        VIMEO_TOKEN = os.getenv('VIMEO_TOKEN')
        VIMEO_KEY = os.getenv('VIMEO_KEY')
        VIMEO_SECRET = os.getenv('VIMEO_SECRET')
        if VIMEO_TOKEN and VIMEO_KEY and VIMEO_SECRET:
            try:
                client = vimeo.VimeoClient(token=VIMEO_TOKEN, key=VIMEO_KEY, secret=VIMEO_SECRET)
                self.stdout.write("Vimeo client initialized.")
                return client
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to initialize Vimeo client: {e}"))
        else:
            self.stdout.write(self.style.WARNING("VIMEO .env credentials missing. Skipping Vimeo API checks."))
        return None

    def download_audio(self, video):
        self.stdout.write('  -> Downloading audio for Whisper...')
        video_id = video.youtube_id or video.vimeo_id
        course_dir = sanitize_filename(video.course.title)
        download_dir = os.path.join(settings.MEDIA_ROOT, 'temp_audio', course_dir)
        os.makedirs(download_dir, exist_ok=True)
        
        output_template = os.path.join(download_dir, f'{video_id}.%(ext)s')
        final_filepath = os.path.join(download_dir, f'{video_id}.mp3')

        if os.path.exists(final_filepath):
             self.stdout.write(self.style.WARNING(f'  -> Reusing existing audio file: {os.path.basename(final_filepath)}'))
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
                    self.stdout.write(self.style.SUCCESS(f'  -> Audio downloaded: {os.path.basename(final_filepath)}'))
                    return final_filepath
                else:
                    self.stdout.write(self.style.ERROR('  -> Downloaded audio file not found at expected path.'))
                    return None
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  -> Error downloading audio: {e}'))
            return None

    def transcribe_with_whisper(self, audio_path, model):
        self.stdout.write(f'  -> Transcribing "{os.path.basename(audio_path)}" with Whisper...')
        try:
            result = model.transcribe(audio_path, fp16=False) 
            self.stdout.write(self.style.SUCCESS('  -> Whisper transcription successful.'))
            return result.get('segments', [])
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  -> Error during Whisper transcription: {e}'))
            return None