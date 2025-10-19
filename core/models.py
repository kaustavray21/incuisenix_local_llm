from django.db import models
from django.contrib.auth.models import User

class Course(models.Model):
    id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=200)
    description = models.TextField()
    image_url = models.URLField(max_length=200)

    def __str__(self):
        return self.title

class Video(models.Model):
    id = models.AutoField(primary_key=True)
    youtube_id = models.CharField(max_length=50, unique=True)
    title = models.CharField(max_length=200)
    video_url = models.URLField(max_length=200)
    course = models.ForeignKey(Course, related_name='videos', on_delete=models.CASCADE)

    def __str__(self):
        return self.title

class Transcript(models.Model):
    id = models.AutoField(primary_key=True)
    start = models.FloatField()
    content = models.TextField()
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name='transcripts')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='transcripts')
    youtube_id = models.CharField(max_length=50, db_index=True, blank=True, null=True)

    def __str__(self):
        return f'{self.video.title} - {self.start}'

class Enrollment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    enrolled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'course')

    def __str__(self):
        return f"{self.user.username} enrolled in {self.course.title}"

class Note(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    video = models.ForeignKey(Video, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=200)
    content = models.TextField()
    video_timestamp = models.PositiveIntegerField(help_text="Timestamp in seconds")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'"{self.title}" by {self.user.username} for {self.video.title}'