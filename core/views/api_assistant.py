import logging
from django.shortcuts import get_object_or_404
from django.db.models import Q # Import Q objects
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import Video, Conversation, ConversationMessage
from ..rag.utils import query_router # Assuming query_router is in ../rag/utils.py

logger = logging.getLogger(__name__)

class AssistantAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        query = request.data.get('query')
        video_id_from_request = request.data.get('video_id')

        # --- DEBUG LINE ADDED ---
        logger.info(f"Received video_id from frontend: '{video_id_from_request}' (Type: {type(video_id_from_request)})")
        # --- END OF DEBUG LINE ---

        timestamp_data = request.data.get('timestamp')
        try:
            timestamp = float(timestamp_data or 0.0)
        except (TypeError, ValueError):
            timestamp = 0.0

        conversation_id = request.data.get('conversation_id')
        force_new = request.data.get('force_new', False)

        if not query or not video_id_from_request:
            logger.error(f"Missing query ('{query}') or video_id ('{video_id_from_request}') in request.") # Added log
            return Response(
                {'error': 'Query and video_id are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Handle case where frontend might send "Start" to force a new chat
        is_dummy_start_query = (force_new and query == "Start")

        try:
            user = request.user

            # Search using Q objects for either YouTube or Vimeo ID
            logger.info(f"Attempting to find Video with youtube_id OR vimeo_id = '{video_id_from_request}'")
            video = get_object_or_404(
                Video,
                Q(youtube_id=video_id_from_request) | Q(vimeo_id=video_id_from_request)
            )
            logger.info(f"Successfully found video: {video.title} (DB ID: {video.pk})")

            conversation = None
            chat_history_messages = []

            # Try to find existing conversation by ID if provided and not forcing new
            if conversation_id and not force_new:
                try:
                    conversation = Conversation.objects.get(id=conversation_id, user=user, video=video) # Ensure video matches too
                except Conversation.DoesNotExist:
                    logger.warning(f"Conversation ID {conversation_id} not found for user {user.id}. Will create new or find latest.")
                    conversation = None # Explicitly set to None

            # If still no conversation, find the latest one for this user/video
            if not conversation and not force_new:
                conversation = Conversation.objects.filter(user=user, video=video).order_by('-created_at').first()

            # Load history if a conversation was found
            if conversation:
                logger.info(f"Using existing conversation {conversation.id} for video {video_id_from_request}")
                messages = conversation.messages.all().order_by('timestamp') # Assuming timestamp field exists on ConversationMessage
                for msg in messages:
                    chat_history_messages.append(f"User: {msg.query}")
                    if msg.answer: # Avoid adding None if answer isn't ready
                       chat_history_messages.append(f"Assistant: {msg.answer}")

            # Create a new conversation if none exists or if forced
            if not conversation:
                initial_title = "New Conversation"
                # Only use the actual query as title if it's not the dummy "Start"
                if not is_dummy_start_query:
                    initial_title = query[:255] # Use first 255 chars of the query as title

                conversation = Conversation.objects.create(
                    user=user,
                    video=video,
                    course=video.course,
                    title=initial_title
                )
                logger.info(f"Created new conversation {conversation.id} for video {video_id_from_request} with title: {initial_title}")

            chat_history = "\n".join(chat_history_messages)

            # --- RAG Query ---
            # Don't call RAG if it's just the dummy query to start a new chat
            if not is_dummy_start_query:
                logger.debug(f"Calling query_router for query: '{query}' on video {video_id_from_request}")
                answer = query_router(
                    query=query,
                    # Pass the actual video_id (which could be YT or Vimeo)
                    video_id=video_id_from_request,
                    timestamp=timestamp,
                    chat_history=chat_history,
                    user_id=user.id
                )

                # Save the new message pair
                ConversationMessage.objects.create(
                    conversation=conversation,
                    query=query,
                    answer=answer
                )

                # Update conversation title from "New Conversation" if needed
                if conversation.title == "New Conversation": # Removed check for initial_title as it might not be relevant here
                    conversation.title = query[:255]
                    conversation.save(update_fields=['title'])
                    logger.info(f"Updated conversation {conversation.id} title to: {conversation.title}")
            else:
                # Response for the dummy "Start" query
                answer = "Starting new chat..."

            return Response({
                'answer': answer,
                'conversation_id': conversation.id
            }, status=status.HTTP_200_OK)

        except Video.DoesNotExist: # Catch if get_object_or_404 fails
             logger.error(f"Video with youtube_id OR vimeo_id '{video_id_from_request}' not found in database.", exc_info=False) # Simplified log
             return Response(
                 {'error': f'Video with ID {video_id_from_request} not found.'},
                 status=status.HTTP_404_NOT_FOUND
             )
        except Exception as e:
            logger.error(f"An error occurred in AssistantAPIView: {e}", exc_info=True)
            # Add video_id to error context if available
            error_context = {'error': 'An error occurred processing your request.'}
            if 'video_id_from_request' in locals():
                 error_context['video_id'] = video_id_from_request
            return Response(
                error_context,
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )