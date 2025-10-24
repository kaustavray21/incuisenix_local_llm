import * as api from "./modules/note-api.js";
import * as ui from "./modules/note-ui.js";
import { formatTimestamp } from "./modules/utils.js";

document.addEventListener("DOMContentLoaded", function () {
  const addNoteModalEl = document.getElementById("addNoteModal");
  const addNoteModal = new bootstrap.Modal(addNoteModalEl);
  const addNoteForm = document.getElementById("add-note-form");

  const editNoteModalEl = document.getElementById("editNoteModal");
  const editNoteModal = new bootstrap.Modal(editNoteModalEl);
  const editNoteForm = document.getElementById("edit-note-form");

  const notesListContainer = document.getElementById("notes-list-container");
  const notePopupOverlay = document.getElementById("note-popup-overlay");
  const popupCloseBtn = document.getElementById("popup-close-btn");

  if (addNoteForm) {
    addNoteForm.addEventListener("submit", async function (event) {
      event.preventDefault();
      const videoId = document.getElementById("player-data-container").dataset
        .videoId;
      const formData = new FormData(this);

      try {
        const data = await api.addNote(videoId, formData);
        if (data.status === "success") {
          ui.addNoteToUI(data.note_card_html);
          addNoteForm.reset();
          addNoteModal.hide();
        } else {
          console.error("Failed to add note:", data.errors);
        }
      } catch (error) {
        console.error("Error submitting form:", error);
      }
    });
  }

  if (editNoteForm) {
    editNoteForm.addEventListener("submit", async function (event) {
      event.preventDefault();
      const noteId = document.getElementById("edit-note-id").value;
      const formData = new FormData(this);

      try {
        const data = await api.editNote(noteId, formData);
        if (data.status === "success") {
          ui.updateNoteInUI(data.note);
          editNoteModal.hide();
        } else {
          console.error("Failed to update note:", data.errors);
        }
      } catch (error) {
        console.error("Error updating note:", error);
      }
    });
  }

  if (notesListContainer) {
    notesListContainer.addEventListener("click", async function (event) {
      const target = event.target;
      const noteCard = target.closest(".note-card");

      if (!noteCard) return;

      const editButton = target.closest(".note-btn-edit");
      const deleteButton = target.closest(".note-btn-delete");
      const noteId = noteCard.dataset.noteId;

      if (editButton) {
        ui.populateEditModal(noteCard);
      } else if (deleteButton) {
        if (confirm("Are you sure you want to delete this note?")) {
          try {
            const data = await api.deleteNote(noteId);
            if (data.status === "success") {
              noteCard.remove();
            } else {
              console.error("Failed to delete note:", data.message);
            }
          } catch (error) {
            console.error("Error deleting note:", error);
          }
        }
      } else {
        const note = {
          id: noteCard.dataset.noteId,
          title: noteCard.dataset.noteTitle,
          content: noteCard.dataset.noteContent,
          timestamp: noteCard.dataset.noteTimestamp,
        };

        ui.showNotePopup(note);
      }
    });
  }

  if (popupCloseBtn) {
    popupCloseBtn.addEventListener("click", () => {
      notePopupOverlay.style.display = "none";
    });
  }
  if (notePopupOverlay) {
    notePopupOverlay.addEventListener("click", (event) => {
      if (event.target === notePopupOverlay) {
        notePopupOverlay.style.display = "none";
      }
    });
  }

  if (addNoteModalEl) {
    addNoteModalEl.addEventListener("show.bs.modal", function () {
      if (
        window.videoPlayer &&
        typeof window.videoPlayer.currentTime === "number"
      ) {
        const currentTime = Math.round(window.videoPlayer.currentTime);
        document.getElementById("id_video_timestamp").value = currentTime;
      }
    });
  }
});
