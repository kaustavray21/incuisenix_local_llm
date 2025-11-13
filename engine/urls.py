from django.urls import path
from .views import api_assistant, api_course, api_transcript

urlpatterns = [
    path('api/roadmap/<int:course_id>/', api_course.roadmap_view, name='roadmap'),
    path('api/enroll/<int:course_id>/', api_course.enroll_view, name='enroll'),
    
    path('api/assistant/', api_assistant.AssistantAPIView.as_view(), name='assistant_api'),
    path( 'api/public/assistant/', api_assistant.PublicAssistantAPIView.as_view(), name='public_assiatant_api'),

    path('api/transcripts/<str:video_id>/', api_transcript.get_transcript_view, name='api_get_transcripts'),
    
    path('api/courses/add/', api_course.create_course_view, name='add_course'),
    path('api/courses/delete/<int:course_id>/', api_course.delete_course_view, name='delete_course'),
    
    path('api/v1/course/<int:course_id>/add-videos/', api_course.add_videos_to_course_view, name='api_add_videos'),
    
    path('api/v1/transcript/queue/', api_transcript.TranscriptQueueView.as_view(), name='api_queue_transcript'),
         
    path('api/v1/index/queue/', api_transcript.IndexQueueView.as_view(), name='api_queue_index'),
]