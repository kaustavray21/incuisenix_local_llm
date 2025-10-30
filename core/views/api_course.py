from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework import status

from ..models import Course, Enrollment, Video # <-- ADDED Video
from ..serializers import CourseSerializer
from ..transcript_service import generate_transcript_for_video # <-- ADDED THIS


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


# --- NEW LOGIC ADDED BELOW ---

@api_view(['POST'])
def generate_course_transcripts_view(request, course_id):
    """
    Triggers transcript generation for ALL videos in a course.
    WARNING: THIS WILL TIME OUT on any real course.
    Use the management command for batch jobs.
    """
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