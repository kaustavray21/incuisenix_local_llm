from django.core.management.base import BaseCommand
from core.models import Video
from core.rag.vector_store import create_vector_store_for_video

class Command(BaseCommand):
    help = 'Creates FAISS indexes for all video transcripts in the database.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting to create FAISS indexes for all videos...'))
        videos = Video.objects.all()
        
        if not videos.exists():
            self.stdout.write(self.style.WARNING('No videos found in the database.'))
            return

        for video in videos:
            self.stdout.write(f"Processing video: {video.title} ({video.youtube_id})")
            try:
                create_vector_store_for_video(video.youtube_id)
                self.stdout.write(self.style.SUCCESS(f"Successfully created index for video: {video.title}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error creating index for video {video.title}: {e}"))
        
        self.stdout.write(self.style.SUCCESS('Finished creating all FAISS indexes.'))