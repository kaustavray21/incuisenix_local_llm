// static/js/modules/assistant-dom.js

// Initialize showdown converter here
const converter = new showdown.Converter();

// Cache DOM elements internally
let chatBox = null;
let mainChatView = null;
let historyView = null;
let sendButton = null;
let assistantInput = null; // Added for clearing input

// Function to find elements on demand and cache them
function getElement(id) {
  let element = document.getElementById(id);
  if (!element) {
    console.error(`DOM element with ID "${id}" not found!`);
  }
  return element;
}

// Lazy getters for elements
function getChatBoxElement() {
  if (!chatBox) chatBox = getElement("assistant-chat-box");
  return chatBox;
}
function getMainChatViewElement() {
  if (!mainChatView) mainChatView = getElement("assistant-main-view");
  return mainChatView;
}
function getHistoryViewElement() {
  if (!historyView) historyView = getElement("assistant-history-view");
  return historyView;
}
function getSendButtonElement() {
  if (!sendButton) sendButton = getElement("assistant-send-btn");
  return sendButton;
}
function getAssistantInputElement() {
  if (!assistantInput) assistantInput = getElement("assistant-input");
  return assistantInput;
}

export function appendMessage(message, sender) {
  const box = getChatBoxElement();
  if (!box) return; // Guard if element not found

  if (!message || String(message).trim() === "") {
    console.warn("DOM: Attempted to append an empty message.");
    return;
  }

  const messageElement = document.createElement("div");
  messageElement.classList.add("chat-message", sender);

  if (sender === "assistant") {
    const htmlContent = converter.makeHtml(String(message));
    messageElement.innerHTML = htmlContent;
  } else {
    messageElement.textContent = message;
  }

  box.appendChild(messageElement);
  box.scrollTop = box.scrollHeight;
}

export function clearChatBox() {
  const box = getChatBoxElement();
  if (box) {
    box.innerHTML = "";
  } else {
    console.error("DOM: Chat box element not found! Cannot clear.");
  }
}

export function showLoadingIndicator() {
  const btn = getSendButtonElement();
  if (btn) btn.disabled = true;

  const box = getChatBoxElement();
  if (!box) return; // Guard

  // Remove existing indicator just in case
  removeLoadingIndicator();

  const loadingElement = document.createElement("div");
  loadingElement.classList.add("chat-message", "loading");
  loadingElement.id = "loading-indicator"; // Keep ID for easy removal
  loadingElement.innerHTML = `
        <div class="d-flex align-items-center">
            <strong class="me-2">Assistant is thinking...</strong>
            <div class="spinner-border spinner-border-sm" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
        </div>
    `;
  box.appendChild(loadingElement);
  box.scrollTop = box.scrollHeight;
}

export function removeLoadingIndicator() {
  const btn = getSendButtonElement();
  if (btn) btn.disabled = false;

  const loadingElement = document.getElementById("loading-indicator");
  if (loadingElement) {
    loadingElement.remove();
  }
}

export function toggleHistoryView(showHistory) {
  const mainView = getMainChatViewElement();
  const histView = getHistoryViewElement();
  if (!mainView || !histView) return; // Guard

  if (showHistory) {
    mainView.style.display = "none";
    histView.style.display = "flex";
  } else {
    mainView.style.display = "flex";
    // *** THIS IS THE FIX ***
    // Add flex-direction to ensure vertical layout of chatbox and form
    mainView.style.flexDirection = "column";
    histView.style.display = "none";
  }
}

export function clearAssistantInput() {
  const input = getAssistantInputElement();
  if (input) {
    input.value = "";
  }
}

export function getAssistantInputValue() {
  const input = getAssistantInputElement();
  return input ? input.value.trim() : "";
}