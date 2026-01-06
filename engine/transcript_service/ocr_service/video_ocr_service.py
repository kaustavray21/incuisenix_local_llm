import logging
import os
import csv
from typing import List, Dict
from django.conf import settings
from core.models import Video, OCRTranscript
from .frame_extractor import FrameExtractor
from .ocr_extractor import OCRExtractor
from .text_processor import TextProcessor
from .ocr_downloader import VideoDownloader
from engine.transcript_service.utils import sanitize_filename

logger = logging.getLogger(__name__)

class VideoOCRService:
    def __init__(self, sample_rate: int = 2):
        self.frame_extractor = FrameExtractor(sample_rate=sample_rate)
        # Use GPU=False for local CPU compatibility, change to True if you have CUDA setup
        self.ocr_extractor = OCRExtractor(lang='en', use_gpu=False) 
        self.text_processor = TextProcessor(min_similarity=0.85)
        self.downloader = VideoDownloader()
        
        # Base directory
        self.ocr_root_dir = os.path.join(settings.MEDIA_ROOT, 'ocr_transcripts')
        if not os.path.exists(self.ocr_root_dir):
            os.makedirs(self.ocr_root_dir)

    def _save_to_csv(self, video, unique_entries: List[Dict]):
        """
        Saves OCR results to a CSV.
        Organizes files into subfolders by Course Name.
        """
        # 1. Determine Filename (ID preferred)
        platform_id = video.vimeo_id or video.youtube_id
        if platform_id:
            filename = f"{platform_id}.csv"
        else:
            filename = f"video_{video.id}.csv"
            
        # 2. Determine Folder (Course Name)
        if video.course:
            course_dir_name = sanitize_filename(video.course.title)
        else:
            course_dir_name = "Uncategorized"
            
        final_dir = os.path.join(self.ocr_root_dir, course_dir_name)
        os.makedirs(final_dir, exist_ok=True)
        
        file_path = os.path.join(final_dir, filename)
        
        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['start', 'content'])
                for entry in unique_entries:
                    writer.writerow([entry['start'], entry['content']])
            logger.info(f"VideoOCRService: CSV saved at {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"VideoOCRService: Failed to write CSV {filename}: {e}")
            return None

    def _consolidate_segments(self, raw_segments: List[Dict]) -> List[Dict]:
        """
        Deduplicates consecutive frames containing the same text.
        Uses the TextProcessor logic to check for similarity.
        """
        if not raw_segments: 
            return []
            
        consolidated = []
        current = raw_segments[0]
        
        for i in range(1, len(raw_segments)):
            nxt = raw_segments[i]
            
            # Use shared text processor logic
            if not self.text_processor.is_similar(current['content'], nxt['content']):
                consolidated.append(current)
                current = nxt
                
        consolidated.append(current)
        return consolidated

    def process_video(self, video_id: int) -> bool:
        temp_video_path = None
        try:
            video = Video.objects.get(id=video_id)
            video_path = None
            
            # --- Robust URL Construction ---
            target_url = video.video_url
            if not target_url:
                if video.vimeo_id:
                    target_url = f"https://vimeo.com/{video.vimeo_id}"
                elif video.youtube_id:
                    target_url = f"https://www.youtube.com/watch?v={video.youtube_id}"
            
            logger.info(f"VideoOCRService: Processing Video {video.id} ({video.title}). Target: {target_url}")

            # --- Logic to handle local vs URL ---
            # 1. Check if it is a local file path that actually exists
            if target_url and os.path.exists(target_url):
                 logger.info(f"VideoOCRService: Found local file: {target_url}")
                 video_path = target_url
                 
            # 2. If it looks like a URL, download it
            elif target_url and ("http" in target_url or "vimeo" in target_url or "youtube" in target_url):
                 logger.info(f"VideoOCRService: Downloading from URL...")
                 video_path = self.downloader.download_video(target_url)
                 temp_video_path = video_path 
            
            # 3. If we still don't have a path, we can't proceed
            if not video_path or not os.path.exists(video_path):
                 logger.error(f"VideoOCRService: Could not resolve video file. Target URL was: {target_url}")
                 return False

            # --- Start OCR Extraction ---
            logger.info(f"VideoOCRService: Starting frame extraction and OCR...")

            raw_segments = []
            frame_count = 0
            
            # Generator yields (timestamp, frame_image)
            for timestamp, frame in self.frame_extractor.extract_frames(video_path):
                text = self.ocr_extractor.extract_text(frame, preprocess=False)
                if text.strip():
                    cleaned_text = self.text_processor.clean_text(text)
                    if cleaned_text:
                        raw_segments.append({'start': timestamp, 'content': cleaned_text})
                frame_count += 1
                if frame_count % 10 == 0:
                    logger.debug(f"VideoOCRService: Processed {frame_count} frames...")

            logger.info(f"VideoOCRService: Extraction complete. {len(raw_segments)} raw segments found. Consolidating...")

            unique_entries = self._consolidate_segments(raw_segments)
            logger.info(f"VideoOCRService: Consolidation complete. {len(unique_entries)} unique text segments.")

            # 1. Database Update
            OCRTranscript.objects.filter(video=video).delete()
            
            entries_to_create = [
                OCRTranscript(
                    video=video,
                    course=video.course,
                    start=entry['start'],
                    content=entry['content'],
                    youtube_id=video.youtube_id,
                    vimeo_id=video.vimeo_id
                ) for entry in unique_entries
            ]
            OCRTranscript.objects.bulk_create(entries_to_create)
            logger.info(f"VideoOCRService: Saved {len(entries_to_create)} records to Database.")

            # 2. File System Update (CSV)
            self._save_to_csv(video, unique_entries)

            return True

        except Exception as e:
            logger.error(f"VideoOCRService: Critical Error for Video {video_id}: {str(e)}", exc_info=True)
            return False
            
        finally:
            if temp_video_path:
                self.downloader.cleanup(temp_video_path)