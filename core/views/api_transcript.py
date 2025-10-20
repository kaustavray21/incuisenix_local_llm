import logging
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from ..models import Transcript

logger = logging.getLogger(__name__)

@login_required
def get_transcript_view(request, video_id):
    logger.info(f"API Request: Fetching transcript for video_id: {video_id}")
    try:
        transcripts = Transcript.objects.filter(video_id=video_id).order_by('start')
        if not transcripts.exists():
            return JsonResponse([], safe=False)
        data = [{'start': t.start, 'content': t.content} for t in transcripts]
        return JsonResponse(data, safe=False)
    except Exception as e:
        logger.error(f"Error fetching transcript for video_id {video_id}: {e}", exc_info=True)
        return JsonResponse({'error': 'An error occurred.'}, status=500)