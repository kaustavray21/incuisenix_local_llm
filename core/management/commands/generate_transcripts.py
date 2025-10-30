import os
from django.core.management.base import BaseCommand
from core.models import Video, Course
from core.transcript_service import generate_transcript_for_video

class Command(BaseCommand):
    help = 'Generates transcript CSV files for videos. Can be filtered by course.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--course_id',
            type=int,
            help='Optional: The ID of the course to process videos for.',
        )

    def handle(self, *args, **options):
        course_id = options.get('course_id', None)
        
        if course_id:
            try:
                course = Course.objects.get(id=course_id)
                self.stdout.write(self.style.SUCCESS(f'Starting transcript generation for ONE course: "{course.title}"'))
                videos_to_check = Video.objects.filter(course=course)
            except Course.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Course with ID {course_id} not found.'))
                return
        else:
            self.stdout.write(self.style.SUCCESS('Starting transcript file generation process for ALL courses...'))
            videos_to_check = Video.objects.all()

        self.stdout.write(f'Found {videos_to_check.count()} total videos to check.')
        
        for video in videos_to_check:
            self.stdout.write(f'\nChecking video: "{video.title}" (ID: {video.id})')
            
            status_msg, log = generate_transcript_for_video(video, force_generation=False)
            
            for line in log:
                if "ERROR" in line:
                    self.stdout.write(self.style.ERROR(line))
                elif "SUCCESS" in line:
                    self.stdout.write(self.style.SUCCESS(line))
                elif "WARNING" in line:
                    self.stdout.write(self.style.WARNING(line))
                else:
                    self.stdout.write(line)

        self.stdout.write(self.style.SUCCESS('\nFinished transcript file generation.'))