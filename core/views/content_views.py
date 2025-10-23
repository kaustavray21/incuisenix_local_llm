# core/views/content_views.py

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from ..models import Enrollment, Course, Video, Note # Use relative imports
from ..forms import NoteForm # Use relative imports

def home(request):
    return render(request, 'core/home.html')

def about_view(request):
    # Assuming you have a template for this view
    # If not, you can create 'core/about.html'
    return render(request, 'core/about.html')

@login_required
def dashboard_view(request):
    user = request.user
    
    # --- Filter Logic ---
    
    # Get filter parameters from the GET request
    sort_by = request.GET.get('sort_by', '-created_at') # Default to newest
    course_id = request.GET.get('course_id')
    video_id = request.GET.get('video_id')

    # Start with all notes for the user
    notes_query = Note.objects.filter(user=user).select_related('video', 'course')

    # Apply filters if they exist
    if course_id:
        notes_query = notes_query.filter(course_id=course_id)
    if video_id:
        notes_query = notes_query.filter(video_id=video_id)

    # Apply sorting
    if sort_by in ['-created_at', 'created_at']: # Whitelist sort options
        notes_query = notes_query.order_by(sort_by)
    else:
        notes_query = notes_query.order_by('-created_at') # Default fallback
        
    # --- Data for Dropdowns ---
    
    # Get all enrolled courses (for the sidebar)
    enrolled_courses = Enrollment.objects.filter(user=user).select_related('course')
    
    # Get only courses where the user has at least one note
    courses_with_notes = Course.objects.filter(
        id__in=Note.objects.filter(user=user).values_list('course_id', flat=True).distinct()
    ).order_by('title')
    
    # Get only videos where the user has at least one note
    videos_with_notes = Video.objects.filter(
        id__in=Note.objects.filter(user=user).values_list('video_id', flat=True).distinct()
    ).order_by('title')
    
    # --- Pagination ---
    paginator = Paginator(notes_query, 6) # Paginate the *filtered* notes
    page_number = request.GET.get('page')
    notes_page_obj = paginator.get_page(page_number)

    context = {
        'enrolled_courses': [enrollment.course for enrollment in enrolled_courses],
        'notes_page_obj': notes_page_obj,
        
        # Pass filter options to the template
        'filter_courses': courses_with_notes,
        'filter_videos': videos_with_notes,
        
        # Pass selected values back to the template
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

    notes = Note.objects.filter(user=request.user, video=video_obj) if video_obj else []
    form = NoteForm()

    context = {
        'course': course,
        'all_videos': all_videos,
        'video': video_obj,
        'notes': notes,
        'form': form,
    }
    return render(request, 'core/video_player.html', context)

def custom_404_view(request, exception=None):
    return render(request, 'core/404.html', {}, status=404)