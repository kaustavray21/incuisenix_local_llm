import os
import shutil
import logging
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework import status

from ..models import Course, Enrollment, Video
from ..serializers import CourseSerializer
from ..transcript_service import generate_transcript_for_video, sanitize_filename
from ..rag.vector_store import create_vector_store_for_video

logger = logging.getLogger(__name__)


@api_view(['POST'])
def create_course_view(request):
    if request.method == 'POST':
        serializer = CourseSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['DELETE'])
def delete_course_view(request, course_id):
    try:
        course = get_object_or_404(Course, id=course_id)
        
        course_dir_safe = sanitize_filename(course.title)
        transcript_dir_path = os.path.join(settings.MEDIA_ROOT, 'transcripts', course_dir_safe)

        if os.path.isdir(transcript_dir_path):
            shutil.rmtree(transcript_dir_path)
            
        course.delete()
        
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@login_required
@require_POST
def enroll_view(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    Enrollment.objects.get_or_create(user=request.user, course=course)
    return redirect('dashboard')


@login_required
def roadmap_view(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    if not Enrollment.objects.filter(user=request.user, course=course).exists():
        return JsonResponse({'error': 'You are not enrolled in this course.'}, status=403)

    course_data = {
        'title': course.title,
        'description': course.description,
    }
    return JsonResponse(course_data)


@api_view(['POST'])
def generate_course_transcripts_view(request, course_id):
    try:
        course = get_object_or_404(Course, id=course_id)
    except Course.DoesNotExist:
        return Response({'status': 'Error', 'log': ['Course not found']}, status=status.HTTP_404_NOT_FOUND)

    videos = Video.objects.filter(course=course)
    if not videos.exists():
        return Response({'status': 'Skipped', 'log': ['No videos found for this course']}, status=status.HTTP_200_OK)

    force = request.data.get('force', False)
    all_logs = {}
    
    for video in videos:
        status_msg, log = generate_transcript_for_video(video, force_generation=force)
        all_logs[f"Video ID {video.id}: {video.title}"] = {
            'status': status_msg,
            'log': log
        }

    return Response({'status': 'Completed', 'results': all_logs}, status=status.HTTP_200_OK)


@api_view(['POST'])
def generate_course_indexes_view(request, course_id):
    try:
        course = get_object_or_404(Course, id=course_id)
    except Course.DoesNotExist:
        return Response({'status': 'Error', 'log': ['Course not found']}, status=status.HTTP_404_NOT_FOUND)

    videos = Video.objects.filter(course=course)
    if not videos.exists():
        return Response({'status': 'Skipped', 'log': ['No videos found for this course']}, status=status.HTTP_200_OK)

    force_creation = request.data.get('force', False)
    all_logs = {}

    for video in videos:
        video_id_to_use = video.youtube_id or video.vimeo_id
        if not video_id_to_use:
            log_msg = f"Video '{video.title}' (DB ID: {video.id}) has no platform ID. Skipping."
            logger.warning(log_msg)
            all_logs[f"Video ID {video.id}"] = {'status': 'Skipped', 'log': log_msg}
            continue

        try:
            index_path = os.path.join(settings.FAISS_INDEX_ROOT, 'transcripts', video_id_to_use)
            faiss_file_path = os.path.join(index_path, "index.faiss")

            if os.path.exists(faiss_file_path) and not force_creation:
                log_msg = f"Index for '{video.title}' already exists. Skipping."
                logger.info(log_msg)
                all_logs[video_id_to_use] = {'status': 'Skipped', 'log': log_msg}
                continue

            create_vector_store_for_video(video_id_to_use)
            log_msg = f"Successfully created index for '{video.title}'."
            logger.info(log_msg)
            all_logs[video_id_to_use] = {'status': 'Created', 'log': log_msg}

        except Exception as e:
            log_msg = f"Error creating index for '{video.title}': {e}"
            logger.error(log_msg, exc_info=True)
            all_logs[video_id_to_use] = {'status': 'Error', 'log': str(e)}

    return Response({'status': 'Completed', 'results': all_logs}, status=status.HTTP_200_OK)