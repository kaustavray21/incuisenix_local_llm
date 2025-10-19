import re
from .chains import (
    get_rag_chain, 
    get_time_based_chain, 
    get_classifier_chain, 
    get_summarizer_chain,
    get_general_chain,
    get_decider_chain
)
from .vector_store import get_retriever
from ..models import Transcript

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

    print("Routing to: Classifier to determine context")
    classifier_chain = get_classifier_chain()
    classification = classifier_chain.invoke({"question": query})
    print(f"Classification: {classification}")

    if "General" in classification:
        print("Routing to: General Chain")
        return get_general_chain().invoke({"question": query})

    print("Routing to: Standard RAG with Decider")
    retriever = get_retriever(video_id, user_id=user_id)
    
    retrieved_docs = retriever.get_relevant_documents(query)
    context = "\n\n".join([doc.page_content for doc in retrieved_docs])

    if not context.strip():
        print("Decider Fallback: No context found. Routing to General Chain.")
        return get_general_chain().invoke({"question": query})

    decider_chain = get_decider_chain()
    decision = decider_chain.invoke({"context": context, "question": query})
    print(f"Decider chose: {decision}")

    if "RAG" in decision:
        print("Decision: Use RAG. Invoking main RAG chain.")
        
        rag_chain = get_rag_chain(video_id, user_id=user_id)
        
        return rag_chain.invoke({
            "question": query,
            "chat_history": chat_history,
            "context": context
        })
    else:
        print("Decision: Fallback to General Chain.")
        return get_general_chain().invoke({"question": query})