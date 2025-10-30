import requests
import os
import logging
from django.conf import settings
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from ..models import Enrollment, Course, Video, Note
from ..forms import NoteForm
from django.core.cache import cache

def home(request):
    return render(request, 'core/home.html')

@login_required
def dashboard_view(request):
    user = request.user
    
    sort_by = request.GET.get('sort_by', '-created_at')
    course_id = request.GET.get('course_id')
    video_id = request.GET.get('video_id')

    notes_query = Note.objects.filter(user=user).select_related('video', 'course')

    if course_id:
        notes_query = notes_query.filter(course_id=course_id)
    if video_id:
        notes_query = notes_query.filter(video_id=video_id)

    if sort_by in ['-created_at', 'created_at']:
        notes_query = notes_query.order_by(sort_by)
    else:
        notes_query = notes_query.order_by('-created_at')
        
    enrolled_courses = Enrollment.objects.filter(user=user).select_related('course')
    
    courses_with_notes = Course.objects.filter(
        id__in=Note.objects.filter(user=user).values_list('course_id', flat=True).distinct()
    ).order_by('title')
    
    videos_with_notes = Video.objects.filter(
        id__in=Note.objects.filter(user=user).values_list('video_id', flat=True).distinct()
    ).order_by('title')
    
    paginator = Paginator(notes_query, 6)
    page_number = request.GET.get('page')
    notes_page_obj = paginator.get_page(page_number)

    context = {
        'enrolled_courses': [enrollment.course for enrollment in enrolled_courses],
        'notes_page_obj': notes_page_obj,
        'filter_courses': courses_with_notes,
        'filter_videos': videos_with_notes,
        'current_filters': {
            'sort_by': sort_by,
            'course_id': int(course_id) if course_id else None,
            'video_id': int(video_id) if video_id else None,
        }
    }
    return render(request, 'core/dashboard.html', context)

@login_required
def courses_list_view(request):
    enrolled_course_ids = Enrollment.objects.filter(user=request.user).values_list('course__id', flat=True)
    all_courses = Course.objects.all()
    context = {
        'all_courses': all_courses,
        'enrolled_course_ids': set(enrolled_course_ids),
    }
    return render(request, 'core/courses_list.html', context)


@login_required
def video_player_view(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    
    if not Enrollment.objects.filter(user=request.user, course=course).exists():
        return redirect('dashboard')
    
    all_videos = course.videos.all().order_by('id')
    video_obj = None 
    
    video_id_from_url = request.GET.get('vid')
    if video_id_from_url:
        video_obj = get_object_or_404(Video, id=video_id_from_url, course=course)
    elif all_videos.exists():
        video_obj = all_videos.first()

    video_provider = None
    error_message = None

    if video_obj and video_obj.vimeo_id:
        video_provider = 'vimeo'
    elif video_obj and video_obj.youtube_id:
        video_provider = 'youtube'
    elif video_obj:
        error_message = "This video object does not have a valid Vimeo or YouTube ID."
    else:
        error_message = "No video selected or available in this course."

    notes = Note.objects.filter(user=request.user, video=video_obj) if video_obj else []
    form = NoteForm()

    context = {
        'course': course,
        'all_videos': all_videos,
        'video': video_obj,
        'notes': notes,
        'form': form,
        'video_links': [],
        'error_message': error_message,
        'video_provider': video_provider,
    }
    return render(request, 'core/video_player.html', context)


@login_required
def get_vimeo_links_api(request, video_id):
    video = get_object_or_404(Video, id=video_id, vimeo_id__isnull=False)
    
    if not Enrollment.objects.filter(user=request.user, course=video.course).exists():
        return JsonResponse({'error': 'Not enrolled'}, status=403)

    cache_key = f"vimeo_links_{video.vimeo_id}"
    cached_links = cache.get(cache_key)

    if cached_links:
        return JsonResponse({'links': cached_links})

    video_links = []
    
    try:
        api_key = os.getenv('VIMEO_TOKEN')
        
        if not api_key:
            raise ValueError("VIMEO_TOKEN is not set in environment variables.")
            
        api_url = f"https://api.vimeo.com/videos/{video.vimeo_id}"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/vnd.vimeo.*+json;version=3.4"
        }
        
        response = requests.get(api_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        for file_info in data.get('files', []):
            if file_info.get('quality') in ('hd', 'sd') and file_info.get('type') == 'video/mp4':
                video_links.append({
                    'url': file_info.get('link'),
                    'quality': file_info.get('height'),
                })
        
        video_links.sort(key=lambda x: x.get('quality', 0), reverse=True)

        if not video_links and data.get('files'):
            first_file = data['files'][0]
            video_links.append({
                    'url': first_file.get('link'),
                    'quality': first_file.get('height') or 'auto',
            })

        if not video_links:
            return JsonResponse({'error': 'No compatible video files were found.'}, status=404)

        cache.set(cache_key, video_links, timeout=7200)

        return JsonResponse({'links': video_links})

    except requests.exceptions.HTTPError as http_err:
        logging.error(f"Vimeo API HTTPError for video {video.vimeo_id}: {http_err}")
        return JsonResponse({'error': f'Vimeo API Error: {http_err.response.status_code}'}, status=502)
    except requests.exceptions.RequestException as req_err:
        logging.error(f"Vimeo API RequestException for video {video.vimeo_id}: {req_err}")
        return JsonResponse({'error': 'Network Error: Could not connect to Vimeo.'}, status=504)
    except Exception as e:
        logging.error(f"Unexpected error fetching Vimeo video {video.vimeo_id}: {e}")
        return JsonResponse({'error': 'An unexpected server error occurred.'}, status=500)

def custom_404_view(request, exception=None):
    return render(request, 'core/404.html', {}, status=404)