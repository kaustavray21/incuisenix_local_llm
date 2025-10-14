import pandas as pd
from django.core.management.base import BaseCommand
from core.models import Transcript, Video

class Command(BaseCommand):
    help = 'Runs diagnostics on video transcripts to check for duration, gaps, and completeness.'

    def add_arguments(self, parser):
        parser.add_argument(
            'youtube_id',
            nargs='?',
            type=str,
            help='The YouTube ID of a specific video to diagnose. If not provided, all videos will be checked.',
        )

    def handle(self, *args, **options):
        youtube_id = options['youtube_id']
        if youtube_id:
            self.stdout.write(self.style.SUCCESS(f"--- Running diagnostics for specific YouTube ID: {youtube_id} ---"))
            self.diagnose_video(youtube_id)
        else:
            self.stdout.write(self.style.SUCCESS("--- Running diagnostics for ALL videos in the database ---"))
            videos = Video.objects.all()
            if not videos.exists():
                self.stdout.write(self.style.WARNING('No videos found.'))
                return
            for video in videos:
                self.diagnose_video(video.youtube_id, video.title)
        
        self.stdout.write(self.style.SUCCESS("\n--- Diagnostics Complete ---"))

    def diagnose_video(self, youtube_id, video_title=None):
        """Runs and prints diagnostics for a single video."""
        if video_title:
            self.stdout.write(f"\n--- Diagnosing Transcript for Video: {video_title} ({youtube_id}) ---")
        
        transcripts = Transcript.objects.filter(video__youtube_id=youtube_id).order_by('start')
        
        if not transcripts.exists():
            self.stdout.write(self.style.ERROR(f"  - ❌ ERROR: No transcript entries found for '{youtube_id}'."))
            return

        df = pd.DataFrame(list(transcripts.values('start', 'content')))
        
        total_entries = len(df)
        min_start = df['start'].min()
        max_start = df['start'].max()
        
        self.stdout.write(self.style.HTTP_INFO("\n[+] Basic Statistics:"))
        self.stdout.write(f"  - Total transcript entries: {total_entries}")
        # --- THIS LINE IS CORRECTED ---
        self.stdout.write(f"  - Earliest entry starts at: {min_start:.2f}s ({self.format_seconds(min_start)})")
        self.stdout.write(f"  - Latest entry starts at:   {max_start:.2f}s ({self.format_seconds(max_start)})")

        df['time_diff'] = df['start'].diff()
        significant_gaps = df[df['time_diff'] > 20] 
        
        self.stdout.write(self.style.HTTP_INFO("\n[+] Gap Analysis:"))
        if significant_gaps.empty:
            self.stdout.write("  - No significant gaps found in the transcript timestamps.")
        else:
            self.stdout.write(self.style.WARNING(f"  - WARNING: Found {len(significant_gaps)} significant gaps ( > 20s)."))
            for index, row in significant_gaps.iterrows():
                gap_duration = row['time_diff']
                gap_start_time = df.loc[index - 1, 'start']
                self.stdout.write(f"    - A gap of {gap_duration:.2f}s was found around {self.format_seconds(gap_start_time)}")

    def format_seconds(self, seconds):
        """Formats seconds into a MMm SSs string for readability."""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"