import os
from django.core.management.base import BaseCommand
from django.conf import settings
from core.models import Video, Transcript

class Command(BaseCommand):
    help = 'Syncs video status (transcript & index) based on existing DB entries and files.'

    def handle(self, *args, **options):
        videos = Video.objects.all()
        self.stdout.write(f"Scanning {videos.count()} videos...")
        
        updated_count = 0

        for video in videos:
            changed = False
            
            # 1. Check Transcript Status
            # If we have transcript entries in the DB, the status should be 'complete'
            if video.transcripts.exists():
                if video.transcript_status != 'complete':
                    video.transcript_status = 'complete'
                    changed = True
            
            # 2. Check FAISS Index Status
            # We check if the folder exists on the disk
            platform_id = video.youtube_id or video.vimeo_id
            if platform_id:
                index_path = os.path.join(settings.FAISS_INDEX_ROOT, 'transcripts', platform_id)
                # FAISS indexes usually contain 'index.faiss' and 'index.pkl'
                if os.path.exists(index_path) and os.path.exists(os.path.join(index_path, 'index.faiss')):
                    if video.index_status != 'complete':
                        video.index_status = 'complete'
                        changed = True
            
            if changed:
                video.save(update_fields=['transcript_status', 'index_status'])
                self.stdout.write(self.style.SUCCESS(f"Updated status for: {video.title}"))
                updated_count += 1
            else:
                self.stdout.write(f"Skipped (already synced): {video.title}")

        self.stdout.write(self.style.SUCCESS(f"\nSuccessfully synced {updated_count} videos."))