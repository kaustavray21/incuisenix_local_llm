from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Note
from .rag.index_notes import update_video_notes_index

@receiver(post_save, sender=Note)
def on_note_save(sender, instance, **kwargs):
    if instance.video:
        # FIX: Pass the full video object and user object
        update_video_notes_index(instance.video, instance.user)

@receiver(post_delete, sender=Note)
def on_note_delete(sender, instance, **kwargs):
    if instance.video:
        # FIX: Pass the full video object and user object
        update_video_notes_index(instance.video, instance.user)