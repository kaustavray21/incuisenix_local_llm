from django.urls import path
from .views import auth_views, content_views,api_course, api_note, api_assistant, api_transcript, api_conversation

urlpatterns = [
    path('', content_views.home, name='home'),
    path('dashboard/', content_views.dashboard_view, name='dashboard'),
    path('courses/', content_views.courses_list_view, name='courses_list'),
    path('courses/<int:course_id>/', content_views.video_player_view, name='video_player'),

    path('signup/', auth_views.signup_view, name='signup'),
    path('login/', auth_views.login_view, name='login'),
    path('logout/', auth_views.logout_view, name='logout'),
    
    path('roadmap/<int:course_id>/', api_course.roadmap_view, name='roadmap'),
    
    path('api/enroll/<int:course_id>/', api_course.enroll_view, name='enroll'),
    
    path('api/notes/add/<str:video_id>/', api_note.add_note_view, name='add_note'),
    path('api/notes/edit/<int:note_id>/', api_note.edit_note_view, name='edit_note'),
    path('api/notes/delete/<int:note_id>/', api_note.delete_note_view, name='delete_note'),
    
    path('api/assistant/', api_assistant.AssistantAPIView.as_view(), name='assistant_api'),

    path('api/transcripts/<str:video_id>/', api_transcript.get_transcript_view, name='api_get_transcripts'),
    
    path('api/conversations/', api_conversation.get_conversation_list, name='get_conversation_list'),
    path('api/conversations/<int:conversation_id>/messages/', api_conversation.get_conversation_messages, name='get_conversation_messages'),
    
    path('api/conversations/delete/<int:conversation_id>/', api_conversation.delete_conversation, name='delete_conversation'),
    path('api/get-vimeo-links/<int:video_id>/', content_views.get_vimeo_links_api, name='api_get_vimeo_links'),
    
    
    path('api/courses/add/', api_course.create_course_view, name='add_course'),
    
    path('api/courses/delete/<int:course_id>/', api_course.delete_course_view, name='delete_course'),
    
    path('api/v1/course/<int:course_id>/add-videos/', 
         api_course.add_videos_to_course_view, 
         name='api_add_videos'),
    
    path('api/v1/transcript/queue/', 
         api_transcript.TranscriptQueueView.as_view(), 
         name='api_queue_transcript'),
         
    path('api/v1/index/queue/', 
         api_transcript.IndexQueueView.as_view(), 
         name='api_queue_index'),
]
handler4_04 = 'core.views.content_views.custom_404_view'
