from django.core.management.base import BaseCommand
from django.db.models import Count
from core.models import Video
from engine.rag.index_notes import update_video_notes_index
import time

class Command(BaseCommand):
    help = 'Creates or updates FAISS indexes for all videos that have notes.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting to index notes for all videos...'))
        start_time = time.time()
        
        videos_with_notes = Video.objects.annotate(
            note_count=Count('note')
        ).filter(note_count__gt=0)
        
        if not videos_with_notes.exists():
            self.stdout.write(self.style.WARNING('No videos with notes found. No indexes to create.'))
            return

        self.stdout.write(f'Found {videos_with_notes.count()} videos with notes to index.')
        
        indexed_count = 0
        failed_count = 0

        for video in videos_with_notes:
            try:
                self.stdout.write(f'Indexing notes for video: {video.title} (ID: {video.id})...')
                update_video_notes_index(video.id)
                indexed_count += 1
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'Failed to index notes for video {video.id}: {e}'))
                failed_count += 1
        
        end_time = time.time()
        total_time = end_time - start_time
        
        self.stdout.write(self.style.SUCCESS('=' * 30))
        self.stdout.write(self.style.SUCCESS('Note indexing complete!'))
        self.stdout.write(f'Successfully indexed: {indexed_count} videos')
        self.stdout.write(self.style.ERROR(f'Failed to index: {failed_count} videos'))
        self.stdout.write(f'Total time taken: {total_time:.2f} seconds')