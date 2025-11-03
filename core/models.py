from django.db import models
from django.contrib.auth.models import User

class Course(models.Model):
    id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=200)
    description = models.TextField()
    image_url = models.URLField(max_length=200)

    # --- ADDED FOR FAISS INDEXING STATUS ---
    INDEX_STATUS_CHOICES = [
        ('none', 'No Index'),
        ('indexing', 'Indexing'),
        ('complete', 'Complete'),
        ('failed', 'Failed'),
    ]
    index_status = models.CharField(
        max_length=20,
        choices=INDEX_STATUS_CHOICES,
        default='none',
        db_index=True  # Add db_index for faster lookups
    )
    # --- END OF ADDITION ---

    def __str__(self):
        return self.title

class Video(models.Model):
    id = models.AutoField(primary_key=True)
    
    # --- MODIFIED: Made unique=True. This is critical for your plan. ---
    # We must allow them to be null, but if they exist, they must be unique.
    youtube_id = models.CharField(max_length=50, unique=True, blank=True, null=True, db_index=True)
    vimeo_id = models.CharField(max_length=50, unique=True, blank=True, null=True, db_index=True)
    # --- END OF MODIFICATION ---

    title = models.CharField(max_length=200)
    video_url = models.URLField(max_length=200)
    course = models.ForeignKey(Course, related_name='videos', on_delete=models.CASCADE)

    # --- ADDED FOR TRANSCRIPT STATUS ---
    TRANSCRIPT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('complete', 'Complete'),
        ('failed', 'Failed'),
    ]
    transcript_status = models.CharField(
        max_length=20,
        choices=TRANSCRIPT_STATUS_CHOICES,
        default='pending',
        db_index=True # Add db_index for faster lookups
    )
    # --- END OF ADDITION ---

    def __str__(self):
        return self.title

class Transcript(models.Model):
    id = models.AutoField(primary_key=True)
    start = models.FloatField()
    content = models.TextField()
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name='transcripts')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='transcripts')
    youtube_id = models.CharField(max_length=50, db_index=True, blank=True, null=True)
    vimeo_id = models.CharField(max_length=50, db_index=True, blank=True, null=True)

    def __str__(self):
        return f'{self.video.title} - {self.start}'

# ... (rest of your models: Enrollment, Note, Conversation, ConversationMessage)
# No changes are needed for the other models.

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
    
    
class Conversation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='conversations')
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name='conversations')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='conversations')
    title = models.CharField(max_length=255, default="New Conversation")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'"{self.title}" by {self.user.username} for {self.video.title}'

class ConversationMessage(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    query = models.TextField()
    answer = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f'Query in "{self.conversation.title}" at {self.timestamp}'