import os
import shutil
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db.models import Q
from core.models import Video
from django_q.tasks import async_task

class Command(BaseCommand):
    help = 'Queues FAISS OCR index generation tasks for videos with existing OCR transcripts.'

    def add_arguments(self, parser):
        parser.add_argument('--wipe', action='store_true', help='Wipe all OCR indexes and reset status.')

    def handle(self, *args, **options):
        # Path to the OCR index directory
        ocr_index_root = os.path.join(settings.FAISS_INDEX_ROOT, 'ocr')

        if options['wipe']:
            self.stdout.write(self.style.WARNING(f'Wiping OCR indexes at {ocr_index_root}...'))
            
            # 1. Delete physical files
            if os.path.exists(ocr_index_root):
                try:
                    shutil.rmtree(ocr_index_root)
                    self.stdout.write(self.style.SUCCESS("  - Deleted physical index directory."))
                except OSError as e:
                    self.stdout.write(self.style.ERROR(f"  - Failed to delete directory: {e}"))
            else:
                self.stdout.write("  - Index directory not found (nothing to delete).")

            # 2. Reset database status
            # Only reset videos that actually have a completed OCR transcript
            count = Video.objects.filter(ocr_transcript_status='complete').update(ocr_index_status='pending')
            self.stdout.write(self.style.SUCCESS(f"  - Reset {count} video statuses to 'pending' (ready for re-indexing)."))

        # Select videos that need indexing
        # Criteria:
        # 1. OCR Transcript MUST be complete.
        # 2. Index status is pending (from wipe/new), failed, or none.
        videos_to_queue = Video.objects.filter(
            ocr_transcript_status='complete'
        ).filter(
            Q(ocr_index_status='none') | 
            Q(ocr_index_status='failed') | 
            Q(ocr_index_status='pending')
        )

        count = videos_to_queue.count()
        self.stdout.write(f'Found {count} videos eligible for OCR indexing.')

        if count == 0:
            self.stdout.write(self.style.SUCCESS("All OCR indexes are up to date."))
            return

        for video in videos_to_queue:
            # OPTIONAL: Set status to 'indexing' immediately so UI shows activity 
            # and prevents double-queueing if command runs again.
            video.ocr_index_status = 'indexing'
            video.save(update_fields=['ocr_index_status'])

            # Queue the task defined in engine/tasks.py
            task_id = async_task('engine.tasks.task_generate_ocr_index', video_id=video.id)
            
            self.stdout.write(f'  [Queueing] {video.title} (ID: {video.id}) -> Task ID: {task_id}')

        self.stdout.write(self.style.SUCCESS(f'\nSuccessfully queued {count} indexing tasks.'))