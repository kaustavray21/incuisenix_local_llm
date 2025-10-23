// static/js/assistant.js - Main Orchestrator

// Import module functions
import * as DomUtils from "./modules/assistant-dom.js";
import * as State from "./modules/assistant-state.js";
import * as Api from "./modules/assistant-api.js";
// Utils are used internally by other modules, no direct import needed here usually

// --- Create and Populate the Global Namespace ---
// Create a local object to hold the API
const InCuiseNixAssistant = window.InCuiseNixAssistant || {};

InCuiseNixAssistant.appendMessage = DomUtils.appendMessage;
InCuiseNixAssistant.clearChatBox = DomUtils.clearChatBox;
InCuiseNixAssistant.toggleHistoryView = DomUtils.toggleHistoryView;
InCuiseNixAssistant.setActiveConversation = State.setActiveConversation;
InCuiseNixAssistant.getState = State.getState;

// The original resetChat logic now needs to interact with both State and DOM
InCuiseNixAssistant.resetChat = function () {
  State.resetCurrentConversation(); // Reset state
  // Clear screen and show initial message
  DomUtils.clearChatBox();
  DomUtils.appendMessage(
    "Hi! How can I help you with this video?",
    "assistant"
  );
  DomUtils.toggleHistoryView(false); // Ensure main view is shown
  // Optionally trigger API to start a new conversation on the backend
  // const timestamp = window.videoPlayer ? window.videoPlayer.currentTime : 0;
  // Api.submitQuery(null, timestamp, { forceNew: true });
};

// *** THIS IS THE FIX ***
// Explicitly attach the populated object to the global window scope
// so that other non-module scripts (like assistant_history.js) can find it.
window.InCuiseNixAssistant = InCuiseNixAssistant;

// --- Main Initialization ---
document.addEventListener("DOMContentLoaded", function () {
  // Get elements needed ONLY for event listeners in this main file
  const assistantForm = document.getElementById("assistant-form");
  const newChatButton = document.getElementById("assistant-new-chat-btn");
  const assistantChat = document.getElementById("assistantOffcanvas");

  // --- Event Listeners ---

  if (assistantForm) {
    assistantForm.addEventListener("submit", (event) => {
      event.preventDefault(); // Prevent default form submission
      const query = DomUtils.getAssistantInputValue(); // Get value via DOM module
      const timestamp = window.videoPlayer ? window.videoPlayer.currentTime : 0;
      Api.submitQuery(query, timestamp); // Call API module function
    });
  }

  if (newChatButton) {
    newChatButton.addEventListener("click", () => {
      console.log("Main: New Chat button clicked.");
      // Use the globally exposed resetChat function
      InCuiseNixAssistant.resetChat();
      // Optionally trigger API to start a new conversation on the backend
      const timestamp = window.videoPlayer ? window.videoPlayer.currentTime : 0;
      Api.submitQuery(null, timestamp, { forceNew: true }); // Use null query to force "Start"
    });
  }

  if (assistantChat) {
    assistantChat.addEventListener("show.bs.offcanvas", function () {
      // DOM elements are now fetched lazily by the DOM module when needed.
      // Ensure the main view is shown initially
      DomUtils.toggleHistoryView(false);

      const newVideoId = assistantChat.dataset.videoId;
      const currentState = State.getState();

      if (newVideoId !== currentState.currentVideoId) {
        console.log(
          `Main: Video changed from ${currentState.currentVideoId} to ${newVideoId}`
        );
        // Update state for the new video
        State.setActiveConversation(
          newVideoId,
          State.getConversationForVideo(newVideoId)
        );
        // Clear screen for the new video context
        DomUtils.clearChatBox();
        DomUtils.appendMessage(
          "Hi! How can I help you with this video?",
          "assistant"
        );
      } else {
        console.log(
          `Main: Resuming chat for video ${currentState.currentVideoId}`
        );
        // Ensure main view is visible if resuming
        DomUtils.toggleHistoryView(false);
      }
    });
  }

  // Initial setup message if needed (might be redundant with offcanvas logic)
  // DomUtils.appendMessage("Hi! How can I help you with this video?", 'assistant');
});