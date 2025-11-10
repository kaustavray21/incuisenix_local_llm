# core/api_note.py
import json
import logging
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
from django.db.models import Q

from ..forms import NoteForm
from ..models import Note, Video

logger = logging.getLogger(__name__)

@login_required
@require_POST
def add_note_view(request, video_id):
    # Use the string video_id (YT or Vimeo) to fetch the video
    video = get_object_or_404(
        Video,
        Q(youtube_id=video_id) | Q(vimeo_id=video_id)
    )
    
    form = NoteForm(request.POST)
    if form.is_valid():
        note = form.save(commit=False)
        note.user = request.user
        note.video = video
        note.course = video.course
        note.save()

        note_card_html = render_to_string(
            'core/components/video_player/_note_card.html',
            {'note': note}
        )
        return JsonResponse({
            'status': 'success',
            'note_card_html': note_card_html,
        })
    # If form is invalid, return errors
    logger.warning(f"Add note failed for video {video_id}: {form.errors}")
    return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)

@login_required
@require_POST
def edit_note_view(request, note_id):
    note = get_object_or_404(Note, id=note_id, user=request.user)
    
    # Use the NoteForm to handle the POST data and update the instance
    form = NoteForm(request.POST, instance=note)
    
    if form.is_valid():
        updated_note = form.save() # Save the changes
                
        return JsonResponse({
            'status': 'success',
            'note': {
                'id': updated_note.id,
                'title': updated_note.title,
                'content': updated_note.content,
                'video_timestamp': updated_note.video_timestamp
            }
        })
    else:
        # If form is invalid, return errors
        logger.warning(f"Edit note failed for note {note_id}: {form.errors}")
        return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)

@login_required
@require_POST
def delete_note_view(request, note_id):
    note = get_object_or_404(Note, id=note_id, user=request.user)

    note.delete()

    return JsonResponse({'status': 'success', 'message': 'Note deleted successfully.'})