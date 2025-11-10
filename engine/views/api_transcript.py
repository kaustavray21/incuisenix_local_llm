import logging
import os
import pandas as pd
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, Http404
from django.db import transaction

from core.models import Transcript, Video, Course
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import IsAdminUser

from engine.transcript_service import sanitize_filename
from django_q.tasks import async_task

logger = logging.getLogger(__name__)


class TranscriptQueueView(APIView):

    def post(self, request, *args, **kwargs):
        external_id = request.data.get('external_id')
        source = request.data.get('source')

        if not external_id or not source:
            return Response(
                {"error": "external_id and source are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            if source == 'vimeo':
                video = Video.objects.get(vimeo_id=external_id)
            elif source == 'youtube':
                video = Video.objects.get(youtube_id=external_id)
            else:
                return Response(
                    {"error": "Invalid source. Must be 'vimeo' or 'youtube'."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Video.DoesNotExist:
            return Response(
                {"error": f"Video not found with {source}_id: {external_id}"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            with transaction.atomic():
                video_locked = Video.objects.select_for_update().get(pk=video.pk)
                
                if video_locked.transcript_status == 'complete':
                    return Response(
                        {"message": "Transcript is already complete."},
                        status=status.HTTP_200_OK
                    )
                
                if video_locked.transcript_status == 'processing':
                    return Response(
                        {"error": "Transcript generation is already in progress."},
                        status=status.HTTP_409_CONFLICT
                    )
                
                video_locked.transcript_status = 'processing'
                video_locked.save()

            async_task('engine.tasks.task_generate_transcript', video_locked.id)
            
            logger.info(f"Queued transcript generation for video {video_locked.id}")
            return Response(
                {"message": "Transcript generation has been queued."},
                status=status.HTTP_202_ACCEPTED
            )
            
        except Exception as e:
            logger.error(f"Error queuing transcript for video {video.id}: {e}")
            video.transcript_status = 'failed'
            video.save()
            return Response(
                {"error": "An internal server error occurred while queuing the job."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class IndexQueueView(APIView):

    def post(self, request, *args, **kwargs):
        course_id = request.data.get('course_id')
        
        if not course_id:
            return Response(
                {"error": "course_id is required."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            course = Course.objects.get(id=course_id)
        except Course.DoesNotExist:
            return Response(
                {"error": f"Course not found with id: {course_id}"},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            with transaction.atomic():
                course_locked = Course.objects.select_for_update().get(pk=course.pk)
                
                if course_locked.index_status == 'complete':
                    return Response(
                        {"message": "Index is already complete."},
                        status=status.HTTP_200_OK
                    )
                
                if course_locked.index_status == 'indexing':
                    return Response(
                        {"error": "Index creation is already in progress."},
                        status=status.HTTP_409_CONFLICT
                    )
                
                course_locked.index_status = 'indexing'
                course_locked.save()

            async_task('engine.tasks.task_generate_index', course_locked.id)
            
            logger.info(f"Queued index generation for course {course_locked.id}")
            return Response(
                {"message": "Index generation has been queued."},
                status=status.HTTP_202_ACCEPTED
            )

        except Exception as e:
            logger.error(f"Error queuing index for course {course.id}: {e}")
            course.index_status = 'failed'
            course.save()
            return Response(
                {"error": "An internal server error occurred while queuing the job."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@login_required
def get_transcript_view(request, video_id):
    logger.info(f"API Request: Fetching transcript for video_id string: '{video_id}'")
    try:
        video = get_object_or_404(
            Video,
            Q(youtube_id=video_id) | Q(vimeo_id=video_id)
        )
        logger.info(f"Found video object with DB ID: {video.pk} for platform ID: '{video_id}'")

        transcripts = Transcript.objects.filter(video=video).order_by('start')

        if transcripts.exists():
            data = [{'start': t.start, 'content': t.content} for t in transcripts]
            logger.info(f"Returning {len(data)} transcript lines from DB for video {video.pk} ('{video_id}')")
            return JsonResponse(data, safe=False)

        logger.warning(f"No transcript lines in DB for video {video.pk}. Checking for CSV fallback.")
        
        platform_id = video.youtube_id or video.vimeo_id
        course_dir_safe = sanitize_filename(video.course.title)
        transcript_path = os.path.join(settings.MEDIA_ROOT, 'transcripts', course_dir_safe, f"{platform_id}.csv")

        if os.path.exists(transcript_path):
            try:
                df = pd.read_csv(transcript_path)
                df = df.where(pd.notnull(df), None)
                data = df.to_dict('records')
                logger.info(f"Returning {len(data)} lines from CSV file: {transcript_path}")
                return JsonResponse(data, safe=False)
            except Exception as e:
                logger.error(f"Failed to read CSV file {transcript_path}: {e}")
                return JsonResponse({'error': f"Found CSV but could not read it: {e}"}, status=500)

        logger.warning(f"No DB entries and no CSV file found for video {video.pk} ('{video_id}')")
        return JsonResponse([], safe=False)

    except Http404:
        logger.error(f"Video with youtube_id or vimeo_id '{video_id}' not found.")
        return JsonResponse({'error': f"Video with ID '{video_id}' not found."}, status=404)

    except Exception as e:
        logger.error(f"Error fetching transcript for video platform ID '{video_id}': {e}", exc_info=True)
        return JsonResponse({'error': 'An internal server error occurred.'}, status=500)