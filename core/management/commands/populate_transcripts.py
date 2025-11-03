import os
import csv
import re
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection, transaction
from core.models import Video, Transcript

def sanitize_filename(title):
    return re.sub(r'[\\/*?:"<>|]', "", title)

class Command(BaseCommand):
    help = 'Manually populates the database from existing CSV files and updates video status.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--wipe',
            action='store_true',
            help='Wipe all existing transcript data from the database before populating.',
        )
        parser.add_argument(
            '--course_id',
            type=int,
            help='Optional: The ID of a specific course to populate.',
        )

    def handle(self, *args, **options):
        wipe_data = options['wipe']
        course_id = options.get('course_id', None)

        if wipe_data:
            self.stdout.write(self.style.WARNING('Wiping all existing transcripts from the database...'))
            deleted_count, _ = Transcript.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(f'Successfully deleted {deleted_count} old transcript lines.'))
            
            try:
                with connection.cursor() as cursor:
                    cursor.execute("ALTER TABLE core_transcript AUTO_INCREMENT = 1;")
                self.stdout.write(self.style.SUCCESS('Successfully reset counter.'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Could not reset counter: {e}'))
                self.stdout.write(self.style.WARNING('This may be normal for non-MySQL databases (e.g., SQLite). Continuing...'))
        
        if course_id:
            try:
                course = Video.objects.filter(course_id=course_id)
                self.stdout.write(f'Processing videos for course ID {course_id}...')
                videos_to_process = course
            except:
                self.stdout.write(self.style.ERROR(f'Course with ID {course_id} not found.'))
                return
        elif wipe_data:
            self.stdout.write('Starting full transcript population from CSV files...')
            videos_to_process = Video.objects.all()
        else:
            self.stdout.write('Starting smart transcript population (only "pending" videos)...')
            videos_to_process = Video.objects.filter(transcript_status='pending')

        self.stdout.write(f'Found {videos_to_process.count()} videos to process.')

        for video in videos_to_process:
            video_id = video.youtube_id or video.vimeo_id
            platform_id_field = 'youtube_id' if video.youtube_id else 'vimeo_id'

            if not video_id:
                self.stdout.write(self.style.ERROR(f'Video "{video.title}" (DB ID: {video.id}) has no youtube_id or vimeo_id. Skipping.'))
                continue

            self.stdout.write(f'Populating transcripts for "{video.title}" (ID: {video_id})...')

            course_dir_safe = sanitize_filename(video.course.title)
            file_path = os.path.join(settings.MEDIA_ROOT, 'transcripts', course_dir_safe, f'{video_id}.csv')

            if not os.path.exists(file_path):
                self.stdout.write(self.style.WARNING(f'  -> CSV file not found at: {file_path}. Skipping.'))
                continue

            try:
                lines_to_create = []
                with open(file_path, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    try:
                        header = next(reader)
                    except StopIteration:
                        self.stdout.write(self.style.WARNING(f'  -> File is empty: {file_path}. Skipping.'))
                        continue

                    for i, row in enumerate(reader):
                        start_str = None
                        content = None

                        if len(row) == 2:
                            start_str, content = row
                        elif len(row) == 3:
                            start_str, _duration, content = row
                        else:
                            self.stdout.write(self.style.WARNING(f'  -> Skipping malformed row {i+2} in {file_path}. Expected 2 or 3 columns, found {len(row)}.'))
                            continue

                        try:
                            start_time = float(start_str)
                            content_stripped = content.strip()
                            if content_stripped:
                                transcript_kwargs = {
                                    'video': video,
                                    'course': video.course,
                                    'start': start_time,
                                    'content': content_stripped,
                                    platform_id_field: video_id
                                }
                                lines_to_create.append(Transcript(**transcript_kwargs))
                        except (ValueError, TypeError):
                            self.stdout.write(self.style.WARNING(f'  -> Could not parse start time "{start_str}" on row {i+2} in {file_path}. Skipping.'))

                if lines_to_create:
                    with transaction.atomic():
                        if not wipe_data:
                            Transcript.objects.filter(video=video).delete()
                        
                        Transcript.objects.bulk_create(lines_to_create)
                        
                        video.transcript_status = 'complete'
                        video.save()
                        
                    self.stdout.write(self.style.SUCCESS(f'  -> Successfully populated {len(lines_to_create)} lines and set video status to "complete".'))
                else:
                    self.stdout.write(self.style.WARNING(f'  -> No valid transcript lines were found in {os.path.basename(file_path)}.'))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  -> Failed to process transcript file {file_path}: {e}'))

        self.stdout.write(self.style.SUCCESS('Finished transcript population from CSVs.'))
