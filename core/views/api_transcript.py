import logging
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, Http404
from ..models import Transcript, Video

logger = logging.getLogger(__name__)

@login_required
def get_transcript_view(request, video_id):
    logger.info(f"API Request: Fetching transcript for video_id string: '{video_id}'")
    try:
        video = get_object_or_404(
            Video,
            Q(youtube_id=video_id) | Q(vimeo_id=video_id)
        )
        logger.info(f"Found video object with DB ID: {video.pk} for platform ID: '{video_id}'")

        transcripts = Transcript.objects.filter(video=video).order_by('start')

        if not transcripts.exists():
            logger.warning(f"No transcript lines found in DB for video {video.pk} ('{video_id}')")
            return JsonResponse([], safe=False)

        data = [{'start': t.start, 'content': t.content} for t in transcripts]
        logger.info(f"Returning {len(data)} transcript lines for video {video.pk} ('{video_id}')")
        return JsonResponse(data, safe=False)

    except Http404:
        logger.error(f"Video with youtube_id or vimeo_id '{video_id}' not found.")
        return JsonResponse({'error': f"Video with ID '{video_id}' not found."}, status=404)

    except Exception as e:
        logger.error(f"Error fetching transcript for video platform ID '{video_id}': {e}", exc_info=True)
        return JsonResponse({'error': 'An internal server error occurred.'}, status=500)