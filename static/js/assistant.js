// static/js/assistant.js

document.addEventListener('DOMContentLoaded', function () {
    // --- Get all DOM elements for the main chat ---
    const assistantForm = document.getElementById('assistant-form');
    const assistantInput = document.getElementById('assistant-input');
    const chatBox = document.getElementById('assistant-chat-box');
    const sendButton = document.getElementById('assistant-send-btn');
    const assistantChat = document.getElementById('assistantOffcanvas'); 
    const newChatBtn = document.getElementById('new-chat-btn');
    const chatTitle = document.getElementById('assistant-chat-title');

    // --- State Management ---
    let currentConversationId = null;

    // --- Utilities ---
    const converter = new showdown.Converter();
    
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

    // --- Core Chat Functions ---

    const handleSubmit = async function (event) {
        event.preventDefault();
        const query = assistantInput.value.trim();
        if (!query) return;

        appendMessage(query, 'user');
        assistantInput.value = '';

        showLoadingIndicator();

        const videoId = assistantChat ? assistantChat.dataset.videoId : null;
        const timestamp = window.videoPlayer ? window.videoPlayer.currentTime : 0;

        try {
            const response = await fetch('/api/assistant/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({
                    query: query,
                    video_id: videoId,
                    timestamp: timestamp,
                    conversation_id: currentConversationId  // Send current session ID
                })
            });

            removeLoadingIndicator();
            
            if (!response.ok) {
                const errorData = await response.json();
                const errorMessage = errorData.error || `An unexpected error occurred. Status: ${response.status}`;
                throw new Error(errorMessage);
            }

            const data = await response.json();

            if (data.answer) {
                appendMessage(data.answer, 'assistant');
                
                // --- UPDATED: Title Logic ---
                currentConversationId = data.conversation_id;
                // Update title from the server's response
                chatTitle.textContent = data.conversation_name || `Conversation #${currentConversationId}`;

            } else {
                appendMessage('Sorry, an error occurred. The assistant did not provide a valid answer.', 'assistant');
            }

        } catch (error) {
            console.error('Error:', error);
            removeLoadingIndicator();
            appendMessage(`Sorry, an error occurred: ${error.message}`, 'assistant');
        }
    };

    // --- Session & History Loading Functions ---

    function startNewChat() {
        currentConversationId = null;
        chatBox.innerHTML = '';
        chatTitle.textContent = 'New Conversation';
        appendMessage("Hi! How can I help you with this video?", 'assistant');
    }

    async function loadConversation(conversationId) {
        chatBox.innerHTML = '';
        showLoadingIndicator();

        try {
            const response = await fetch(`/api/assistant/conversations/${conversationId}/`);
            if (!response.ok) {
                throw new Error('Failed to load conversation messages.');
            }
            
            // --- UPDATED: Handle new response structure ---
            const data = await response.json();
            const messages = data.messages;

            removeLoadingIndicator();
            
            currentConversationId = data.id; // Set the active conversation
            chatTitle.textContent = data.name; // Set the title from the response

            messages.forEach(message => {
                appendMessage(message.question, 'user');
                appendMessage(message.answer, 'assistant');
            });

        } catch (error) {
            console.error('Error loading conversation:', error);
            removeLoadingIndicator();
            appendMessage(`Error: Could not load conversation #${conversationId}.`, 'assistant');
        }
    }


    // --- UI Helper Functions ---

    function appendMessage(message, sender) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('chat-message', sender);

        if (sender === 'assistant') {
            const htmlContent = converter.makeHtml(message);
            messageElement.innerHTML = htmlContent;
        } else {
            messageElement.textContent = message;
        }

        chatBox.appendChild(messageElement);
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    function showLoadingIndicator() {
        if (sendButton) sendButton.disabled = true;
        const loadingElement = document.createElement('div');
        loadingElement.classList.add('chat-message', 'loading');
        loadingElement.id = 'loading-indicator';
        loadingElement.innerHTML = `
            <div class="d-flex align-items-center">
                <strong class="me-2">Assistant is thinking...</strong>
                <div class="spinner-border spinner-border-sm" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
            </div>
        `;
        chatBox.appendChild(loadingElement);
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    // --- FIX: Renamed this function (removed underscore) ---
    function removeLoadingIndicator() {
        if (sendButton) sendButton.disabled = false;
        const loadingElement = document.getElementById('loading-indicator');
        if (loadingElement) {
            loadingElement.remove();
        }
    }

    // --- Event Listeners ---
    if (assistantForm) {
        assistantForm.addEventListener('submit', handleSubmit);
    }
    if (newChatBtn) {
        newChatBtn.addEventListener('click', startNewChat);
    }
    
    // --- Listen for the custom event from assistant_history.js ---
    document.addEventListener('loadConversation', (e) => {
        const { conversationId } = e.detail;
        if (conversationId) {
            loadConversation(conversationId);
        }
    });

    // Optional: Start a new chat every time the panel is opened
    if (assistantChat) {
        assistantChat.addEventListener('show.bs.offcanvas', function () {
            startNewChat();
        });
    }
});