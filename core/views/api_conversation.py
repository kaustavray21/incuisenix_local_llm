import logging
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
# --- Import timezone utils ---
from django.utils import timezone
from ..models import Conversation, ConversationMessage, Video

logger = logging.getLogger(__name__)

@login_required
def get_conversation_list(request):
    """
    Get all conversations for the logged-in user.
    """
    # --- REMOVED: video_id filter ---
    # We are now fetching all conversations
    
    try:
        # Get all conversations for the current user
        conversations = Conversation.objects.filter(
            user=request.user
        ).select_related('video', 'video__course').order_by('-created_at') # Show newest first
        
        # Format the data
        data = []
        for convo in conversations:
            # --- NEW: Format date to IST ---
            # Convert created_at (which is timezone-aware) to IST
            ist_time = convo.created_at.astimezone(timezone.get_current_timezone())
            
            data.append({
                'id': convo.id,
                'title': convo.title,
                # --- NEW: Add video context ---
                'video_id': convo.video.youtube_id,
                'video_title': convo.video.title,
                'course_title': convo.video.course.title,
                # --- UPDATED: Use IST formatted time ---
                'created_at': ist_time.strftime('%B %d, %Y - %I:%M %p')
            })
        
        return JsonResponse(data, safe=False)

    except Exception as e:
        logger.error(f"Error getting conversation list for user {request.user.id}: {e}", exc_info=True)
        return JsonResponse({'error': 'An error occurred.'}, status=500)

@login_required
def get_conversation_messages(request, conversation_id):
    """
    Get all messages for a specific conversation.
    """
    try:
        # Ensure the conversation exists and belongs to the user
        conversation = get_object_or_404(
            Conversation,
            id=conversation_id,
            user=request.user
        )
        
        # Get all messages for this conversation, ordered by timestamp
        messages = conversation.messages.all().order_by('timestamp')
        
        data = [
            {
                'query': msg.query,
                'answer': msg.answer,
                'timestamp': msg.timestamp.isoformat()
            }
            for msg in messages
        ]
        
        return JsonResponse(data, safe=False)

    except Conversation.DoesNotExist:
        return JsonResponse({'error': 'Conversation not found.'}, status=4.04)
    except Exception as e:
        logger.error(f"Error getting messages for conversation {conversation_id}: {e}", exc_info=True)
        return JsonResponse({'error': 'An error occurred.'}, status=500)