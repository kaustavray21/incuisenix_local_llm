# core/urls.py

from django.urls import path
from .views import auth_views, content_views,api_course, api_note, api_assistant, api_transcript, api_conversation

urlpatterns = [
    # --- Content Page URLs ---
    path('', content_views.home, name='home'),
    path('dashboard/', content_views.dashboard_view, name='dashboard'),
    path('courses/', content_views.courses_list_view, name='courses_list'),
    path('courses/<int:course_id>/', content_views.video_player_view, name='video_player'),

    # --- Authentication URLs ---
    path('signup/', auth_views.signup_view, name='signup'),
    path('login/', auth_views.login_view, name='login'),
    path('logout/', auth_views.logout_view, name='logout'),
    
    # --- Standalone Roadmap URL ---
    path('roadmap/<int:course_id>/', api_course.roadmap_view, name='roadmap'),
    
    # --- API Endpoint URLs ---
    path('api/enroll/<int:course_id>/', api_course.enroll_view, name='enroll'),
    
    # Note API URLs
    path('api/notes/add/<int:video_id>/', api_note.add_note_view, name='add_note'),
    path('api/notes/edit/<int:note_id>/', api_note.edit_note_view, name='edit_note'),
    path('api/notes/delete/<int:note_id>/', api_note.delete_note_view, name='delete_note'),
    
    # AI Assistant API URL
    path('api/assistant/', api_assistant.AssistantAPIView.as_view(), name='assistant_api'),

    # Transcript API URL
    path('api/transcripts/<int:video_id>/', api_transcript.get_transcript_view, name='api_get_transcripts'),

    # --- NEW: Conversation History API URLs ---
    path('api/conversations/', api_conversation.get_conversation_list, name='get_conversation_list'),
    path('api/conversations/<int:conversation_id>/messages/', api_conversation.get_conversation_messages, name='get_conversation_messages'),
]
handler404 = 'core.views.content_views.custom_404_view'