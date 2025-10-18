// static/js/assistant_history.js

// We wrap our history logic in an IIFE (Immediately Invoked Function Expression)
// to avoid polluting the global scope.
(function () {
    // --- Get DOM elements for the history panel ---
    const historyBtn = document.getElementById('history-btn');
    const backToChatBtn = document.getElementById('back-to-chat-btn');
    const mainView = document.getElementById('assistant-main-view');
    const historyView = document.getElementById('assistant-history-view');
    const historyList = document.getElementById('assistant-history-list');
    const assistantChat = document.getElementById('assistantOffcanvas');

    // --- Utility function ---
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
    const csrfToken = getCookie('csrftoken');

    // --- View Switching Functions ---

    function showHistoryView() {
        mainView.classList.add('d-none');
        historyView.classList.remove('d-none');
        loadConversationHistory();
    }

    function showMainChatView() {
        historyView.classList.add('d-none');
        mainView.classList.remove('d-none');
    }

    // --- Core History Logic ---

    async function loadConversationHistory() {
        historyList.innerHTML = `
            <div class="d-flex justify-content-center">
                <div class="spinner-border spinner-border-sm" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
            </div>`;
        
        const videoId = assistantChat ? assistantChat.dataset.videoId : null;
        if (!videoId) {
            historyList.innerHTML = '<p class="text-muted">Error: No video ID found.</p>';
            return;
        }

        try {
            const response = await fetch(`/api/assistant/conversations/?video_id=${videoId}`);
            if (!response.ok) {
                throw new Error('Failed to load history.');
            }
            const conversations = await response.json();
            
            historyList.innerHTML = ''; // Clear spinner

            if (conversations.length === 0) {
                historyList.innerHTML = '<p class="text-muted text-center">No chat history for this video.</p>';
                return;
            }

            conversations.forEach(conversation => {
                const item = document.createElement('a');
                item.href = '#';
                item.classList.add('list-group-item', 'list-group-item-action');
                item.textContent = conversation.name || `Chat #${conversation.id}`; // Fallback if name is empty
                
                const date = new Date(conversation.created_at).toLocaleString();
                item.innerHTML += `<br><small class="text-muted">${date}</small>`;
                
                item.dataset.conversationId = conversation.id;
                
                item.addEventListener('click', (e) => {
                    e.preventDefault();
                    // --- Fire a custom event to tell assistant.js to load this chat ---
                    const loadEvent = new CustomEvent('loadConversation', { 
                        detail: { conversationId: conversation.id } 
                    });
                    document.dispatchEvent(loadEvent);
                    showMainChatView();
                });
                historyList.appendChild(item);
            });

        } catch (error) {
            console.error('Error loading history:', error);
            historyList.innerHTML = '<p class="text-danger">Failed to load history.</p>';
        }
    }

    // --- Event Listeners ---
    if (historyBtn) {
        historyBtn.addEventListener('click', showHistoryView);
    }
    if (backToChatBtn) {
        backToChatBtn.addEventListener('click', showMainChatView);
    }

})();