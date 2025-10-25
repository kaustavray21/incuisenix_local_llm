import json
from django.core.management.base import BaseCommand
from django.db import connection
from core.models import Course, Video

class Command(BaseCommand):
    help = 'Loads courses and videos from a JSON file. Use --wipe to clear all data first.'

    def add_arguments(self, parser):
        parser.add_argument('json_file', type=str, help='The path to the JSON file (e.g., "courses.json").')
        
        # --- ADDED THIS NEW ARGUMENT ---
        parser.add_argument(
            '--wipe',
            action='store_true',
            help='Wipe all existing course and video data before loading.',
        )

    def handle(self, *args, **options):
        json_file_path = options['json_file']
        wipe_data = options['wipe']

        # --- ONLY WIPE IF THE --wipe FLAG IS USED ---
        if wipe_data:
            self.stdout.write('Clearing all existing course-related data...')
            Video.objects.all().delete()
            Course.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('Successfully cleared old data.'))

            self.stdout.write('Resetting database auto-increment counters...')
            try:
                with connection.cursor() as cursor:
                    cursor.execute("ALTER TABLE core_course AUTO_INCREMENT = 1;")
                    cursor.execute("ALTER TABLE core_video AUTO_INCREMENT = 1;")
                self.stdout.write(self.style.SUCCESS('Successfully reset counters.'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Could not reset counters: {e}'))
                self.stdout.write(self.style.WARNING('This may be normal for non-MySQL databases (e.g., SQLite). Continuing...'))
        else:
            self.stdout.write(self.style.WARNING('Running in "append" mode. No data will be deleted.'))


        try:
            with open(json_file_path, 'r', encoding='utf-8') as f:
                courses_data = json.load(f)
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f'{json_file_path} not found.'))
            return
        except json.JSONDecodeError:
            self.stdout.write(self.style.ERROR(f'Error decoding {json_file_path}.'))
            return

        for course_data in courses_data:
            course, created = Course.objects.update_or_create(
                title=course_data['title'],
                defaults={
                    'description': course_data.get('description', ''),
                    'image_url': course_data.get('image_url', '')
                }
            )

            if created:
                self.stdout.write(self.style.SUCCESS(f'Created course: "{course.title}"'))
            else:
                self.stdout.write(self.style.WARNING(f'Course "{course.title}" already exists. Adding/updating videos.'))

            for video_data in course_data.get('videos', []):
                video_id = video_data.get('video_id')
                video_url = video_data.get('video_url')
                video_title = video_data.get('title', 'Untitled Video')
                
                if not video_id or not video_url:
                    self.stdout.write(self.style.WARNING(f'  - Skipping video with missing ID or URL: {video_title}'))
                    continue

                video_defaults = {
                    'course': course,
                    'title': video_title,
                    'video_url': video_url
                }

                v_created = False
                video = None

                if 'youtube.com' in video_url:
                    video, v_created = Video.objects.update_or_create(
                        youtube_id=video_id,
                        course=course,
                        defaults=video_defaults
                    )
                elif 'vimeo.com' in video_url:
                    video, v_created = Video.objects.update_or_create(
                        vimeo_id=video_id,
                        course=course,
                        defaults=video_defaults
                    )
                else:
                    self.stdout.write(self.style.WARNING(f'  - Skipping video: Unknown platform for URL: {video_url}'))
                    continue
                
                if v_created:
                    self.stdout.write(f'  - Added video: "{video.title}"')

        self.stdout.write(self.style.SUCCESS(f'Finished loading data from {json_file_path}.'))

# use  --wipe   to clear the dataset of all the video files