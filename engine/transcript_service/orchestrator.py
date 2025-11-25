import os
import logging
from core.models import Video

# Import all our new helper functions
from .providers import get_api_transcript
from .downloader import download_audio
from .transcriber import transcribe_with_whisper
from .db_writer import save_and_populate_transcript

logger = logging.getLogger(__name__)

def generate_transcript_for_video(video_id: int):
    """
    Orchestrates the complete transcript generation pipeline for a single video.
    This is the main function to be called by background tasks.
    """
    log_list = []
    video = None
    audio_path = None # To track the temp audio file for cleanup

    try:
        video = Video.objects.get(id=video_id)
        log_list.append(f'--- Processing video ID: {video.id} ("{video.title}") ---')

        # Step 1: Try to get transcript from an API (e.g., YouTube)
        transcript_data, use_whisper = get_api_transcript(video, log_list)

        # Step 2: If API fails or isn't applicable, use Whisper
        if use_whisper:
            # 2a. Download the audio file
            audio_path = download_audio(video, log_list)
            
            if audio_path:
                # 2b. Transcribe the audio file
                whisper_segments = transcribe_with_whisper(audio_path, log_list)
                
                if whisper_segments:
                    transcript_data = [{'start': seg['start'], 'content': seg['text']} for seg in whisper_segments]
                else:
                    raise Exception("Whisper transcription failed or returned no segments.")
            else:
                raise Exception("Audio download failed. Cannot transcribe.")

        # Step 3: Save results to CSV and Database
        if transcript_data:
            save_and_populate_transcript(video, transcript_data, log_list)
            
            # Step 4: Final success update
            video.transcript_status = 'complete'
            video.index_status = 'none'
            video.save()
            log_list.append(f'--- Finished. Set video {video.id} status to "complete" ---')
            return "Generated", log_list
            
        else:
             raise Exception("No transcript data was generated to save.")

    except Exception as e:
        logger.error(f"Failed to generate transcript for video {video_id}: {e}", exc_info=True)
        log_list.append(f'  -> FATAL ERROR: {e}')
        
        # Set video status to 'failed' on any error
        if video:
            video.transcript_status = 'failed'
            video.save()
            log_list.append(f'--- Finished. Set video {video.id} status to "failed" ---')
            
        return "Error", log_list
    
    finally:
        # Step 5: Always clean up the audio file if it exists
        if audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
                log_list.append(f'  -> SUCCESS: Cleaned up audio file: {os.path.basename(audio_path)}')
            except OSError as e:
                log_list.append(f'  -> WARNING: Could not remove audio file: {e}')