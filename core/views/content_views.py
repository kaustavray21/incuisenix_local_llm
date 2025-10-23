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
    enrolled_courses = Enrollment.objects.filter(user=request.user).select_related('course')
    
    # Get all notes for the user, ordered by most recent
    all_notes = Note.objects.filter(user=request.user).select_related('video', 'course').order_by('-created_at')
    
    # Paginate the notes, showing 6 per page
    paginator = Paginator(all_notes, 6) 
    page_number = request.GET.get('page')
    notes_page_obj = paginator.get_page(page_number)

    context = {
        'enrolled_courses': [enrollment.course for enrollment in enrolled_courses],
        'notes_page_obj': notes_page_obj
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