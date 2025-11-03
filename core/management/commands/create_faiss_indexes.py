import os
import shutil
import logging
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from core.models import Course
from django_q.tasks import async_task

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Queues FAISS index generation tasks for courses.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--wipe',
            action='store_true',
            help='Wipe all existing FAISS transcript indexes and re-queue all courses.',
        )
        parser.add_argument(
            '--course_id',
            type=int,
            help='Optional: The ID of a specific course to queue.',
        )

    def handle(self, *args, **options):
        wipe_data = options['wipe']
        course_id = options.get('course_id', None)

        if wipe_data:
            self.stdout.write(self.style.WARNING('Wiping all existing FAISS transcript indexes...'))
            index_dir = os.path.join(settings.FAISS_INDEX_ROOT, 'transcripts')
            if os.path.exists(index_dir):
                shutil.rmtree(index_dir)
                self.stdout.write(self.style.SUCCESS(f'Deleted directory: {index_dir}'))
            os.makedirs(index_dir, exist_ok=True)

        if course_id:
            try:
                base_queryset = Course.objects.filter(id=course_id)
                if not base_queryset.exists():
                    raise Course.DoesNotExist
            except Course.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Course with ID {course_id} not found.'))
                return
            self.stdout.write(self.style.SUCCESS(f'Queueing FAISS index generation for ONE course...'))
        else:
            base_queryset = Course.objects.all()
            self.stdout.write(self.style.SUCCESS('Queueing FAISS index generation for ALL courses...'))

        if wipe_data:
            self.stdout.write(self.style.WARNING('(--wipe enabled) Re-queueing all courses.'))
            courses_to_queue = base_queryset
        else:
            self.stdout.write('Queueing "none" and "failed" courses.')
            courses_to_queue = base_queryset.filter(
                Q(index_status='none') | Q(index_status='failed')
            )
        
        total_found = courses_to_queue.count()
        if total_found == 0:
            self.stdout.write('No courses found to queue.')
            return

        self.stdout.write(f'Found {total_found} courses to queue.')

        queued_count = 0
        skipped_count = 0

        for course in courses_to_queue:
            try:
                with transaction.atomic():
                    course_locked = Course.objects.select_for_update().get(pk=course.pk)
                    
                    if course_locked.index_status == 'indexing' and not wipe_data:
                        self.stdout.write(self.style.WARNING(f'  Skipping "{course.title}": Already "indexing"'))
                        skipped_count += 1
                        continue
                    
                    course_locked.index_status = 'indexing'
                    course_locked.save()
                
                async_task('core.tasks.task_generate_index', course_locked.id)
                
                self.stdout.write(self.style.SUCCESS(f'  Queued: "{course.title}" (ID: {course.id})'))
                queued_count += 1
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  Failed to queue "{course.title}": {e}'))

        self.stdout.write(self.style.SUCCESS(f'\nFinished.'))
        self.stdout.write(self.style.SUCCESS(f'Successfully queued {queued_count} tasks.'))
        self.stdout.write(self.style.WARNING(f'Skipped {skipped_count} tasks (already in progress).'))