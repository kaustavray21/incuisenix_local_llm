import os
import csv
import re
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection
from core.models import Video, Transcript

def sanitize_filename(title):
    """Sanitizes a string for use as a filename/directory."""
    return re.sub(r'[\\/*?:"<>|]', "", title)

class Command(BaseCommand):
    help = 'Populates the database from CSV files. Use --wipe to clear all transcripts first.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--wipe',
            action='store_true',
            help='Wipe all existing transcript data from the database before populating.',
        )

    def handle(self, *args, **options):
        wipe_data = options['wipe']

        if wipe_data:
            self.stdout.write(self.style.WARNING('Wiping all existing transcripts from the database...'))
            deleted_count, _ = Transcript.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(f'Successfully deleted {deleted_count} old transcript lines.'))
            
            self.stdout.write('Resetting transcript table auto-increment counter...')
            try:
                with connection.cursor() as cursor:
                    # Note: This table name depends on your app name (e.g., core_transcript)
                    cursor.execute("ALTER TABLE core_transcript AUTO_INCREMENT = 1;")
                self.stdout.write(self.style.SUCCESS('Successfully reset counter.'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Could not reset counter: {e}'))
                self.stdout.write(self.style.WARNING('This may be normal for non-MySQL databases (e.g., SQLite). Continuing...'))
            
            # If wiping, we process ALL videos, not just ones without transcripts
            self.stdout.write('Starting full transcript population from CSV files...')
            videos_to_process = Video.objects.all()
        else:
            # Original "smart" behavior
            self.stdout.write('Starting smart transcript population from CSV files...')
            videos_to_process = Video.objects.filter(transcripts__isnull=True).distinct()

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
                self.stdout.write(self.style.WARNING(f'  -> CSV file not found at: {file_path}. Run generate_transcripts first. Skipping.'))
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
                            else:
                                self.stdout.write(self.style.NOTICE(f"    -> Skipping empty content at row {i+2} in {file_path}"))
                        except (ValueError, TypeError):
                            self.stdout.write(self.style.WARNING(f'  -> Could not parse start time "{start_str}" on row {i+2} in {file_path}. Skipping.'))

                if lines_to_create:
                    Transcript.objects.bulk_create(lines_to_create)
                    self.stdout.write(self.style.SUCCESS(f'  -> Successfully populated {len(lines_to_create)} transcript lines from {os.path.basename(file_path)}.'))
                else:
                    self.stdout.write(self.style.WARNING(f'  -> No valid transcript lines were found in {os.path.basename(file_path)}.'))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  -> Failed to process transcript file {file_path}: {e}'))

        self.stdout.write(self.style.SUCCESS('Finished transcript population from CSVs.'))