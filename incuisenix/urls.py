from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('', include('engine.urls')),
]

handler404 = 'core.views.content_views.custom_404_view'