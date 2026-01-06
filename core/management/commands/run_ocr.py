from django.core.management.base import BaseCommand
from django.db.models import Q
from core.models import Video
# Ensure this import path matches your actual file structure
from engine.transcript_service.ocr_service.video_ocr_service import VideoOCRService

class Command(BaseCommand):
    help = 'Runs OCR extraction on videos. Processes pending AND failed videos.'

    def add_arguments(self, parser):
        parser.add_argument(
            'video_identifier', 
            nargs='?', 
            type=str, 
            help='The Vimeo ID or YouTube ID of the video to process'
        )
        # Optional: Add a flag to force re-processing of completed videos
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force re-processing of completed videos'
        )

    def handle(self, *args, **options):
        video_identifier = options['video_identifier']
        force_mode = options['force']
        
        # Initialize service with default sample rate
        service = VideoOCRService(sample_rate=2)

        # 1. Determine which videos to process
        if video_identifier:
            videos = Video.objects.filter(
                Q(vimeo_id=video_identifier) | Q(youtube_id=video_identifier)
            )
            if not videos.exists():
                self.stdout.write(self.style.ERROR(f'No video found with ID: {video_identifier}'))
                return
        else:
            self.stdout.write(self.style.WARNING('No ID provided. Searching for queue...'))
            
            # IMPROVEMENT: Include 'failed' so you can retry automatically
            query = Q(ocr_transcript_status='pending') | Q(ocr_transcript_status='failed')
            
            if force_mode:
                 self.stdout.write(self.style.WARNING('FORCE MODE: including completed videos.'))
                 videos = Video.objects.all()
            else:
                 videos = Video.objects.filter(query)
            
            if not videos.exists():
                self.stdout.write(self.style.SUCCESS('No pending or failed videos found.'))
                return

        self.stdout.write(self.style.WARNING(f'Found {videos.count()} video(s) to process...'))

        # 2. Process Loop
        for video in videos:
            display_id = video.vimeo_id or video.youtube_id or video.id
            self.stdout.write(f'Starting processing for Video: {video.title} (ID: {display_id})...')
            
            # Set to processing so UI knows something is happening
            video.ocr_transcript_status = 'processing'
            video.save(update_fields=['ocr_transcript_status'])

            try:
                # Pass the internal DB ID to the service
                success = service.process_video(video.id)

                if success:
                    # Refetch to ensure we don't overwrite if service already saved
                    video.refresh_from_db()
                    
                    # 1. Mark Transcript as Complete
                    video.ocr_transcript_status = 'complete'
                    
                    # 2. Mark Index as Pending (Triggers next step in pipeline)
                    # This ensures the 'create_ocr_indexes' command or signals pick it up
                    video.ocr_index_status = 'pending'
                    
                    video.save(update_fields=['ocr_transcript_status', 'ocr_index_status'])
                    self.stdout.write(self.style.SUCCESS(f'Successfully processed: {display_id}. Marked for Indexing.'))
                else:
                    video.ocr_transcript_status = 'failed'
                    video.save(update_fields=['ocr_transcript_status'])
                    self.stdout.write(self.style.ERROR(f'Failed to process: {display_id}'))
            
            except Exception as e:
                # Catch unexpected crashes (like keyboard interrupt) to ensure DB isn't stuck
                self.stdout.write(self.style.ERROR(f'Exception processing {display_id}: {e}'))
                video.ocr_transcript_status = 'failed'
                video.save(update_fields=['ocr_transcript_status'])