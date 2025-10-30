from rest_framework import serializers
from .models import Course, Video

class VideoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Video
        fields = ['title', 'video_url', 'youtube_id', 'vimeo_id']

    def validate(self, data):
        """
        Check that at least one of youtube_id or vimeo_id is provided.
        """
        if not data.get('youtube_id') and not data.get('vimeo_id'):
            raise serializers.ValidationError("A video must have either a youtube_id or a vimeo_id.")
        return data

class CourseSerializer(serializers.ModelSerializer):
    videos = VideoSerializer(many=True, write_only=True)

    class Meta:
        model = Course
        fields = ['id', 'title', 'description', 'image_url', 'videos']
        read_only_fields = ['id']

    def create(self, validated_data):
        videos_data = validated_data.pop('videos')
        course = Course.objects.create(**validated_data)
        for video_data in videos_data:
            Video.objects.create(course=course, **video_data)
        return course