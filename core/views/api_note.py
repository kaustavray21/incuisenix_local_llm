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
# Ensure this import path is correct for your project structure
from ..rag.index_notes import update_video_notes_index

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

        # Re-build note index
        try:
            # Get the platform ID (YT or Vimeo) for clearer logging
            platform_id = video.youtube_id or video.vimeo_id
            logger.info(f"Re-building note index for user {request.user.id}, video platform_id {platform_id} (DB ID: {video.pk}) after adding note.")
            update_video_notes_index(video, request.user)
        except Exception as e:
            logger.error(f"Failed to re-build note index after adding note {note.id}: {e}", exc_info=True)

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

        # Re-build note index
        try:
            # Get the platform ID (YT or Vimeo) for clearer logging
            platform_id = updated_note.video.youtube_id or updated_note.video.vimeo_id
            logger.info(f"Re-building note index for user {request.user.id}, video platform_id {platform_id} (DB ID: {updated_note.video.pk}) after editing note.")
            update_video_notes_index(updated_note.video, request.user)
        except Exception as e:
            logger.error(f"Failed to re-build note index after editing note {note_id}: {e}", exc_info=True)
                
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

    # Store related objects before deleting the note
    video_to_update = note.video
    user_to_update = request.user

    note.delete()

    # Re-build note index
    try:
        # Get the platform ID (YT or Vimeo) for clearer logging
        platform_id = video_to_update.youtube_id or video_to_update.vimeo_id
        logger.info(f"Re-building note index for user {user_to_update.id}, video platform_id {platform_id} (DB ID: {video_to_update.pk}) after deleting note.")
        update_video_notes_index(video_to_update, user_to_update)
    except Exception as e:
        logger.error(f"Failed to re-build note index after deleting note {note_id}: {e}", exc_info=True)

    return JsonResponse({'status': 'success', 'message': 'Note deleted successfully.'})