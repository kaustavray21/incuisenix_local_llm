import os
import whisper
import logging

logger = logging.getLogger(__name__)

# --- Model Loading ---
# We load the model once when the app starts.
# This is much more efficient than loading it for every video.
try:
    whisper_model = whisper.load_model("base")
    logger.info("Whisper 'base' model loaded successfully into memory.")
except Exception as e:
    logger.error(f"FATAL: Failed to load Whisper 'base' model: {e}", exc_info=True)
    whisper_model = None
# --- End Model Loading ---

def transcribe_with_whisper(audio_path, log_list):
    """
    Transcribes the audio file at the given path using the pre-loaded
    Whisper model.
    """
    log_list.append(f'  -> Transcribing "{os.path.basename(audio_path)}" with Whisper...')
    
    if whisper_model is None:
        log_list.append('  -> ERROR: Whisper model is not loaded. Cannot transcribe.')
        logger.error("transcribe_with_whisper called but Whisper model is not loaded.")
        return None

    try:
        log_list.append(f'  -> Calling model.transcribe()... (This may take a while)')
        result = whisper_model.transcribe(audio_path, fp16=False) 
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
        logger.error(f"Error during Whisper transcription for {audio_path}: {e}", exc_info=True)
        return None