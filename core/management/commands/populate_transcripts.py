import os
import csv
from django.conf import settings
from django.core.management.base import BaseCommand
from core.models import Video, Transcript

class Command(BaseCommand):
    help = 'Populates the database with new transcripts, skipping videos that already have them.'

    def handle(self, *args, **options):
        self.stdout.write('Starting smart transcript population...')
        videos_to_process = Video.objects.all()
        self.stdout.write(f'Found {videos_to_process.count()} videos to check.')

        for video in videos_to_process:
            if Transcript.objects.filter(video=video).exists():
                self.stdout.write(self.style.SUCCESS(f'Transcripts for "{video.title}" already exist. Skipping.'))
                continue

            self.stdout.write(f'Populating transcripts for "{video.title}"...')
            file_path = os.path.join(settings.MEDIA_ROOT, 'transcripts', video.course.title, f'{video.youtube_id}.csv')

            if not os.path.exists(file_path):
                self.stdout.write(self.style.WARNING(f'  -> CSV file not found. Skipping.'))
                continue

            try:
                lines_to_create = []
                with open(file_path, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    try:
                        next(reader)
                    except StopIteration:
                        self.stdout.write(self.style.WARNING(f'  -> File is empty. Skipping.'))
                        continue

                    for i, row in enumerate(reader):
                        start_str = None
                        content = None
                        
                        if len(row) == 3:
                            start_str, _, content = row
                        elif len(row) == 2:
                            start_str, content = row
                        else:
                            self.stdout.write(self.style.WARNING(f'  -> Skipping malformed row {i+2}. Expected 2 or 3 columns, found {len(row)}.'))
                            continue
                        
                        try:
                            start_time = float(start_str)
                            lines_to_create.append(
                                Transcript(
                                    video=video,
                                    course=video.course,
                                    start=start_time,
                                    content=content.strip(),
                                    youtube_id=video.youtube_id
                                )
                            )
                        except (ValueError, TypeError):
                            self.stdout.write(self.style.WARNING(f'  -> Could not parse start time "{start_str}" on row {i+2}. Skipping.'))
                
                if lines_to_create:
                    Transcript.objects.bulk_create(lines_to_create)
                    self.stdout.write(self.style.SUCCESS(f'  -> Successfully populated transcript.'))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  -> Failed to process transcript: {e}'))

        self.stdout.write(self.style.SUCCESS('Finished transcript population check.'))
