// static/js/modules/assistant-api.js

import { getCookie } from "./assistant-utils.js";
import * as DomUtils from "./assistant-dom.js"; // Use DomUtils for UI feedback
import * as State from "./assistant-state.js"; // Use State to get/set conversation details

const csrfToken = getCookie("csrftoken");
const ASSISTANT_API_URL = "/api/assistant/";

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
    DomUtils.appendMessage(query, "user");
  }
  DomUtils.clearAssistantInput(); // Clear input field

  DomUtils.showLoadingIndicator();

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

    DomUtils.removeLoadingIndicator();

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
        DomUtils.appendMessage(data.answer, "assistant");
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
    DomUtils.removeLoadingIndicator();
    DomUtils.appendMessage(
      `Sorry, an error occurred: ${error.message}`,
      "assistant"
    );
  }
}
