import os
import shutil
import logging
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework import status

from ..models import Course, Enrollment, Video
from ..serializers import CourseSerializer, VideoReadOnlySerializer
from ..transcript_service import sanitize_filename

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

@api_view(['POST'])
def add_videos_to_course_view(request, course_id):
    try:
        course = get_object_or_404(Course, id=course_id)
    except Course.DoesNotExist:
        return Response({"error": "Course not found."}, status=status.HTTP_404_NOT_FOUND)

    video_list = request.data
    if not isinstance(video_list, list):
        return Response({"error": "Expected a list of video objects."}, status=status.HTTP_400_BAD_REQUEST)

    created_videos = []
    errors = []

    for video_data in video_list:
        title = video_data.get('title')
        vimeo_id = video_data.get('vimeo_id')
        youtube_id = video_data.get('youtube_id')
        
        if not title:
            errors.append({"video_data": video_data, "error": "Missing 'title'."})
            continue
            
        if not vimeo_id and not youtube_id:
            errors.append({"video_data": video_data, "error": "Missing 'vimeo_id' or 'youtube_id'."})
            continue

        query = Q()
        if vimeo_id:
            query |= Q(vimeo_id=vimeo_id)
        if youtube_id:
            query |= Q(youtube_id=youtube_id)

        if Video.objects.filter(query).exists():
            errors.append({"video_data": video_data, "error": "Video with this vimeo_id or youtube_id already exists."})
            continue
            
        try:
            video = Video.objects.create(
                course=course,
                title=title,
                video_url=video_data.get('video_url', ''),
                vimeo_id=vimeo_id,
                youtube_id=youtube_id
            )
            created_videos.append(video)
        except Exception as e:
            errors.append({"video_data": video_data, "error": str(e)})

    created_serializer = VideoReadOnlySerializer(created_videos, many=True)
    return Response({
        "message": f"Successfully created {len(created_videos)} videos.",
        "created": created_serializer.data,
        "errors": errors
    }, status=status.HTTP_201_CREATED)


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