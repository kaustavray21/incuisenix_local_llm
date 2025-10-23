// Wait for the main assistant script to be loaded
document.addEventListener("DOMContentLoaded", function () {
  // Ensure the main assistant object exists
  if (typeof InCuiseNixAssistant === "undefined") {
    console.error("Main assistant script not loaded.");
    return;
  }

  const historyButton = document.getElementById("assistant-history-btn");
  const historyList = document.getElementById("assistant-history-list");
  // const historyView = document.getElementById("assistant-history-view"); // Not needed here

  // --- NEW: State variable to track history visibility ---
  let isHistoryVisible = false;

  /**
   * Helper function to get a cookie value by name.
   */
  function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== "") {
      const cookies = document.cookie.split(";");
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim();
        if (cookie.substring(0, name.length + 1) === name + "=") {
          cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
          break;
        }
      }
    }
    return cookieValue;
  }

  /**
   * Loads the list of past conversations from the API.
   */
  async function loadConversationHistory() {
    historyList.innerHTML = '<p class="text-center">Loading history...</p>';
    const apiUrl = "/api/conversations/";

    try {
      const response = await fetch(apiUrl);
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || "Failed to fetch history.");
      }
      const conversations = await response.json();

      if (!Array.isArray(conversations)) {
        throw new Error("Invalid history format received.");
      }

      if (conversations.length === 0) {
        historyList.innerHTML =
          '<p class="text-center">No conversation history found.</p>';
        return;
      }

      historyList.innerHTML = "";
      conversations.forEach((convo) => {
        const card = document.createElement("div");
        card.className = "conversation-card";
        // --- We no longer need data attributes on the card itself ---

        // --- UPDATED: Added delete button and a content wrapper ---
        card.innerHTML = `
                <div class="conversation-card-content" data-conversation-id="${convo.id}" data-video-id="${convo.video_id}">
                    <div class="conversation-card-title">${convo.title}</div>
                    <small class="conversation-card-video text-muted" title="${convo.course_title} | ${convo.video_title}">
                        ${convo.video_title} 
                    </small>
                    <div class="conversation-card-date">${convo.created_at}</div>
                </div>
                <button class="delete-conversation-btn" data-id="${convo.id}" title="Delete chat">&times;</button>
            `;

        // --- UPDATED: Replaced with a single delegated listener below ---
        historyList.appendChild(card);
      });
    } catch (error) {
      console.error("Error loading history:", error);
      historyList.innerHTML = `<p class="text-center text-danger">Error loading history: ${error.message}</p>`;
    }
  }

  /**
   * Loads messages for a specific conversation.
   */
  async function loadConversationMessages(conversationId, videoId) {
    if (!conversationId || !videoId) {
      console.error("Missing conversationId or videoId when loading messages");
      InCuiseNixAssistant.clearChatBox();
      InCuiseNixAssistant.appendMessage(
        "Sorry, could not load this conversation due to missing data.",
        "assistant"
      );
      return;
    }

    console.log(
      `Loading messages for conversation ${conversationId} (video ${videoId})`
    ); // Debug log

    InCuiseNixAssistant.clearChatBox();
    InCuiseNixAssistant.appendMessage("Loading history...", "assistant");

    try {
      const response = await fetch(
        `/api/conversations/${conversationId}/messages/`
      );
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || "Failed to fetch messages.");
      }
      const messages = await response.json();

      if (!Array.isArray(messages)) {
        throw new Error("Invalid messages format received.");
      }

      InCuiseNixAssistant.clearChatBox(); // Clear loading message

      InCuiseNixAssistant.setActiveConversation(videoId, conversationId);

      messages.forEach((msg) => {
        InCuiseNixAssistant.appendMessage(msg.query, "user");
        InCuiseNixAssistant.appendMessage(msg.answer, "assistant");
      });

      // --- FIX: Update state and toggle view ---
      isHistoryVisible = false;
      InCuiseNixAssistant.toggleHistoryView(false);
    } catch (error) {
      console.error("Error loading messages:", error);
      InCuiseNixAssistant.clearChatBox();
      InCuiseNixAssistant.appendMessage(
        `Sorry, an error occurred while loading this conversation: ${error.message}`,
        "assistant"
      );
    }
  }

  /**
   * --- NEW: Deletes a conversation from the server and UI ---
   */
  async function deleteConversation(conversationId, cardElement) {
    if (!confirm("Are you sure you want to delete this conversation?")) {
      return;
    }

    try {
      const response = await fetch(
        `/api/conversations/delete/${conversationId}/`,
        {
          method: "DELETE",
          headers: {
            "X-CSRFToken": getCookie("csrftoken"),
            Accept: "application/json",
          },
        }
      );

      if (response.status === 204) {
        // 1. Remove from UI
        cardElement.remove();

        // 2. If it was the currently active chat, reset the chat window
        const currentState = InCuiseNixAssistant.getState();
        if (currentState.currentConversationId == conversationId) {
          InCuiseNixAssistant.resetChat();
        }

        // 3. Check if list is now empty
        if (historyList.children.length === 0) {
          historyList.innerHTML =
            '<p class="text-center">No conversation history found.</p>';
        }
      } else {
        const errorData = await response.json();
        console.error("Failed to delete conversation:", errorData.error);
        alert("Failed to delete conversation.");
      }
    } catch (error) {
      console.error("Error deleting conversation:", error);
      alert("An error occurred while deleting the chat.");
    }
  }

  // --- Event Listeners ---

  if (historyButton) {
    historyButton.addEventListener("click", () => {
      // --- FIX: Use state variable for logic ---
      if (!isHistoryVisible) {
        loadConversationHistory(); // Only load if we are opening it
      }
      isHistoryVisible = !isHistoryVisible; // Toggle state
      InCuiseNixAssistant.toggleHistoryView(isHistoryVisible);
    });
  }

  // --- NEW: Delegated Event Listener for the history list ---
  // This replaces adding a listener to every single card.
  if (historyList) {
    historyList.addEventListener("click", (e) => {
      const deleteBtn = e.target.closest(".delete-conversation-btn");
      const cardContent = e.target.closest(".conversation-card-content");

      if (deleteBtn) {
        // --- Handle Delete Click ---
        e.stopPropagation();
        const conversationId = deleteBtn.dataset.id;
        const cardElement = deleteBtn.closest(".conversation-card");
        deleteConversation(conversationId, cardElement);
      } else if (cardContent) {
        // --- Handle Load Click ---
        const conversationId = cardContent.dataset.conversationId;
        const videoId = cardContent.dataset.videoId;
        loadConversationMessages(conversationId, videoId);
      }
    });
  }
});