import os
import logging
import shutil
from django.core.management.base import BaseCommand
from django.conf import settings
from core.models import Video
from engine.transcript_service.utils import sanitize_filename 

class Command(BaseCommand):
    help = 'Syncs video status. Resets FAILED, processing, or stuck tasks if no data exists.'

    def handle(self, *args, **options):
        videos = Video.objects.all()
        self.stdout.write(f"Scanning {videos.count()} videos...")
        
        updated_count = 0
        reset_count = 0

        for video in videos:
            changed = False
            
            # ==========================================
            # 1. Sync Audio Transcript Status
            # ==========================================
            if video.transcripts.exists():
                if video.transcript_status != 'complete':
                    video.transcript_status = 'complete'
                    changed = True
            
            # ==========================================
            # 2. Sync OCR Transcript Status
            # ==========================================
            ocr_db_exists = video.ocr_transcripts.exists()
            
            # Construct expected file path
            if video.course:
                course_dir = sanitize_filename(video.course.title)
            else:
                course_dir = "Uncategorized"
                
            platform_id = video.vimeo_id or video.youtube_id
            if platform_id:
                filename = f"{platform_id}.csv"
            else:
                filename = f"video_{video.id}.csv"

            ocr_file_path = os.path.join(settings.MEDIA_ROOT, 'ocr_transcripts', course_dir, filename)
            ocr_file_exists = os.path.exists(ocr_file_path)

            # Logic:
            # - If NO DB data -> Reset status to 'pending' (allows retry)
            # - If DB + File exist -> Mark 'complete'
            # - If DB exists but File missing -> Reset to 'pending' (something is wrong)
            
            if not ocr_db_exists:
                should_reset = False
                
                if video.ocr_transcript_status != 'pending':
                    video.ocr_transcript_status = 'pending'
                    should_reset = True
                
                # If no OCR text, we can't have an index, so reset index to pending (or none)
                if video.ocr_index_status != 'pending':
                    video.ocr_index_status = 'pending' 
                    should_reset = True
                
                if should_reset:
                    self.stdout.write(self.style.WARNING(f"  No OCR Transcripts (DB) for '{video.title}'. Resetting statuses to pending."))
                    changed = True
                    reset_count += 1
            
            elif ocr_db_exists and ocr_file_exists:
                if video.ocr_transcript_status != 'complete':
                    video.ocr_transcript_status = 'complete'
                    changed = True
            
            else:
                # DB exists, but file is missing
                if video.ocr_transcript_status in ['processing', 'complete', 'failed']:
                    if not ocr_file_exists:
                        reason = f"File missing at {course_dir}/{filename}"
                    else:
                        reason = "Unknown"

                    self.stdout.write(self.style.WARNING(f"  Resetting OCR Transcript for '{video.title}': {reason} -> 'pending'"))
                    video.ocr_transcript_status = 'pending'
                    changed = True
                    reset_count += 1

            # ==========================================
            # 3. Sync Standard FAISS Index Status (Audio)
            # ==========================================
            std_index_path = ""
            std_index_exists = False

            if platform_id:
                std_index_path = os.path.join(settings.FAISS_INDEX_ROOT, 'transcripts', platform_id)
                if os.path.exists(std_index_path) and os.path.exists(os.path.join(std_index_path, 'index.faiss')):
                    std_index_exists = True

            if std_index_exists:
                if video.index_status != 'complete':
                    video.index_status = 'complete'
                    changed = True
            else:
                if video.index_status in ['indexing', 'complete', 'failed']:
                    self.stdout.write(self.style.WARNING(f"  Resetting Standard Index for '{video.title}': Files missing -> 'none'"))
                    video.index_status = 'none'
                    changed = True
                    reset_count += 1

            # ==========================================
            # 4. Sync OCR FAISS Index Status
            # ==========================================
            ocr_index_exists = False
            ocr_index_path = ""
            
            if platform_id:
                ocr_index_path = os.path.join(settings.FAISS_INDEX_ROOT, 'ocr', platform_id)
                if os.path.exists(ocr_index_path) and os.path.exists(os.path.join(ocr_index_path, 'index.faiss')):
                    ocr_index_exists = True

            # Clean up Orphaned Index (Files exist, but DB data is gone - e.g. after a wipe)
            if ocr_index_exists and not ocr_db_exists:
                self.stdout.write(self.style.WARNING(f"  Orphaned OCR Index found for '{video.title}' (No DB transcripts). Deleting index..."))
                try:
                    shutil.rmtree(ocr_index_path)
                    self.stdout.write(self.style.SUCCESS("    - Index deleted successfully."))
                    
                    ocr_index_exists = False
                    video.ocr_transcript_status = 'pending'
                    video.ocr_index_status = 'pending'
                    changed = True
                    reset_count += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"    - Failed to delete orphaned index: {e}"))

            # Sync Status based on file existence
            if ocr_index_exists:
                if video.ocr_index_status != 'complete':
                    video.ocr_index_status = 'complete'
                    changed = True
            else:
                if video.ocr_index_status in ['indexing', 'complete', 'failed']:
                    # Use 'pending' if no index exists, so the system knows to try generating it
                    if video.ocr_index_status != 'pending':
                        self.stdout.write(self.style.WARNING(f"  Resetting OCR Index for '{video.title}': Files missing -> 'pending'"))
                        video.ocr_index_status = 'pending'
                        changed = True
                        reset_count += 1

            if changed:
                video.save(update_fields=[
                    'transcript_status', 
                    'ocr_transcript_status', 
                    'index_status', 
                    'ocr_index_status'
                ])
                updated_count += 1

        self.stdout.write(self.style.SUCCESS(f"\n-----------------------------------"))
        self.stdout.write(self.style.SUCCESS(f"Sync Finished."))
        self.stdout.write(self.style.SUCCESS(f"Updated/Synced: {updated_count} videos"))
        self.stdout.write(self.style.WARNING(f"Reset (Ready to Retry): {reset_count} videos"))
        self.stdout.write(self.style.SUCCESS(f"-----------------------------------"))