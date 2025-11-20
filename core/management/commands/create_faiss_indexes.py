import os
import shutil
import logging
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db.models import Q
from core.models import Course, Video  # Import Video
from django_q.tasks import async_task

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Queues FAISS index generation tasks for courses based on video status.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--wipe',
            action='store_true',
            help='Wipe all existing FAISS transcript indexes, reset Video statuses, and re-queue all.',
        )
        parser.add_argument(
            '--course_id',
            type=int,
            help='Optional: The ID of a specific course to queue.',
        )

    def handle(self, *args, **options):
        wipe_data = options['wipe']
        course_id = options.get('course_id', None)

        # 1. Handle Wipe: Delete files AND reset DB status
        if wipe_data:
            self.stdout.write(self.style.WARNING('Wiping all existing FAISS transcript indexes...'))
            index_dir = os.path.join(settings.FAISS_INDEX_ROOT, 'transcripts')
            if os.path.exists(index_dir):
                shutil.rmtree(index_dir)
                self.stdout.write(self.style.SUCCESS(f'Deleted directory: {index_dir}'))
            os.makedirs(index_dir, exist_ok=True)
            
            # Reset all videos to 'none' so they get picked up
            self.stdout.write(self.style.WARNING('Resetting all Video index statuses to "none"...'))
            Video.objects.all().update(index_status='none')

        # 2. Build QuerySet
        base_queryset = Course.objects.all()

        if course_id:
            # If specific ID provided, just try to get that course
            courses_to_queue = base_queryset.filter(id=course_id)
            if not courses_to_queue.exists():
                self.stdout.write(self.style.ERROR(f'Course with ID {course_id} not found.'))
                return
            self.stdout.write(self.style.SUCCESS(f'Queueing specific course ID: {course_id}'))
        
        elif wipe_data:
            # If wipe, queue everything
            courses_to_queue = base_queryset
            self.stdout.write(self.style.SUCCESS('Queueing ALL courses (wipe enabled).'))
            
        else:
            # 3. Smart Filtering: Only queue courses that have at least one video 
            # with status 'none' or 'failed'.
            self.stdout.write('Looking for courses with videos needing indexing...')
            courses_to_queue = base_queryset.filter(
                Q(videos__index_status='none') | Q(videos__index_status='failed')
            ).distinct()

        total_found = courses_to_queue.count()
        if total_found == 0:
            self.stdout.write('No courses found needing indexing.')
            return

        self.stdout.write(f'Found {total_found} courses to process.')

        queued_count = 0

        for course in courses_to_queue:
            try:
                # Note: We removed the transaction/locking on Course because 
                # Course no longer holds the status. The task handles Video locking/updates.
                
                # FIX: Corrected path from 'core.tasks' to 'engine.tasks'
                async_task('engine.tasks.task_generate_index', course.id)
                
                self.stdout.write(self.style.SUCCESS(f'  Queued: "{course.title}" (ID: {course.id})'))
                queued_count += 1
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  Failed to queue "{course.title}": {e}'))

        self.stdout.write(self.style.SUCCESS(f'\nFinished. Successfully queued {queued_count} tasks.'))