# Standard library imports
import json
import logging

# Django imports
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

# Django REST Framework imports
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

# Local application imports
from ..forms import NoteForm
from ..models import (Conversation, ConversationMessage, Course, Enrollment,
                    Note, Transcript, Video)
# UPDATED IMPORT: We now use the query_router from the robust utils file
from ..rag.utils import query_router
from ..serializers import ConversationMessageSerializer, ConversationSerializer

logger = logging.getLogger(__name__)

# --- Standard Django Views (No Changes) ---

@login_required
@require_POST
def enroll_view(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    Enrollment.objects.get_or_create(user=request.user, course=course)
    return redirect('dashboard')

@login_required
def roadmap_view(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    if not Enrollment.objects.filter(user=request.user, course=course).exists():
        return JsonResponse({'error': 'You are not enrolled in this course.'}, status=403)
    course_data = {
        'title': course.title,
        'description': course.description
    }
    return JsonResponse(course_data)

# --- Note API Views (No Changes) ---

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
    data = json.loads(request.body)
    new_title = data.get('title')
    new_content = data.get('content')

    if new_content and new_title:
        note.title = new_title
        note.content = new_content
        note.save()
        return JsonResponse({'status': 'success', 'message': 'Note updated successfully.'})
    
    return JsonResponse({'status': 'error', 'message': 'Title and content cannot be empty.'}, status=400)

@login_required
@require_POST
def delete_note_view(request, note_id):
    note = get_object_or_404(Note, id=note_id, user=request.user)
    note.delete()
    return JsonResponse({'status': 'success', 'message': 'Note deleted successfully.'})

# --- Transcript API View (No Changes) ---

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

# --- DRF API Views (Corrected and Updated) ---

class AssistantAPIView(APIView):
    """
    API View to handle queries to the AI assistant.
    Uses a router to delegate to the appropriate chain.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        query = request.data.get('query')
        youtube_video_id = request.data.get('video_id')
        # Get the current video timestamp from the frontend for context
        timestamp = float(request.data.get('timestamp', 0))

        if not query or not youtube_video_id:
            return Response(
                {'error': 'Query and video_id are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            video = get_object_or_404(Video, youtube_id=youtube_video_id)
            conversation, created = Conversation.objects.get_or_create(
                user=request.user, course=video.course, video=video
            )

            previous_messages = conversation.messages.order_by('created_at')
            chat_history = "\n".join([f"Human: {m.question}\nAI: {m.answer}" for m in previous_messages])
            
            notes = Note.objects.filter(user=request.user, video=video)
            notes_context = "\n".join([f"- {note.title}: {note.content}" for note in notes])

            # *** UPDATED LOGIC: Call the new, robust query router ***
            answer = query_router(
                query=query,
                video_id=youtube_video_id,
                timestamp=timestamp,
                chat_history=chat_history,
                notes=notes_context
            )

            # Save the new message to the conversation
            ConversationMessage.objects.create(
                conversation=conversation, question=query, answer=answer
            )

            return Response({'answer': answer}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"An error occurred in AssistantAPIView: {e}", exc_info=True)
            return Response(
                {'error': 'An error occurred while processing your request.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# --- Conversation Views (No Changes) ---

class ConversationListView(ListAPIView):
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Conversation.objects.filter(user=self.request.user).order_by('-created_at')

class ConversationDetailView(RetrieveAPIView):
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]
    queryset = Conversation.objects.all()
    lookup_field = 'id'
