from django.urls import path
from .views import api_assistant, api_course, api_transcript

urlpatterns = [
    path('roadmap/<int:course_id>/', api_course.roadmap_view, name='roadmap'),
    path('enroll/<int:course_id>/', api_course.enroll_view, name='enroll'),
    
    path('assistant/', api_assistant.AssistantAPIView.as_view(), name='assistant_api'),

    path('transcripts/<str:video_id>/', api_transcript.get_transcript_view, name='api_get_transcripts'),
    
    path('courses/add/', api_course.create_course_view, name='add_course'),
    path('courses/delete/<int:course_id>/', api_course.delete_course_view, name='delete_course'),
    
    path('v1/course/<int:course_id>/add-videos/', 
         api_course.add_videos_to_course_view, 
         name='api_add_videos'),
    
    path('v1/transcript/queue/', 
         api_transcript.TranscriptQueueView.as_view(), 
         name='api_queue_transcript'),
         
    path('v1/index/queue/', 
         api_transcript.IndexQueueView.as_view(), 
         name='api_queue_index'),
]