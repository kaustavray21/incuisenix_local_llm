import os
import logging
from django.core.management.base import BaseCommand
from django.conf import settings
from core.models import Video

class Command(BaseCommand):
    help = 'Syncs video status based on existing DB entries and files. Resets stuck indexing tasks.'

    def handle(self, *args, **options):
        videos = Video.objects.all()
        self.stdout.write(f"Scanning {videos.count()} videos...")
        
        updated_count = 0
        reset_count = 0

        for video in videos:
            changed = False
            
            if video.transcripts.exists():
                if video.transcript_status != 'complete':
                    video.transcript_status = 'complete'
                    changed = True
            
            platform_id = video.youtube_id or video.vimeo_id
            index_exists_on_disk = False

            if platform_id:
                index_path = os.path.join(settings.FAISS_INDEX_ROOT, 'transcripts', platform_id)
                if os.path.exists(index_path) and os.path.exists(os.path.join(index_path, 'index.faiss')):
                    index_exists_on_disk = True

            if index_exists_on_disk:
                if video.index_status != 'complete':
                    video.index_status = 'complete'
                    changed = True
            
            else:
                if video.index_status in ['indexing', 'complete']:
                    self.stdout.write(self.style.WARNING(f"  Resetting '{video.title}': Status was '{video.index_status}' but no file found."))
                    video.index_status = 'none'
                    changed = True
                    reset_count += 1

            if changed:
                video.save(update_fields=['transcript_status', 'index_status'])
                updated_count += 1

        self.stdout.write(self.style.SUCCESS(f"\n-----------------------------------"))
        self.stdout.write(self.style.SUCCESS(f"Sync Finished."))
        self.stdout.write(self.style.SUCCESS(f"Updated/Synced: {updated_count} videos"))
        self.stdout.write(self.style.WARNING(f"Reset (Fixed Stuck): {reset_count} videos"))
        self.stdout.write(self.style.SUCCESS(f"-----------------------------------"))