import logging
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import Video
from ..rag.utils import query_router

logger = logging.getLogger(__name__)

class AssistantAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        query = request.data.get('query')
        youtube_video_id = request.data.get('video_id')
        timestamp = float(request.data.get('timestamp', 0))

        if not query or not youtube_video_id:
            return Response(
                {'error': 'Query and video_id are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            video = get_object_or_404(Video, youtube_id=youtube_video_id)
            user_id = request.user.id 
            chat_history = ""
            
            answer = query_router(
                query=query,
                video_id=youtube_video_id,
                timestamp=timestamp,
                chat_history=chat_history,
                user_id=user_id
            )

            return Response({
                'answer': answer,
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"An error occurred in AssistantAPIView: {e}", exc_info=True)
            return Response(
                {'error': 'An error occurred while processing your request.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )