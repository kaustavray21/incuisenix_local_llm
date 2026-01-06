from django.core.management.base import BaseCommand
from django_q.models import Task, OrmQ, Schedule
from core.models import Video, Note

class Command(BaseCommand):
    help = 'Clears all Django Q data and resets stuck videos and notes to pending/failed.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("Starting System Cleanup..."))

        # 1. Clear Pending Tasks (The "Stacked Up" Queue)
        pending_count = OrmQ.objects.count()
        if pending_count > 0:
            OrmQ.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(f'  [✓] Deleted {pending_count} pending tasks from queue.'))
        else:
            self.stdout.write('  [-] No pending tasks found.')

        # 2. Clear History (Failed & Successful Logs)
        history_count = Task.objects.count()
        if history_count > 0:
            Task.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(f'  [✓] Deleted {history_count} entries from task history.'))
        else:
            self.stdout.write('  [-] No task history found.')

        # 3. Reset "Stuck" Videos
        # If a task was deleted while running, the statuses remain in "processing" or "indexing".
        self.stdout.write(self.style.WARNING("  Scanning for stuck videos..."))
        
        # A. Audio Transcripts: processing -> pending (Retry)
        count = Video.objects.filter(transcript_status='processing').update(transcript_status='pending')
        if count > 0:
            self.stdout.write(self.style.SUCCESS(f'  [✓] Reset {count} Audio Transcripts from "processing" -> "pending".'))

        # B. OCR Transcripts: processing -> pending (Retry)
        count = Video.objects.filter(ocr_transcript_status='processing').update(ocr_transcript_status='pending')
        if count > 0:
            self.stdout.write(self.style.SUCCESS(f'  [✓] Reset {count} OCR Transcripts from "processing" -> "pending".'))

        # C. Standard Index: indexing -> failed (Stop waiting)
        count = Video.objects.filter(index_status='indexing').update(index_status='failed')
        if count > 0:
            self.stdout.write(self.style.SUCCESS(f'  [✓] Reset {count} Standard Indexes from "indexing" -> "failed".'))

        # D. OCR Index: indexing -> failed (Stop waiting)
        count = Video.objects.filter(ocr_index_status='indexing').update(ocr_index_status='failed')
        if count > 0:
            self.stdout.write(self.style.SUCCESS(f'  [✓] Reset {count} OCR Indexes from "indexing" -> "failed".'))

        # 4. Reset Stuck Notes
        count = Note.objects.filter(index_status='processing').update(index_status='pending')
        if count > 0:
            self.stdout.write(self.style.SUCCESS(f'  [✓] Reset {count} User Notes from "processing" -> "pending".'))

        self.stdout.write(self.style.SUCCESS('\nSystem Ready. Clean slate achieved.'))