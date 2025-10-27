import re
import logging
from django.db.models import Q # Import Q
from django.shortcuts import get_object_or_404 # Import get_object_or_404
from .chains import (
    get_rag_chain,
    get_time_based_chain,
    get_summarizer_chain,
    get_general_chain,
    get_query_type_classifier_chain
)
from ..models import Transcript, Note, Video # Import Video

logger = logging.getLogger(__name__)

# --- parse_time function remains the same ---
def parse_time(query: str, timestamp: float) -> float | None:
    # ... (keep existing code) ...
    time_pattern = r"(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?"
    match = re.search(time_pattern, query)
    if match:
        parts = [int(p) for p in match.groups() if p is not None]
        if len(parts) == 3:
            h, m, s = parts
            return h * 3600 + m * 60 + s
        elif len(parts) == 2:
            m, s = parts
            return m * 60 + s

    minute_match = re.search(r'(\d+)\s*(?:minute|min)', query, re.IGNORECASE)
    if minute_match:
        return int(minute_match.group(1)) * 60

    if "this moment" in query.lower() or "right now" in query.lower():
        return timestamp

    return None

def query_router(query: str, video_id: str, timestamp: float, chat_history: str, user_id: int):
    
    # --- Find the Video object first ---
    try:
        video = get_object_or_404(
            Video,
            Q(youtube_id=video_id) | Q(vimeo_id=video_id)
        )
        logger.info(f"Query Router: Found video {video.pk} for platform ID {video_id}")
    except Exception as e:
         logger.error(f"Query Router: Could not find video for ID {video_id}: {e}")
         return "Sorry, I couldn't identify the video associated with this request."
    # --- End finding video ---

    # --- PRIORITY 1: SUMMARIZATION ---
    summarization_keywords = ['summarize', 'summary', 'overview', 'tldr', 'key points']
    if any(keyword in query.lower() for keyword in summarization_keywords):
        logger.info("Routing to: Summarizer Chain")
        # --- FIXED QUERY ---
        transcripts_qs = Transcript.objects.filter(video=video).order_by('start')
        if not transcripts_qs.exists():
             return "I couldn't find a transcript to summarize for this video."
        full_transcript = " ".join(t.content for t in transcripts_qs)
        # --- END FIXED QUERY ---

        summarizer_chain = get_summarizer_chain()
        return summarizer_chain.invoke({"context": full_transcript, "question": query})

    # --- PRIORITY 2: TIME-BASED QUERY ---
    parsed_seconds = parse_time(query, timestamp)
    if parsed_seconds is not None:
        logger.info(f"Routing to: Time-Based Chain (Time: {parsed_seconds}s)")
        try:
            # --- FIXED QUERY ---
            transcript_segment = Transcript.objects.filter(
                video=video, # Use the found video object
                start__lte=parsed_seconds
            ).latest('start')
            # --- END FIXED QUERY ---
            context = transcript_segment.content
            
            time_chain = get_time_based_chain()
            return time_chain.invoke({"context": context, "question": query})
        except Transcript.DoesNotExist:
             logger.warning(f"No transcript segment found for video {video.pk} at or before {parsed_seconds}s")
             # Try RAG chain as fallback? Or return specific message.
             # return "I couldn't find any transcript information for that specific time."
             # Let's try falling through to RAG instead for better chance of answer
             logger.info("Time-based segment not found, falling back to RAG.")
             pass # Explicitly fall through to classifier/RAG


    # --- PRIORITY 3: CLASSIFIER ROUTING ---
    logger.info("Routing to: Query Type Classifier")
    classifier_chain = get_query_type_classifier_chain()
    # Handle potential errors during classification
    try:
        classification = classifier_chain.invoke({"question": query}).strip()
        logger.info(f"Classification result: {classification}")
    except Exception as e:
        logger.error(f"Query classification failed: {e}. Defaulting to RAG.")
        classification = "RAG" # Default to RAG on classifier error


    if "Fetch_Notes" in classification:
        logger.info("Routing to: Fetch Notes (Direct DB Query)")
        
        # --- FIXED QUERY ---
        notes = Note.objects.filter(
            user__id=user_id,
            video=video # Use the found video object
        ).order_by('video_timestamp')
        # --- END FIXED QUERY ---
        
        if not notes.exists():
            return "You haven't created any notes for this video yet."
        
        response_message = "Here are your notes for this video:\n\n"
        for note in notes:
            minutes = int(note.video_timestamp // 60)
            seconds = int(note.video_timestamp % 60)
            formatted_time = f"{minutes}:{seconds:02d}"
            
            response_message += f"* **(at {formatted_time}) - {note.title}**\n"
            # Limit content length if necessary
            content_preview = note.content[:200] + ('...' if len(note.content) > 200 else '')
            response_message += f"    * {content_preview}\n" # Indent content
        
        return response_message

    if "General" in classification:
        logger.info("Routing to: General Chain")
        return get_general_chain().invoke({"question": query})

    # --- DEFAULT ROUTING: RAG ---
    # This branch is hit if classification is 'RAG' or if classifier failed
    logger.info("Routing to: Standard RAG Chain")
    rag_chain = get_rag_chain(video_id, user_id=user_id) # get_rag_chain needs the platform ID
    return rag_chain.invoke({
        "question": query,
        "chat_history": chat_history
    })