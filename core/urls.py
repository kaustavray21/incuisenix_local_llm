# core/urls.py

from django.urls import path
from .views import auth_views, content_views, api_views

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
    path('roadmap/<int:course_id>/', api_views.roadmap_view, name='roadmap'),
    
    # --- API Endpoint URLs ---
    path('api/enroll/<int:course_id>/', api_views.enroll_view, name='enroll'),
    
    # Note API URLs
    path('api/notes/add/<int:video_id>/', api_views.add_note_view, name='add_note'),
    path('api/notes/edit/<int:note_id>/', api_views.edit_note_view, name='edit_note'),
    path('api/notes/delete/<int:note_id>/', api_views.delete_note_view, name='delete_note'),
    
    # AI Assistant API URL
    path('api/assistant/', api_views.AssistantAPIView.as_view(), name='assistant_api'),

    # Transcript API URL
    path('api/transcripts/<int:video_id>/', api_views.get_transcript_view, name='api_get_transcripts'),

    # Conversation History API URLs
    path('api/assistant/conversations/', api_views.ConversationListView.as_view(), name='conversation_list'),
    path('api/assistant/conversations/<int:conversation_id>/', api_views.ConversationDetailView.as_view(), name='conversation_detail'),
]

# Corrected handler for 404 Not Found errors
handler404 = 'core.views.custom_404_view'