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
   * Helper to parse markdown (Duplicated here to ensure availability)
   * This handles formatting like bolding, code blocks, and lists.
   */
  function parseMarkdown(text) {
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
    );

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

      // --- UPDATED LOGIC ---
      if (messages.length === 0) {
        // Handle the case where the conversation exists but has no messages
        InCuiseNixAssistant.appendMessage(
          "No messages found in this conversation.", 
          "assistant"
        );
      } else {
        messages.forEach((msg) => {
          InCuiseNixAssistant.appendMessage(msg.query, "user");
          
          // Apply markdown formatting to the assistant's answer
          const htmlAnswer = parseMarkdown(msg.answer);
          InCuiseNixAssistant.appendMessage(htmlAnswer, "assistant");
        });
      }

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
   * Deletes a conversation from the server and UI
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
        cardElement.remove();

        const currentState = InCuiseNixAssistant.getState();
        if (currentState.currentConversationId == conversationId) {
          InCuiseNixAssistant.resetChat();
        }

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
      if (!isHistoryVisible) {
        loadConversationHistory();
      }
      isHistoryVisible = !isHistoryVisible;
      InCuiseNixAssistant.toggleHistoryView(isHistoryVisible);
    });
  }

  if (historyList) {
    historyList.addEventListener("click", (e) => {
      const deleteBtn = e.target.closest(".delete-conversation-btn");
      const cardContent = e.target.closest(".conversation-card-content");

      if (deleteBtn) {
        e.stopPropagation();
        const conversationId = deleteBtn.dataset.id;
        const cardElement = deleteBtn.closest(".conversation-card");
        deleteConversation(conversationId, cardElement);
      } else if (cardContent) {
        const conversationId = cardContent.dataset.conversationId;
        const videoId = cardContent.dataset.videoId;
        loadConversationMessages(conversationId, videoId);
      }
    });
  }
});