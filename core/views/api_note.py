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
        
        # --- NEW: Re-build note index ---
        try:
            logger.info(f"Re-building note index for user {request.user.id}, video {video.youtube_id} after adding note.")
            # --- CORRECTED FUNCTION CALL ---
            # Pass the video object and user object
            update_video_notes_index(video, request.user)
        except Exception as e:
            logger.error(f"Failed to re-build note index after adding note: {e}", exc_info=True)
        # --- End of new code ---
            
        note_card_html = render_to_string(
            'core/components/video_player/_note_card.html',
            {'note': note}
        )
        return JsonResponse({
            'status': 'success',
            'note_card_html': note_card_html,
        })
    return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)

@login_required
@require_POST
def edit_note_view(request, note_id):
    note = get_object_or_404(Note, id=note_id, user=request.user)
    
    try:
        data = json.loads(request.body)
        new_title = data.get('title')
        new_content = data.get('content')

        if new_content and new_title:
            note.title = new_title
            note.content = new_content
            note.save() 

            # --- NEW: Re-build note index ---
            try:
                logger.info(f"Re-building note index for user {request.user.id}, video {note.video.youtube_id} after editing note.")
                # --- CORRECTED FUNCTION CALL ---
                # Pass the video object and user object
                update_video_notes_index(note.video, request.user)
            except Exception as e:
                logger.error(f"Failed to re-build note index after editing note: {e}", exc_info=True)
            # --- End of new code ---
            
            return JsonResponse({
                'status': 'success',
                'note': {
                    'id': note.id,
                    'title': note.title,
                    'content': note.content,
                    'video_timestamp': note.video_timestamp 
                }
            })
        
        return JsonResponse({'status': 'error', 'message': 'Title and content cannot be empty.'}, status=400)
    
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required
@require_POST
def delete_note_view(request, note_id):
    note = get_object_or_404(Note, id=note_id, user=request.user)
    
    # --- Store video and user *before* deleting ---
    video_to_update = note.video
    user_to_update = request.user
    
    note.delete()
    
    # --- NEW: Re-build note index ---
    try:
        logger.info(f"Re-building note index for user {user_to_update.id}, video {video_to_update.youtube_id} after deleting note.")
        # --- CORRECTED FUNCTION CALL ---
        # Pass the video object and user object
        update_video_notes_index(video_to_update, user_to_update)
    except Exception as e:
        logger.error(f"Failed to re-build note index after deleting note: {e}", exc_info=True)
    # --- End of new code ---
    
    return JsonResponse({'status': 'success', 'message': 'Note deleted successfully.'})