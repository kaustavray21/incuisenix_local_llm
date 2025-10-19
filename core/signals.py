from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Note

@receiver(post_save, sender=Note)
def on_note_save(sender, instance, **kwargs):
    from .rag.index_notes import update_video_notes_index
    if instance.video:
        update_video_notes_index(instance.video.id)

@receiver(post_delete, sender=Note)
def on_note_delete(sender, instance, **kwargs):
    from .rag.index_notes import update_video_notes_index
    if instance.video:
        update_video_notes_index(instance.video.id)