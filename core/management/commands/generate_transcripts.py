from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from core.models import Video, Course
from django_q.tasks import async_task

class Command(BaseCommand):
    help = 'Queues transcript generation tasks for videos.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--course_id',
            type=int,
            help='Optional: The ID of the course to process videos for.',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force re-queueing of videos marked "complete" or "failed".',
        )

    def handle(self, *args, **options):
        course_id = options.get('course_id', None)
        force = options.get('force', False)
        
        base_queryset = Video.objects.all()

        if course_id:
            try:
                course = Course.objects.get(id=course_id)
                self.stdout.write(self.style.SUCCESS(f'Starting transcript queuing for ONE course: "{course.title}"'))
                base_queryset = Video.objects.filter(course=course)
            except Course.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Course with ID {course_id} not found.'))
                return
        else:
            self.stdout.write(self.style.SUCCESS('Starting transcript queuing process for ALL courses...'))

        if force:
            self.stdout.write(self.style.WARNING('(--force enabled) Re-queueing "complete" and "failed" videos.'))
            videos_to_queue = base_queryset.filter(
                Q(transcript_status='complete') | Q(transcript_status='failed')
            )
        else:
            self.stdout.write('Queueing "pending" and "failed" videos.')
            videos_to_queue = base_queryset.filter(
                Q(transcript_status='pending') | Q(transcript_status='failed')
            )

        total_found = videos_to_queue.count()
        if total_found == 0:
            self.stdout.write('No videos found to queue.')
            return

        self.stdout.write(f'Found {total_found} videos to queue.')
        
        queued_count = 0
        skipped_count = 0
        
        for video in videos_to_queue:
            try:
                with transaction.atomic():
                    video_locked = Video.objects.select_for_update().get(pk=video.pk)
                    
                    if video_locked.transcript_status == 'processing':
                        self.stdout.write(self.style.WARNING(f'  Skipping "{video.title}": Already "processing"'))
                        skipped_count += 1
                        continue
                    
                    video_locked.transcript_status = 'processing'
                    video_locked.save()
                
                async_task('engine.tasks.task_generate_transcript', video_locked.id)
                
                self.stdout.write(self.style.SUCCESS(f'  Queued: "{video.title}" (ID: {video.id})'))
                queued_count += 1
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  Failed to queue "{video.title}": {e}'))

        self.stdout.write(self.style.SUCCESS(f'\nFinished.'))
        self.stdout.write(self.style.SUCCESS(f'Successfully queued {queued_count} tasks.'))
        self.stdout.write(self.style.WARNING(f'Skipped {skipped_count} tasks (already in progress).'))