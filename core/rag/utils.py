import re
from .chains import (
    get_rag_chain, 
    get_time_based_chain, 
    get_classifier_chain, 
    get_summarizer_chain,
    get_general_chain,
    get_decider_chain  # Added the decider chain
)
from .vector_store import get_retriever # Added retriever for the decider step
from ..models import Transcript

def parse_time(query: str, timestamp: float) -> float | None:
    """
    Parses a timestamp from a query string, making the assistant more flexible.
    Handles explicit timestamps (e.g., "12:34"), relative phrases ("right now"),
    and vague references ("5-minute mark").
    """
    # This function is already robust and requires no changes.
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


def query_router(query: str, video_id: str, timestamp: float, chat_history: str, notes: str):
    """
    Intelligently routes a user's query to the correct chain using a more robust,
    multi-step process inspired by the older file's logic.
    """
    # --- Step 1: Handle specific intents first (Summarization & Time-Based) ---
    summarization_keywords = ['summarize', 'summary', 'overview', 'tldr', 'key points']
    if any(keyword in query.lower() for keyword in summarization_keywords):
        print("Routing to: Summarizer Chain")
        full_transcript = " ".join(
            t.content for t in Transcript.objects.filter(video__youtube_id=video_id).order_by('start')
        )
        if not full_transcript:
            return "I couldn't find a transcript to summarize for this video."
        
        summarizer_chain = get_summarizer_chain()
        return summarizer_chain.invoke({"context": full_transcript, "question": query})

    parsed_seconds = parse_time(query, timestamp)
    if parsed_seconds is not None:
        print(f"Routing to: Time-Based Chain (Time: {parsed_seconds}s)")
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

    # --- Step 2: Classify if the query is General or Video-Specific ---
    print("Routing to: Classifier to determine context")
    classifier_chain = get_classifier_chain()
    classification = classifier_chain.invoke({"question": query})
    print(f"Classification: {classification}")

    if "General" in classification:
        print("Routing to: General Chain")
        return get_general_chain().invoke({"question": query})

    # --- Step 3: Use RAG with a Decider for all other video-specific questions ---
    # This is the robust logic from the older file.
    print("Routing to: Standard RAG with Decider")
    retriever = get_retriever(video_id)
    retrieved_docs = retriever.get_relevant_documents(query)
    context = "\n\n".join([doc.page_content for doc in retrieved_docs])

    # If no context is found, don't bother the LLM.
    if not context.strip():
        print("Decider Fallback: No context found. Routing to General Chain.")
        return get_general_chain().invoke({"question": query})

    decider_chain = get_decider_chain()
    decision = decider_chain.invoke({"context": context, "question": query})
    print(f"Decider chose: {decision}")

    if "RAG" in decision:
        print("Decision: Use RAG. Invoking main RAG chain.")
        rag_chain = get_rag_chain(video_id)
        # We only pass the retrieved context, not the whole retriever again.
        return rag_chain.invoke({
            "question": query,
            "chat_history": chat_history,
            "notes": notes,
            # We must provide the 'context' key that the chain now expects
            "context": context
        })
    else:
        # The decider determined the context wasn't relevant.
        print("Decision: Fallback to General Chain.")
        return get_general_chain().invoke({"question": query})