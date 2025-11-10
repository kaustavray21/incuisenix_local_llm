import logging
from django.shortcuts import get_object_or_404
from django.db.models import Q 
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Video, Conversation, ConversationMessage
from engine.rag.utils import query_router

logger = logging.getLogger(__name__)

class AssistantAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        query = request.data.get('query')
        video_id_from_request = request.data.get('video_id')

        logger.info(f"Received video_id from frontend: '{video_id_from_request}' (Type: {type(video_id_from_request)})")

        timestamp_data = request.data.get('timestamp')
        try:
            timestamp = float(timestamp_data or 0.0)
        except (TypeError, ValueError):
            timestamp = 0.0

        conversation_id = request.data.get('conversation_id')
        force_new = request.data.get('force_new', False)

        if not query or not video_id_from_request:
            logger.error(f"Missing query ('{query}') or video_id ('{video_id_from_request}') in request.")
            return Response(
                {'error': 'Query and video_id are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        is_dummy_start_query = (force_new and query == "Start")

        try:
            user = request.user

            logger.info(f"Attempting to find Video with youtube_id OR vimeo_id = '{video_id_from_request}'")
            video = get_object_or_404(
                Video,
                Q(youtube_id=video_id_from_request) | Q(vimeo_id=video_id_from_request)
            )
            logger.info(f"Successfully found video: {video.title} (DB ID: {video.pk})")

            conversation = None
            chat_history_messages = []

            if conversation_id and not force_new:
                try:
                    conversation = Conversation.objects.get(id=conversation_id, user=user, video=video)
                except Conversation.DoesNotExist:
                    logger.warning(f"Conversation ID {conversation_id} not found for user {user.id}. Will create new or find latest.")
                    conversation = None

            if not conversation and not force_new:
                conversation = Conversation.objects.filter(user=user, video=video).order_by('-created_at').first()

            if conversation:
                logger.info(f"Using existing conversation {conversation.id} for video {video_id_from_request}")
                messages = conversation.messages.all().order_by('timestamp')
                for msg in messages:
                    chat_history_messages.append(f"User: {msg.query}")
                    if msg.answer:
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
                logger.info(f"Created new conversation {conversation.id} for video {video_id_from_request} with title: {initial_title}")

            chat_history = "\n".join(chat_history_messages)

            if not is_dummy_start_query:
                logger.debug(f"Calling query_router for query: '{query}' on video {video_id_from_request}")
                answer = query_router(
                    query=query,
                    video_id=video_id_from_request,
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

        except Video.DoesNotExist:
             logger.error(f"Video with youtube_id OR vimeo_id '{video_id_from_request}' not found in database.", exc_info=False)
             return Response(
                 {'error': f'Video with ID {video_id_from_request} not found.'},
                 status=status.HTTP_44_NOT_FOUND
             )
        except Exception as e:
            logger.error(f"An error occurred in AssistantAPIView: {e}", exc_info=True)
            error_context = {'error': 'An error occurred processing your request.'}
            if 'video_id_from_request' in locals():
                 error_context['video_id'] = video_id_from_request
            return Response(
                error_context,
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )