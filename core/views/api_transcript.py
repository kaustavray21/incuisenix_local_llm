import logging
import os
import pandas as pd
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, Http404
from ..models import Transcript, Video
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from ..transcript_service import generate_transcript_for_video, sanitize_filename

logger = logging.getLogger(__name__)


@login_required
def get_transcript_view(request, video_id):
    """
    Fetches transcript lines.
    
    Tries to fetch from the fast database Transcript model first.
    If no DB entries exist, it falls back to reading the generated CSV file.
    """
    logger.info(f"API Request: Fetching transcript for video_id string: '{video_id}'")
    try:
        video = get_object_or_404(
            Video,
            Q(youtube_id=video_id) | Q(vimeo_id=video_id)
        )
        logger.info(f"Found video object with DB ID: {video.pk} for platform ID: '{video_id}'")

        # --- 1. Try to get from Database first (it's faster) ---
        transcripts = Transcript.objects.filter(video=video).order_by('start')

        if transcripts.exists():
            data = [{'start': t.start, 'content': t.content} for t in transcripts]
            logger.info(f"Returning {len(data)} transcript lines from DB for video {video.pk} ('{video_id}')")
            return JsonResponse(data, safe=False)

        # --- 2. Fallback: If not in DB, try to read the CSV file ---
        logger.warning(f"No transcript lines in DB for video {video.pk}. Checking for CSV fallback.")
        
        platform_id = video.youtube_id or video.vimeo_id
        course_dir_safe = sanitize_filename(video.course.title)
        transcript_path = os.path.join(settings.MEDIA_ROOT, 'transcripts', course_dir_safe, f"{platform_id}.csv")

        if os.path.exists(transcript_path):
            try:
                df = pd.read_csv(transcript_path)
                # Ensure columns are correct, fill NaNs just in case
                df = df.where(pd.notnull(df), None)
                data = df.to_dict('records')
                logger.info(f"Returning {len(data)} lines from CSV file: {transcript_path}")
                return JsonResponse(data, safe=False)
            except Exception as e:
                logger.error(f"Failed to read CSV file {transcript_path}: {e}")
                return JsonResponse({'error': f"Found CSV but could not read it: {e}"}, status=500)

        # --- 3. If neither exists ---
        logger.warning(f"No DB entries and no CSV file found for video {video.pk} ('{video_id}')")
        return JsonResponse([], safe=False)

    except Http404:
        logger.error(f"Video with youtube_id or vimeo_id '{video_id}' not found.")
        return JsonResponse({'error': f"Video with ID '{video_id}' not found."}, status=404)

    except Exception as e:
        logger.error(f"Error fetching transcript for video platform ID '{video_id}': {e}", exc_info=True)
        return JsonResponse({'error': 'An internal server error occurred.'}, status=500)


@api_view(['POST'])
def generate_transcript_view(request, video_id):
    """
    Triggers the generation of a transcript CSV file for a single video.
    """
    try:
        # Note: This API uses the *database* ID (pk), not the vimeo/youtube ID
        video = get_object_or_404(Video, id=video_id)
    except Exception as e:
        return Response({'status': 'Error', 'log': [f"Failed to find video with database ID: {video_id}"]}, status=status.HTTP_404_NOT_FOUND)
        
    force = request.data.get('force', False)
    
    try:
        status_msg, log = generate_transcript_for_video(video, force_generation=force)
        
        if "Generated" in status_msg:
            return Response({'status': status_msg, 'log': log}, status=status.HTTP_201_CREATED)
        elif "Skipped" in status_msg:
            return Response({'status': status_msg, 'log': log}, status=status.HTTP_200_OK)
        else:
            return Response({'status': status_msg, 'log': log}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    except Exception as e:
        return Response({'status': 'Failed', 'log': [f'An unexpected error occurred: {str(e)}']}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)