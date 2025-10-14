from django.db.models import Max
from core.models import Transcript
from .rag.vector_store import get_vector_store, create_vector_store_for_video
from .rag.chains import (
    get_general_chain, get_rag_chain, get_classifier_chain, 
    get_decider_chain, get_summarizer_chain, get_time_based_chain
)
from .rag.utils import parse_timestamp_from_query, get_context_window

def query_router(query, video_id=None, video_title=None, timestamp=0):
    """
    Routes the query to the correct chain using a robust, multi-step process.
    """
    if not video_id:
        return get_general_chain().invoke({"question": query})

    store = get_vector_store(video_id)
    if not store:
        create_vector_store_for_video(video_id)
        store = get_vector_store(video_id)
        if not store:
            return get_general_chain().invoke({"question": query})

    effective_timestamp = parse_timestamp_from_query(query) or timestamp
    time_keywords = ['this moment', 'right now', 'at this time', 'what is he saying', 'what does this mean', 'what did he just say']
    is_time_sensitive = effective_timestamp > 1 and (parse_timestamp_from_query(query) is not None or any(keyword in query.lower() for keyword in time_keywords))

    if is_time_sensitive:
        print(f"DEBUG: Time-sensitive query. Searching for timestamp: {effective_timestamp}s")
        
        docstore = store.docstore
        index_to_docstore_id = store.index_to_docstore_id
        all_doc_ids = list(index_to_docstore_id.values())
        all_video_docs = [docstore.search(doc_id) for doc_id in all_doc_ids]
        all_video_docs = sorted(all_video_docs, key=lambda doc: doc.metadata.get('start', 0))
        
        print(f"DEBUG: Directly loaded and sorted {len(all_video_docs)} chunks from the docstore.")

        target_index = -1
        
        for i, doc in enumerate(all_video_docs):
            if doc.metadata.get('start', 0) <= effective_timestamp < doc.metadata.get('end', float('inf')):
                target_index = i
                print(f"DEBUG: Found exact match at index {i}")
                break
        
        if target_index == -1 and all_video_docs:
            print("DEBUG: No exact match found. Approximating to the closest time...")
            closest_doc = min(all_video_docs, key=lambda doc: abs(doc.metadata.get('start', 0) - effective_timestamp))
            target_index = all_video_docs.index(closest_doc)
            
            closest_time = closest_doc.metadata.get('start', 0)
            print(f"DEBUG: Found closest match at index {target_index} (time: {closest_time}s)")

        if target_index != -1:
            context_docs = get_context_window(all_video_docs, target_index, window_size=5)
            context = "\n\n".join([doc.page_content for doc in context_docs])
            
            print("-" * 50)
            print("DEBUG: FINAL CONTEXT SENT TO TIME-BASED CHAIN:")
            print(context)
            print("-" * 50)
            
            # --- FINAL FIX: Use the new, specialized time-based chain ---
            time_chain = get_time_based_chain()
            # We only need to pass the context, as the prompt itself frames the question.
            answer = time_chain.invoke({"context": context})
            
            print("DEBUG: FINAL ANSWER RECEIVED FROM AI MODEL:")
            print(f"'{answer}'")
            print("-" * 50)

            return answer
        else:
            return "I couldn't retrieve the transcript for this video to answer your question."

    # Summarization and other queries remain the same
    summarization_keywords = ['summarize', 'summary', 'overview', 'what is this video about', 'key points', 'give me a tldr']
    if any(keyword in query.lower() for keyword in summarization_keywords):
        retriever = store.as_retriever(search_kwargs={'k': 500})
        all_video_docs = retriever.get_relevant_documents("")
        full_transcript_context = "\n\n".join([doc.page_content for doc in all_video_docs])
        summarizer_chain = get_summarizer_chain()
        return summarizer_chain.invoke({"context": full_transcript_context, "question": query})

    print("Standard video-specific query detected. Using Decider-based RAG.")
    retriever = store.as_retriever(search_kwargs={'k': 5})
    docs = retriever.get_relevant_documents(query)
    context = "\n\n".join([doc.page_content for doc in docs])

    decider_chain = get_decider_chain()
    decision = decider_chain.invoke({"context": context, "question": query})
    print(f"Decider chose: {decision}")

    if "RAG" in decision and context:
        rag_chain = get_rag_chain()
        return rag_chain.invoke({"context": context, "question": query})

    print("Routing to general knowledge chain (default).")
    return get_general_chain().invoke({"question": query})