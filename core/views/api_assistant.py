import logging
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import Video, Conversation, ConversationMessage
from ..rag.utils import query_router

logger = logging.getLogger(__name__)

class AssistantAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        query = request.data.get('query')
        youtube_video_id = request.data.get('video_id')
        
        timestamp_data = request.data.get('timestamp')
        try:
            timestamp = float(timestamp_data or 0.0)
        except (TypeError, ValueError):
            timestamp = 0.0
        
        conversation_id = request.data.get('conversation_id')
        force_new = request.data.get('force_new', False)

        if not query or not youtube_video_id:
            return Response(
                {'error': 'Query and video_id are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        is_dummy_start_query = (force_new and query == "Start")

        try:
            video = get_object_or_404(Video, youtube_id=youtube_video_id)
            user = request.user
            
            conversation = None
            chat_history_messages = []
            
            if conversation_id and not force_new:
                try:
                    conversation = Conversation.objects.get(id=conversation_id, user=user)
                except Conversation.DoesNotExist:
                    conversation = None
            
            if not conversation and not force_new:
                conversation = Conversation.objects.filter(user=user, video=video).order_by('-created_at').first()

            if conversation:
                messages = conversation.messages.all().order_by('timestamp')
                for msg in messages:
                    chat_history_messages.append(f"User: {msg.query}")
                    chat_history_messages.append(f"Assistant: {msg.answer}")
            
            if not conversation:
                initial_title = "New Conversation"
                if not is_dummy_start_query:
                    initial_title = query[:255]

                conversation = Conversation.objects.create(
                    user=user,
                    video=video,
                    course=video.course,
                    title=initial_title
                )
                logger.info(f"Created new conversation {conversation.id} with title: {initial_title}")

            chat_history = "\n".join(chat_history_messages)

            if not is_dummy_start_query:
                answer = query_router(
                    query=query,
                    video_id=youtube_video_id,
                    timestamp=timestamp,
                    chat_history=chat_history, 
                    user_id=user.id
                )

                ConversationMessage.objects.create(
                    conversation=conversation,
                    query=query,
                    answer=answer
                )

                if conversation.title == "New Conversation":
                    conversation.title = query[:255] 
                    conversation.save(update_fields=['title']) 
                    logger.info(f"Updated conversation {conversation.id} title to: {conversation.title}")

            else:
                answer = "Starting new chat..." 

            return Response({
                'answer': answer,
                'conversation_id': conversation.id 
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"An error occurred in AssistantAPIView: {e}", exc_info=True)
            return Response(
                {'error': 'An error occurred while processing your request.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )