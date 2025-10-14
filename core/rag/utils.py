import re

def parse_timestamp_from_query(query):
    """
    Finds a timestamp in formats like HH:MM:SS, MM:SS, or "X minutes/minute"
    and converts it to seconds.
    
    This function uses regular expressions to find time patterns in the user's text
    and converts them into a total number of seconds.
    
    Args:
        query (str): The user's input query.
        
    Returns:
        int: The timestamp in total seconds, or None if no timestamp is found.
    """
    # Regex to find patterns like "30th minute", "15 minutes", or "5 min"
    minute_match = re.search(r'(\d+)\s*(?:minute|minutes|min|th minute)', query, re.IGNORECASE)
    if minute_match:
        minutes = int(minute_match.group(1))
        return minutes * 60

    # Regex to find patterns like 12:34:56 or 12:34
    time_match = re.search(r'(\d{1,2}):(\d{1,2}):(\d{1,2})|(\d{1,2}):(\d{1,2})', query)
    if not time_match:
        return None
        
    # Filter out the None values from the regex groups
    time_parts_str = [p for p in time_match.groups() if p is not None]
    time_parts = [int(p) for p in time_parts_str]
    
    seconds = 0
    if len(time_parts) == 3:  # Format HH:MM:SS
        seconds = time_parts[0] * 3600 + time_parts[1] * 60 + time_parts[2]
    elif len(time_parts) == 2:  # Format MM:SS
        seconds = time_parts[0] * 60 + time_parts[1]
        
    return seconds if seconds > 0 else None

def get_context_window(all_docs, target_index, window_size=1):
    """
    Retrieves a window of documents around a central target index.
    
    This is used to get the transcript segments immediately before and after the
    segment that matches the user's timestamp, providing better context for the AI.
    
    Args:
        all_docs (list): The list of all transcript documents for the video.
        target_index (int): The index of the primary document of interest.
        window_size (int): How many documents to retrieve on either side of the target.
        
    Returns:
        list: A new list of documents representing the context window.
    """
    # Calculate the start index, ensuring it's not less than 0
    start_index = max(0, target_index - window_size)
    
    # Calculate the end index, ensuring it doesn't exceed the list length
    end_index = min(len(all_docs), target_index + window_size + 1)
    
    return all_docs[start_index:end_index]