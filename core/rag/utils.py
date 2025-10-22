import re
import logging
from .chains import (
    get_rag_chain, 
    get_time_based_chain, 
    get_summarizer_chain,
    get_general_chain,
    get_query_type_classifier_chain
)
from ..models import Transcript, Note, Video
from django.shortcuts import get_object_or_404

logger = logging.getLogger(__name__)

def parse_time(query: str, timestamp: float) -> float | None:
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
    
    summarization_keywords = ['summarize', 'summary', 'overview', 'tldr', 'key points']
    if any(keyword in query.lower() for keyword in summarization_keywords):
        logger.info("Routing to: Summarizer Chain")
        full_transcript = " ".join(
            t.content for t in Transcript.objects.filter(video__youtube_id=video_id).order_by('start')
        )
        if not full_transcript:
            return "I couldn't find a transcript to summarize for this video."
        
        summarizer_chain = get_summarizer_chain()
        return summarizer_chain.invoke({"context": full_transcript, "question": query})

    parsed_seconds = parse_time(query, timestamp)
    if parsed_seconds is not None:
        logger.info(f"Routing to: Time-Based Chain (Time: {parsed_seconds}s)")
        try:
            transcript_segment = Transcript.objects.filter(
                video__youtube_id=video_id,
                start__lte=parsed_seconds
            ).latest('start')
            context = transcript_segment.content if transcript_segment else "No transcript available for this specific moment."
            
            time_chain = get_time_based_chain()
            return time_chain.invoke({"context": context, "question": query})
        except Transcript.DoesNotExist:
            return "I couldn't find any transcript information for that specific time."

    logger.info("Routing to: Query Type Classifier")
    classifier_chain = get_query_type_classifier_chain()
    classification = classifier_chain.invoke({"question": query})
    logger.info(f"Classification: {classification}")

    if "Fetch_Notes" in classification:
        logger.info("Routing to: Fetch Notes (Direct DB Query)")
        try:
            video = get_object_or_404(Video, youtube_id=video_id)
            notes = Note.objects.filter(user__id=user_id, video=video).order_by('video_timestamp')
            
            if not notes.exists():
                return "You haven't created any notes for this video yet."
            
            response_message = "Here are your notes for this video:\n\n"
            for note in notes:
                minutes = int(note.video_timestamp // 60)
                seconds = int(note.video_timestamp % 60)
                formatted_time = f"{minutes}:{seconds:02d}"
                
                response_message += f"* **(at {formatted_time}) - {note.title}**\n"
                response_message += f"    * {note.content}\n"
            
            return response_message
        except Exception as e:
            logger.error(f"Error fetching notes from DB: {e}", exc_info=True)
            return "Sorry, I had trouble retrieving your notes from the database."


    if "General" in classification:
        logger.info("Routing to: General Chain")
        return get_general_chain().invoke({"question": query})

    logger.info("Routing to: Standard RAG Chain")
    rag_chain = get_rag_chain(video_id, user_id=user_id)
    return rag_chain.invoke({
        "question": query,
        "chat_history": chat_history
    })