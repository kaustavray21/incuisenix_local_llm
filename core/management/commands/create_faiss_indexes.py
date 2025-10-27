import os
import re
import time
from django.core.management.base import BaseCommand
from django.conf import settings
from core.models import Video, Transcript
from core.rag.vector_store import create_vector_store_for_video
import logging

logger = logging.getLogger(__name__)

# No sanitize_filename function needed here anymore, as path logic is simpler.

class Command(BaseCommand):
    help = 'Creates FAISS indexes for individual video transcripts, skipping existing ones.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--delay',
            type=int,
            default=7, # Default delay of 7 seconds to respect 10 RPM limit
            help='Seconds to wait between processing each video (default: 7s for 10 RPM).',
        )
        
        parser.add_argument(
            '--wipe',
            action='store_true',
            help='Wipe all existing FAISS transcript indexes before creating new ones.',
        )

    def handle(self, *args, **options):
        delay_seconds = options['delay']
        wipe_data = options['wipe']
        
        self.stdout.write(self.style.SUCCESS(f'Starting FAISS index creation (with {delay_seconds}s delay)...'))

        if wipe_data:
            self.stdout.write(self.style.WARNING('Wiping all existing FAISS transcript indexes...'))
            index_dir = os.path.join(settings.FAISS_INDEX_ROOT, 'transcripts')
            if os.path.exists(index_dir):
                import shutil
                shutil.rmtree(index_dir)
                self.stdout.write(self.style.SUCCESS(f'Deleted directory: {index_dir}'))
            os.makedirs(index_dir, exist_ok=True)

        # We must check all videos
        videos = Video.objects.all()

        if not videos.exists():
            self.stdout.write(self.style.WARNING('No videos found in the database.'))
            return

        processed_count = 0
        skipped_count = 0
        error_count = 0

        for video in videos:
            video_id_to_use = video.youtube_id or video.vimeo_id
            platform = "YouTube" if video.youtube_id else "Vimeo" if video.vimeo_id else "Unknown"

            should_process = True 

            if not video_id_to_use:
                self.stdout.write(self.style.ERROR(f"Video '{video.title}' (ID: {video.id}) has no ID. Skipping."))
                error_count += 1
                should_process = False
            else:
                self.stdout.write(f"\nChecking video: {video.title} ({platform} ID: {video_id_to_use})...")

                if not Transcript.objects.filter(video=video).exists():
                    self.stdout.write(self.style.NOTICE(f"  -> No transcripts found in database. Skipping index creation."))
                    skipped_count += 1
                    should_process = False
                else:
                    # --- This is the Corrected Path Logic ---
                    # It now checks the same path that vector_store.py uses
                    index_path = os.path.join(settings.FAISS_INDEX_ROOT, 'transcripts', video_id_to_use)
                    faiss_file_path = os.path.join(index_path, "index.faiss")

                    if os.path.exists(faiss_file_path) and not wipe_data:
                        self.stdout.write(self.style.NOTICE(f"  -> FAISS index already exists. Skipping generation."))
                        skipped_count += 1
                        should_process = False

            # --- Process or Skip ---
            if should_process:
                self.stdout.write(f"  -> Index not found or wipe enabled. Proceeding with creation...")
                try:
                    create_vector_store_for_video(video_id_to_use)
                    self.stdout.write(self.style.SUCCESS(f"  -> Successfully created index for video: {video.title}"))
                    processed_count += 1
                except Exception as e:
                    if "ResourceExhausted" in str(e) or "429" in str(e):
                        self.stdout.write(self.style.ERROR(f"  -> RATE LIMIT HIT for video {video.title}. Error: {e}"))
                        self.stdout.write(self.style.WARNING("    -> Suggestion: Increase delay or check billing/quota."))
                    else:
                        self.stdout.write(self.style.ERROR(f"  -> Error creating index for video {video.title}: {e}"))
                    logger.exception(f"Failed to create FAISS index for video ID {video_id_to_use}")
                    error_count += 1
            
            # --- Add Delay ---
            if should_process and delay_seconds > 0:
                self.stdout.write(f"    -> Delaying for {delay_seconds} second(s)...")
                time.sleep(delay_seconds)


        # --- Final Summary ---
        self.stdout.write(self.style.SUCCESS(f'\nFinished FAISS index creation check.'))
        self.stdout.write(self.style.SUCCESS(f'Created/Updated {processed_count} indexes.'))
        self.stdout.write(self.style.NOTICE(f'Skipped {skipped_count} videos.'))
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f'{error_count} videos encountered errors.'))