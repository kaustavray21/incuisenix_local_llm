from django.core.management.base import BaseCommand, CommandError
from core.models import Video, Transcript

class Command(BaseCommand):
    help = 'Diagnoses transcript data. Checks a specific video if a YouTube ID is provided, otherwise checks all videos.'

    def add_arguments(self, parser):
        parser.add_argument(
            'youtube_id',
            nargs='?',
            type=str,
            default=None,
            help='Optional: The YouTube ID of a specific video to diagnose.'
        )

    def _diagnose_video(self, video):
        transcript_lines = Transcript.objects.filter(video=video)
        if not transcript_lines.exists():
            self.stdout.write(self.style.WARNING(
                f"  - ❌ MISSING transcript for '{video.title}' (ID: {video.youtube_id})"
            ))
            return False
        else:
            self.stdout.write(self.style.SUCCESS(
                f"  - ✅ FOUND {transcript_lines.count()} lines for '{video.title}' (ID: {video.youtube_id})"
            ))
            return True

    def handle(self, *args, **options):
        youtube_id = options['youtube_id']

        if youtube_id:
            self.stdout.write(self.style.SUCCESS(
                f"--- Running diagnostics for specific YouTube ID: {youtube_id} ---"
            ))
            try:
                video = Video.objects.get(youtube_id=youtube_id)
                self._diagnose_video(video)
            except Video.DoesNotExist:
                raise CommandError(f"Video with YouTube ID '{youtube_id}' not found.")
        else:
            self.stdout.write(self.style.SUCCESS(
                "--- Running diagnostics for ALL videos in the database ---"
            ))
            all_videos = Video.objects.all()
            if not all_videos:
                self.stdout.write(self.style.WARNING("No videos found in the database to diagnose."))
                return

            success_count = 0
            missing_count = 0
            
            for video in all_videos:
                if self._diagnose_video(video):
                    success_count += 1
                else:
                    missing_count += 1
            
            self.stdout.write("\n" + "="*25)
            self.stdout.write("  Full Diagnostics Summary")
            self.stdout.write("="*25)
            self.stdout.write(self.style.SUCCESS(f"Videos with transcripts: {success_count}"))
            if missing_count > 0:
                self.stdout.write(self.style.ERROR(f"Videos MISSING transcripts: {missing_count}"))
            else:
                self.stdout.write(self.style.SUCCESS("Excellent! All videos have transcripts."))
            self.stdout.write("="*25)


        self.stdout.write(self.style.SUCCESS("\n--- Diagnostics Complete ---"))