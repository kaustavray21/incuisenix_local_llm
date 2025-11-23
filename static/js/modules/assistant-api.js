import { getCookie } from "./assistant-utils.js";
import * as DomUtils from "./assistant-dom.js";
import * as State from "./assistant-state.js";

const csrfToken = getCookie("csrftoken");
const ASSISTANT_API_URL = "/api/assistant/";

function removeLoadingIndicator() {
  const loadingEl = document.getElementById("assistant-loading-msg");
  if (loadingEl) {
    loadingEl.remove();
  }
}

// --- UPDATED: Added 'export' keyword here ---
export function parseMarkdown(text) {
  if (window.marked && typeof window.marked.parse === "function") {
    return window.marked.parse(text);
  } else {
    console.warn("Marked.js not loaded. Code blocks will not be formatted.");
    return text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;")
      .replace(/\n/g, "<br>");
  }
}

export async function submitQuery(query, timestamp, options = {}) {
  if (!query && !options.forceNew) return;

  const effectiveQuery = query || "Start";

  if (!options.forceNew && query) {
    DomUtils.appendMessage(query, "user");
  }

  const currentState = State.getState();

  const requestData = {
    query: effectiveQuery,
    video_id: currentState.currentVideoId,
    timestamp: timestamp,
    conversation_id: currentState.currentConversationId,
  };
  if (options.forceNew) {
    requestData.force_new = true;
  }

  try {
    const response = await fetch(ASSISTANT_API_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken,
      },
      body: JSON.stringify(requestData),
    });

    removeLoadingIndicator();

    if (!response.ok) {
      const errorData = await response.json();
      const errorMessage =
        errorData.error ||
        `An unexpected error occurred. Status: ${response.status}`;
      throw new Error(errorMessage);
    }

    const data = await response.json();

    if (data.answer) {
      if (!options.forceNew || effectiveQuery !== "Start") {
        const htmlAnswer = parseMarkdown(data.answer);
        DomUtils.appendMessage(htmlAnswer, "assistant");
      }

      if (data.conversation_id && currentState.currentVideoId) {
        State.setActiveConversation(
          currentState.currentVideoId,
          data.conversation_id
        );
      }
    } else {
      DomUtils.appendMessage(
        "Sorry, an error occurred. The assistant did not provide a valid answer.",
        "assistant"
      );
    }
  } catch (error) {
    console.error("API Error:", error);
    removeLoadingIndicator();
    DomUtils.appendMessage(
      `Sorry, an error occurred: ${error.message}`,
      "assistant"
    );
  }
}