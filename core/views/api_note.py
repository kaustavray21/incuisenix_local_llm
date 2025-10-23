import json
import logging
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

from ..forms import NoteForm
from ..models import Note, Video
# --- Import is correct ---
from ..rag.index_notes import update_video_notes_index

logger = logging.getLogger(__name__)

@login_required
@require_POST
def add_note_view(request, video_id):
    video = get_object_or_404(Video, id=video_id)
    form = NoteForm(request.POST)
    if form.is_valid():
        note = form.save(commit=False)
        note.user = request.user
        note.video = video
        note.course = video.course
        note.save()

        # Re-build note index
        try:
            logger.info(f"Re-building note index for user {request.user.id}, video {video.youtube_id} after adding note.")
            update_video_notes_index(video, request.user)
        except Exception as e:
            logger.error(f"Failed to re-build note index after adding note: {e}", exc_info=True)

        note_card_html = render_to_string(
            'core/components/video_player/_note_card.html',
            {'note': note}
        )
        return JsonResponse({
            'status': 'success',
            'note_card_html': note_card_html,
        })
    # If form is invalid, return errors
    return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)

@login_required
@require_POST
def edit_note_view(request, note_id):
    note = get_object_or_404(Note, id=note_id, user=request.user)
    
    # *** THIS IS THE FIX ***
    # Use the NoteForm to handle the POST data and update the instance
    form = NoteForm(request.POST, instance=note)
    
    if form.is_valid():
        updated_note = form.save() # Save the changes

        # Re-build note index
        try:
            logger.info(f"Re-building note index for user {request.user.id}, video {updated_note.video.youtube_id} after editing note.")
            update_video_notes_index(updated_note.video, request.user)
        except Exception as e:
            logger.error(f"Failed to re-build note index after editing note: {e}", exc_info=True)
            
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

    video_to_update = note.video
    user_to_update = request.user

    note.delete()

    # Re-build note index
    try:
        logger.info(f"Re-building note index for user {user_to_update.id}, video {video_to_update.youtube_id} after deleting note.")
        update_video_notes_index(video_to_update, user_to_update)
    except Exception as e:
        logger.error(f"Failed to re-build note index after deleting note: {e}", exc_info=True)

    return JsonResponse({'status': 'success', 'message': 'Note deleted successfully.'})