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

// --- (NEW Step 3 & 6) Helper to reset textarea ---
function resetTextarea(inputEl, buttonEl) {
  if (inputEl) {
    inputEl.value = "";
    inputEl.style.height = "auto";
  }
  if (buttonEl) {
    buttonEl.disabled = true;
  }
}

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
  
  // --- (NEW Step 3 & 6) Also reset the input form ---
  const assistantInput = document.getElementById("assistant-input");
  const assistantSendBtn = document.getElementById("assistant-send-btn");
  resetTextarea(assistantInput, assistantSendBtn);
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

  // --- (NEW) Get elements for new UI features ---
  const assistantInput = document.getElementById("assistant-input");
  const assistantSendBtn = document.getElementById("assistant-send-btn");
  const loadingTemplate = document.getElementById("assistant-loading-template");


  // --- Event Listeners ---

  // --- (UPDATED) Form submit handler ---
  if (assistantForm && assistantInput && assistantSendBtn && loadingTemplate) {
    assistantForm.addEventListener("submit", (event) => {
      event.preventDefault(); // Prevent default form submission
      
      const query = assistantInput.value.trim();
      if (!query) {
        return; // Don't send empty messages
      }

      // --- (NEW Step 4) Show Typing Indicator ---
      // This check prevents multiple loading indicators
      if (!document.getElementById("assistant-loading-msg")) {
        const loadingEl = loadingTemplate.content.firstElementChild.cloneNode(true);
        loadingEl.id = "assistant-loading-msg"; // Give it an ID to find later
        
        // Use the DOM module to append the element and scroll
        if (typeof DomUtils.appendElementToChatBox === "function") {
            DomUtils.appendElementToChatBox(loadingEl); 
        } else {
            // Fallback if the function doesn't exist (it should)
            document.getElementById("assistant-chat-box").appendChild(loadingEl);
        }

        if (typeof DomUtils.scrollToBottom === "function") {
            DomUtils.scrollToBottom();
        }
      }
      
      // NOTE: The loading indicator MUST be removed by the Api.submitQuery 
      // function (or its callbacks) after the API call completes.
      // We are just adding it here.
      // --- END (Step 4) ---

      const timestamp = window.videoPlayer ? window.videoPlayer.currentTime : 0;
      Api.submitQuery(query, timestamp); // Call API module function
      
      // --- (NEW Step 3 & 6) Reset textarea and button after submit ---
      resetTextarea(assistantInput, assistantSendBtn);
    });
  }

  // --- (NEW Step 3 & 6) Listeners for auto-growing textarea and smart button ---
  if (assistantInput && assistantSendBtn) {
    assistantInput.addEventListener("input", () => {
      // --- (Step 6) Smarter Send Button ---
      const isInputEmpty = assistantInput.value.trim() === "";
      assistantSendBtn.disabled = isInputEmpty;

      // --- (Step 3) Auto-Growing Textarea ---
      assistantInput.style.height = "auto"; // Reset height to allow shrinking
      assistantInput.style.height = `${assistantInput.scrollHeight}px`; // Set to content height
    });
  }

  // --- (NEW) Listener for Enter-to-Submit ---
  if (assistantInput && assistantForm && assistantSendBtn) {
      assistantInput.addEventListener("keydown", (event) => {
        // Submit on Enter, but allow Shift+Enter for new line
        if (event.key === "Enter" && !event.shiftKey) {
          event.preventDefault();
          // Manually trigger the form's submit event if not disabled
          if (!assistantSendBtn.disabled) {
            assistantForm.dispatchEvent(new Event("submit", { cancelable: true, bubbles: true }));
          }
        }
      });
  }
  // --- END NEW ---


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
      
      // --- (NEW) Reset textarea on open ---
      const assistantInput = document.getElementById("assistant-input");
      const assistantSendBtn = document.getElementById("assistant-send-btn");
      resetTextarea(assistantInput, assistantSendBtn);
    });
  }

  // Initial setup message if needed (might be redundant with offcanvas logic)
  // DomUtils.appendMessage("Hi! How can I help you with this video?", 'assistant');
});