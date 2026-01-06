import os
import csv
import logging
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import transaction
from core.models import Video, OCRTranscript 

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Imports local OCR CSV files into the database and flags them for indexing.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--wipe',
            action='store_true',
            help='Wipe all existing OCR transcripts before importing.',
        )

    def handle(self, *args, **options):
        base_dir = os.path.join(settings.MEDIA_ROOT, 'ocr_transcripts')
        
        # --- WIPE LOGIC ---
        if options['wipe']:
            self.stdout.write(self.style.WARNING('!!! WIPE DETECTED !!!'))
            self.stdout.write('Cleaning Database records...')
            with transaction.atomic():
                count, _ = OCRTranscript.objects.all().delete()
                
                # Reset transcript status to pending (needs import/processing)
                # Reset index status to none (source data is gone, so index is invalid)
                Video.objects.update(
                    ocr_transcript_status='pending',
                    ocr_index_status='none' 
                )
            self.stdout.write(self.style.SUCCESS(f'  - Deleted {count} OCR transcript rows from DB.'))
            self.stdout.write(self.style.SUCCESS('  - Reset video statuses.'))
        # ------------------

        if not os.path.exists(base_dir):
            self.stdout.write(self.style.ERROR(f"Directory not found: {base_dir}"))
            return

        self.stdout.write(f"Scanning directory: {base_dir}")
        
        processed_count = 0
        skipped_count = 0
        error_count = 0

        # Walk through course folders
        for root, dirs, files in os.walk(base_dir):
            for filename in files:
                if not filename.endswith('.csv'):
                    continue

                file_path = os.path.join(root, filename)
                # Remove extension to get ID (e.g., "video_123" or "817684084")
                file_id = os.path.splitext(filename)[0]
                
                try:
                    self.process_file(file_path, file_id)
                    processed_count += 1
                except Video.DoesNotExist:
                    self.stdout.write(self.style.WARNING(f"Skipped {filename}: Video not found in DB."))
                    skipped_count += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error processing {filename}: {e}"))
                    error_count += 1

        self.stdout.write(self.style.SUCCESS(f"\nImport Finished."))
        self.stdout.write(f"Processed: {processed_count}")
        self.stdout.write(f"Skipped (No DB Match): {skipped_count}")
        self.stdout.write(f"Errors: {error_count}")

    def process_file(self, file_path, file_id):
        video = None
        
        # 1. Try finding by Vimeo ID (Most common in your dataset)
        if not video:
            try:
                video = Video.objects.get(vimeo_id=file_id)
            except Video.DoesNotExist:
                pass
        
        # 2. Try finding by YouTube ID
        if not video:
            try:
                video = Video.objects.get(youtube_id=file_id)
            except Video.DoesNotExist:
                pass

        # 3. Try finding by DB ID (e.g. video_123.csv)
        if not video and file_id.startswith('video_'):
            try:
                db_id = int(file_id.split('_')[1])
                video = Video.objects.get(id=db_id)
            except (IndexError, ValueError, Video.DoesNotExist):
                pass
        
        # Final check
        if not video:
            raise Video.DoesNotExist

        # Delete existing DB records for this specific video to avoid duplicates
        # (Even if --wipe wasn't used globally)
        if video.ocr_transcripts.exists():
            # self.stdout.write(f"  Refreshing records for: {video.title}")
            video.ocr_transcripts.all().delete()

        transcript_objects = []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            # Handle potential header
            first_row = next(reader, None)
            if not first_row:
                return # Empty file

            # Check if first row is header or data
            try:
                float(first_row[0])
                # It's data, process it
                if len(first_row) >= 2:
                    transcript_objects.append(self._create_obj(video, first_row))
            except ValueError:
                # It's likely a header ("start", "content"), skip it
                pass
            
            # Process rest of rows
            for row in reader:
                if len(row) < 2:
                    continue
                obj = self._create_obj(video, row)
                if obj:
                    transcript_objects.append(obj)

        if transcript_objects:
            with transaction.atomic():
                OCRTranscript.objects.bulk_create(transcript_objects)
                
                # --- CRITICAL UPDATE ---
                # 1. Mark OCR Transcript as Complete
                video.ocr_transcript_status = 'complete'
                
                # 2. Mark OCR Index as Pending
                # This ensures the 'create_ocr_indexes' command or the signal logic
                # knows this video is ready for vector embedding.
                video.ocr_index_status = 'pending'
                
                video.save(update_fields=['ocr_transcript_status', 'ocr_index_status'])
                
            self.stdout.write(f"  [Imported] {video.title} ({len(transcript_objects)} segments)")

    def _create_obj(self, video, row):
        try:
            start_time = float(row[0])
            text_content = row[1].strip()

            if text_content:
                # Get platform IDs for the model fields
                vid_yid = video.youtube_id
                vid_vid = video.vimeo_id

                return OCRTranscript(
                    video=video,
                    start=start_time,
                    course=video.course,
                    content=text_content,
                    youtube_id=vid_yid,
                    vimeo_id=vid_vid
                )
        except ValueError:
            return None
        return None