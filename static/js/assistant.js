import * as DomUtils from "./modules/assistant-dom.js";
import * as State from "./modules/assistant-state.js";
import * as Api from "./modules/assistant-api.js";

const InCuiseNixAssistant = window.InCuiseNixAssistant || {};

InCuiseNixAssistant.appendMessage = DomUtils.appendMessage;
InCuiseNixAssistant.clearChatBox = DomUtils.clearChatBox;
InCuiseNixAssistant.toggleHistoryView = DomUtils.toggleHistoryView;
InCuiseNixAssistant.setActiveConversation = State.setActiveConversation;
InCuiseNixAssistant.getState = State.getState;

function resetTextarea(inputEl, buttonEl) {
  if (inputEl) {
    inputEl.value = "";
    inputEl.style.height = "auto";
  }
  if (buttonEl) {
    buttonEl.disabled = true;
  }
}

InCuiseNixAssistant.resetChat = function () {
  State.resetCurrentConversation();
  DomUtils.clearChatBox();
  DomUtils.appendMessage(
    "Hi! How can I help you with this video?",
    "assistant"
  );
  DomUtils.toggleHistoryView(false);
  
  const assistantInput = document.getElementById("assistant-input");
  const assistantSendBtn = document.getElementById("assistant-send-btn");
  resetTextarea(assistantInput, assistantSendBtn);
};

window.InCuiseNixAssistant = InCuiseNixAssistant;

document.addEventListener("DOMContentLoaded", function () {
  const assistantForm = document.getElementById("assistant-form");
  const newChatButton = document.getElementById("assistant-new-chat-btn");
  const assistantChat = document.getElementById("assistantOffcanvas");

  const assistantInput = document.getElementById("assistant-input");
  const assistantSendBtn = document.getElementById("assistant-send-btn");
  const loadingTemplate = document.getElementById("assistant-loading-template");

  if (assistantForm && assistantInput && assistantSendBtn && loadingTemplate) {
    assistantForm.addEventListener("submit", (event) => {
      event.preventDefault();
      
      const query = assistantInput.value.trim();
      if (!query) {
        return;
      }

      if (!document.getElementById("assistant-loading-msg")) {
        const loadingEl = loadingTemplate.content.firstElementChild.cloneNode(true);
        loadingEl.id = "assistant-loading-msg";
        
        if (typeof DomUtils.appendElementToChatBox === "function") {
            DomUtils.appendElementToChatBox(loadingEl); 
        } else {
            document.getElementById("assistant-chat-box").appendChild(loadingEl);
        }

        if (typeof DomUtils.scrollToBottom === "function") {
            DomUtils.scrollToBottom();
        }
      }
      
      const timestamp = window.videoPlayer ? window.videoPlayer.currentTime : 0;
      Api.submitQuery(query, timestamp);
      
      resetTextarea(assistantInput, assistantSendBtn);
    });
  }

  if (assistantInput && assistantSendBtn) {
    assistantInput.addEventListener("input", () => {
      const isInputEmpty = assistantInput.value.trim() === "";
      assistantSendBtn.disabled = isInputEmpty;

      assistantInput.style.height = "auto";
      assistantInput.style.height = `${assistantInput.scrollHeight}px`;
    });
  }

  if (assistantInput && assistantForm && assistantSendBtn) {
      assistantInput.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && !event.shiftKey) {
          event.preventDefault();
          if (!assistantSendBtn.disabled) {
            assistantForm.dispatchEvent(new Event("submit", { cancelable: true, bubbles: true }));
          }
        }
      });
  }

  if (newChatButton) {
    newChatButton.addEventListener("click", () => {
      InCuiseNixAssistant.resetChat();
      const timestamp = window.videoPlayer ? window.videoPlayer.currentTime : 0;
      Api.submitQuery(null, timestamp, { forceNew: true });
    });
  }

  if (assistantChat) {
    assistantChat.addEventListener("show.bs.offcanvas", function () {
      DomUtils.toggleHistoryView(false);

      const newVideoId = assistantChat.dataset.videoId;
      const currentState = State.getState();

      if (newVideoId && newVideoId !== currentState.currentVideoId) {
        State.setActiveConversation(
          newVideoId,
          State.getConversationForVideo(newVideoId)
        );
        DomUtils.clearChatBox();
        DomUtils.appendMessage(
          "Hi! How can I help you with this video?",
          "assistant"
        );
      } else {
        DomUtils.toggleHistoryView(false);
      }
      
      const assistantInput = document.getElementById("assistant-input");
      const assistantSendBtn = document.getElementById("assistant-send-btn");
      resetTextarea(assistantInput, assistantSendBtn);
    });
  }
});