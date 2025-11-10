from django.urls import path

from .views import auth_views, content_views,api_note, api_conversation

urlpatterns = [
    path('', content_views.home, name='home'),
    path('dashboard/', content_views.dashboard_view, name='dashboard'),
    path('courses/', content_views.courses_list_view, name='courses_list'),
    path('courses/<int:course_id>/', content_views.video_player_view, name='video_player'),

    path('signup/', auth_views.signup_view, name='signup'),
    path('login/', auth_views.login_view, name='login'),
    path('logout/', auth_views.logout_view, name='logout'),
    
    path('api/notes/add/<str:video_id>/', api_note.add_note_view, name='add_note'),
    path('api/notes/edit/<int:note_id>/', api_note.edit_note_view, name='edit_note'),
    path('api/notes/delete/<int:note_id>/', api_note.delete_note_view, name='delete_note'),
    
    path('api/conversations/', api_conversation.get_conversation_list, name='get_conversation_list'),
    path('api/conversations/<int:conversation_id>/messages/', api_conversation.get_conversation_messages, name='get_conversation_messages'),
    
    path('api/conversations/delete/<int:conversation_id>/', api_conversation.delete_conversation, name='delete_conversation'),
    path('api/get-vimeo-links/<int:video_id>/', content_views.get_vimeo_links_api, name='api_get_vimeo_links'),
]
handler4_04 = 'core.views.content_views.custom_404_view'