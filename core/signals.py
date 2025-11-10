from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Note
from django_q.tasks import async_task
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Note)
def on_note_save(sender, instance, created, **kwargs):
    """
    When a note is saved (created or updated), queue an async task
    to update the user's FAISS index for this video.
    """
    if instance.video:
        platform_id = instance.video.youtube_id or instance.video.vimeo_id

        if platform_id:
            if not created and instance.index_status != 'pending':
                Note.objects.filter(pk = instance.pk).update(index_status = 'pending')
                logger.info(f"Signal: Queuing note index update for user {instance.user.id}, video {platform_id}")
                async_task('core.tasks.task_update_note_index', user_id = instance.user.id, video_id = platform_id)
        else:
            logger.warning(f"Signal: Note {instance.pk} was saved, but its video has no platform_id. Cannot queue task.")

@receiver(post_delete, sender=Note)
def on_note_delete(sender, instance, **kwargs):
    if instance.video:
        """
        When a note is deleted, queue an async task to rebuild the index
        for that user/video, which will now exclude the deleted note.
        """
        platform_id = instance.video.youtube_id or instance.video.vimeo_id

        if platform_id:
            logger.info(f"Signal: Queuing note index update (due to delete) for user {instance.user.id}, video {platform_id}")
            async_task('core.tasks.taks_update_note_index', user_id = instance.user.id, video_id = platform_id)
        else:
            logger.warning(f"Signal: Note {instance.pk} was deleted, but its video has no platform_id. Cannot queue task.")

            