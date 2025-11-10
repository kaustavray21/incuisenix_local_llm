// static/js/modules/assistant-api.js

import { getCookie } from "./assistant-utils.js";
import * as DomUtils from "./assistant-dom.js"; // Use DomUtils for UI feedback
import * as State from "./assistant-state.js"; // Use State to get/set conversation details

const csrfToken = getCookie("csrftoken");
const ASSISTANT_API_URL = "/api/engine/assistant/";

/**
 * --- (NEW) ---
 * Helper function to safely remove the loading element.
 */
function removeLoadingIndicator() {
  const loadingEl = document.getElementById("assistant-loading-msg");
  if (loadingEl) {
    loadingEl.remove();
  }
}

/**
 * --- (NEW Step 5) ---
 * Helper function to parse Markdown, formatting code blocks.
 * @param {string} text - Raw text from the API.
 * @returns {string} - HTML-formatted string.
 */
function parseMarkdown(text) {
  // Assumes a Markdown library (like marked.js) is loaded on the window.
  if (window.marked && typeof window.marked.parse === "function") {
    // Sanitize to prevent XSS, though 'marked' is generally safe.
    // For enhanced security, consider adding DOMPurify:
    // if (window.DOMPurify) {
    //   return window.DOMPurify.sanitize(window.marked.parse(text));
    // }
    return window.marked.parse(text);
  } else {
    // Fallback if marked.js isn't loaded.
    // Manually escape HTML and convert newlines to <br>
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

/**
 * Sends a query to the assistant API and handles the response.
 * @param {string} query - The user's input query.
 * @param {number} timestamp - The current video timestamp.
 * @param {object} options - Additional options like forceNew.
 */
export async function submitQuery(query, timestamp, options = {}) {
  // Don't submit if input is empty unless forced
  if (!query && !options.forceNew) return;

  // Use a default initial query if forced and input is empty
  const effectiveQuery = query || "Start";

  // Only append user message if it wasn't forced and not empty
  if (!options.forceNew && query) {
    // --- (UPDATED Step 5) ---
    // User messages should also be appended as plain text,
    // but we use the HTML-based appendMessage.
    // The existing appendMessage function should handle this safely.
    DomUtils.appendMessage(query, "user");
  }

  // --- (REMOVED) ---
  // DomUtils.clearAssistantInput(); // This is now done in assistant.js
  // DomUtils.showLoadingIndicator(); // This is now done in assistant.js

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

    // --- (UPDATED Step 4) ---
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
      // Don't show the generic "Start" answer if it was forced
      if (!options.forceNew || effectiveQuery !== "Start") {
        // --- (UPDATED Step 5) ---
        // Parse the answer as Markdown before appending
        const htmlAnswer = parseMarkdown(data.answer);
        DomUtils.appendMessage(htmlAnswer, "assistant");
      }

      // Update state with the potentially new conversation ID
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
    // --- (UPDATED Step 4) ---
    removeLoadingIndicator();
    DomUtils.appendMessage(
      `Sorry, an error occurred: ${error.message}`,
      "assistant"
    );
  }
}