import logging
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ..models import Conversation, ConversationMessage, Video

# Imports for DRF-based delete view
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response


logger = logging.getLogger(__name__)

@login_required
def get_conversation_list(request):
    """
    Get all conversations for the logged-in user.
    """
    try:
        conversations = Conversation.objects.filter(
            user=request.user
        ).select_related('video', 'video__course').order_by('-created_at')
        
        data = []
        for convo in conversations:
            ist_time = convo.created_at.astimezone(timezone.get_current_timezone())
            
            data.append({
                'id': convo.id,
                'title': convo.title,
                'video_id': convo.video.youtube_id,
                'video_title': convo.video.title,
                'course_title': convo.video.course.title,
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
        conversation = get_object_or_404(
            Conversation,
            id=conversation_id,
            user=request.user
        )
        
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
        return JsonResponse({'error': 'Conversation not found.'}, status=404)
    except Exception as e:
        logger.error(f"Error getting messages for conversation {conversation_id}: {e}", exc_info=True)
        return JsonResponse({'error': 'An error occurred.'}, status=500)


@api_view(['DELETE'])
@login_required
def delete_conversation(request, conversation_id):
    """
    Deletes a specific conversation and all its messages.
    (This is a DRF API view)
    """
    try:
        conversation = get_object_or_404(
            Conversation, 
            id=conversation_id, 
            user=request.user
        )
        
        conversation.delete()
        
        return Response(status=status.HTTP_204_NO_CONTENT)
        
    except Exception as e:
        logger.error(f"Error deleting conversation {conversation_id}: {e}")
        return Response(
            {'error': 'An error occurred while deleting the conversation.'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )