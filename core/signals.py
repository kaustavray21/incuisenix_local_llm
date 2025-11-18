from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from core.models import Note, Video
from django_q.tasks import async_task
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Video)
def on_video_save(sender, instance, created, **kwargs):
    if created:
        logger.info(f"Signal: New video created (ID: {instance.pk}). Scheduling processing pipeline.")
        
        # --- UPDATED: Set both statuses on the Video object directly ---
        instance.transcript_status = 'processing'
        instance.index_status = 'indexing'
        instance.save(update_fields=['transcript_status', 'index_status'])
        
        async_task(
            'engine.tasks.task_process_new_video',
            instance.pk
        )

@receiver(post_save, sender=Note)
def on_note_save(sender, instance, created, **kwargs):
    if instance.video:
        platform_id = instance.video.youtube_id or instance.video.vimeo_id

        if platform_id:
            if not created and instance.index_status != 'pending':
                Note.objects.filter(pk=instance.pk).update(index_status='pending')
            
            logger.info(f"Signal: Queuing note index update for user {instance.user.id}, video {platform_id}")
            async_task('engine.tasks.task_update_note_index', user_id=instance.user.id, video_id=platform_id)
        else:
            logger.warning(f"Signal: Note {instance.pk} was saved, but its video has no platform_id. Cannot queue task.")

@receiver(post_delete, sender=Note)
def on_note_delete(sender, instance, **kwargs):
    if instance.video:
        platform_id = instance.video.youtube_id or instance.video.vimeo_id

        if platform_id:
            logger.info(f"Signal: Queuing note index update (due to delete) for user {instance.user.id}, video {platform_id}")
            async_task('engine.tasks.task_update_note_index', user_id=instance.user.id, video_id=platform_id)
        else:
            logger.warning(f"Signal: Note {instance.pk} was deleted, but its video has no platform_id. Cannot queue task.")