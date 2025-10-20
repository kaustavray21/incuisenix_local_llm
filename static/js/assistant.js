// Create a global namespace to share functions
var InCuiseNixAssistant = InCuiseNixAssistant || {};

document.addEventListener('DOMContentLoaded', function () {
    const assistantForm = document.getElementById('assistant-form');
    const assistantInput = document.getElementById('assistant-input');
    const chatBox = document.getElementById('assistant-chat-box');
    const sendButton = document.getElementById('assistant-send-btn');
    const assistantChat = document.getElementById('assistantOffcanvas'); 
    
    const newChatButton = document.getElementById('assistant-new-chat-btn');
    const mainChatView = document.getElementById('assistant-main-view');
    const historyView = document.getElementById('assistant-history-view');

    const converter = new showdown.Converter();
    
    let videoConversationMap = {};
    let currentVideoId = null;
    let currentConversationId = null;
    
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

    // --- UPDATED: handleSubmit now accepts an options object ---
    const handleSubmit = async function (event, options = {}) {
        if (event) {
            event.preventDefault();
        }
        
        const query = assistantInput.value.trim();
        // Don't submit if input is empty unless forced 
        if (!query && !options.forceNew) return; 

        // Use a default initial query if forced and input is empty
        const effectiveQuery = query || "Start"; 

        // Only append user message if it wasn't forced and not empty
        if (!options.forceNew && query) { 
            InCuiseNixAssistant.appendMessage(query, 'user');
        }
        assistantInput.value = ''; 

        showLoadingIndicator();

        const timestamp = window.videoPlayer ? window.videoPlayer.currentTime : 0;
        
        // --- NEW: Prepare data payload, including force_new flag ---
        const requestData = {
            query: effectiveQuery,
            video_id: currentVideoId, 
            timestamp: timestamp,
            conversation_id: currentConversationId 
        };
        // *** THIS IS THE KEY CHANGE FOR THE BUG FIX ***
        if (options.forceNew) {
            requestData.force_new = true; 
        }
        // *** END KEY CHANGE ***

        try {
            const response = await fetch('/api/assistant/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                // Send the prepared data
                body: JSON.stringify(requestData)
            });

            removeLoadingIndicator();
            
            if (!response.ok) {
                const errorData = await response.json();
                const errorMessage = errorData.error || `An unexpected error occurred. Status: ${response.status}`;
                throw new Error(errorMessage);
            }

            const data = await response.json();

            if (data.answer) {
                 // Don't show the generic "Start" answer if it was forced
                 if (!options.forceNew || effectiveQuery !== "Start") {
                     InCuiseNixAssistant.appendMessage(data.answer, 'assistant');
                 }
                
                 if (data.conversation_id && currentVideoId) {
                     currentConversationId = data.conversation_id;
                     videoConversationMap[currentVideoId] = currentConversationId;
                 }
            } else {
                InCuiseNixAssistant.appendMessage('Sorry, an error occurred. The assistant did not provide a valid answer.', 'assistant');
            }

        } catch (error) {
            console.error('Error:', error);
            removeLoadingIndicator();
            InCuiseNixAssistant.appendMessage(`Sorry, an error occurred: ${error.message}`, 'assistant');
        }
    };

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

    function removeLoadingIndicator() {
        if (sendButton) sendButton.disabled = false;
        const loadingElement = document.getElementById('loading-indicator');
        if (loadingElement) {
            loadingElement.remove();
        }
    }
    
    function clearChatScreen() {
        InCuiseNixAssistant.clearChatBox();
        InCuiseNixAssistant.appendMessage("Hi! How can I help you with this video?", 'assistant');
        InCuiseNixAssistant.toggleHistoryView(false); 
    }

    // --- Exposed Functions ---
    InCuiseNixAssistant.toggleHistoryView = function(showHistory) {
        if (showHistory) {
            mainChatView.style.display = 'none';
            historyView.style.display = 'flex'; 
        } else {
            mainChatView.style.display = 'flex'; 
            historyView.style.display = 'none';
        }
    }

    InCuiseNixAssistant.appendMessage = function(message, sender) {
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

    InCuiseNixAssistant.clearChatBox = function() {
        chatBox.innerHTML = '';
    }

    InCuiseNixAssistant.setActiveConversation = function(videoId, convId) {
        currentVideoId = videoId;
        currentConversationId = convId;
        if (videoId) {
            videoConversationMap[videoId] = convId;
        }
    }

    // --- NEW: Expose resetChat and getState for history module ---
    InCuiseNixAssistant.resetChat = function() {
        if (currentVideoId) {
            videoConversationMap[currentVideoId] = null;
            currentConversationId = null;
        }
        clearChatScreen();
        // Optionally, you might want to send a "forceNew" request here
        // if your backend requires it to register the "New Conversation"
        // handleSubmit(null, { forceNew: true });
    }

    InCuiseNixAssistant.getState = function() {
        return {
            currentVideoId: currentVideoId,
            currentConversationId: currentConversationId
        };
    }
    // --- End New ---


    // --- Event Listeners ---
    if (assistantForm) {
        assistantForm.addEventListener('submit', handleSubmit); // No options passed for normal submit
    }
    
    if (newChatButton) {
        // --- UPDATED: "New Chat" button listener ---
        newChatButton.addEventListener('click', () => {
            console.log("New Chat button clicked, forcing new conversation.");
            // Clear local state
            if (currentVideoId) {
                videoConversationMap[currentVideoId] = null;
                currentConversationId = null;
            }
            // Clear screen
            clearChatScreen();
            
            // --- NEW: Trigger handleSubmit with forceNew flag ---
            // Sends a dummy "Start" query to backend to force creation
            handleSubmit(null, { forceNew: true }); // Pass forceNew option
            // Note: Input field remains empty for user
        });
    }
    
    if (assistantChat) {
        assistantChat.addEventListener('show.bs.offcanvas', function () {
            const newVideoId = assistantChat.dataset.videoId;
            if (newVideoId !== currentVideoId) {
                console.log(`Video changed from ${currentVideoId} to ${newVideoId}`);
                currentVideoId = newVideoId;
                currentConversationId = videoConversationMap[currentVideoId] || null;
                clearChatScreen();
            } else {
                console.log(`Resuming chat for video ${currentVideoId}`);
                InCuiseNixAssistant.toggleHistoryView(false); // Ensure chat view is visible
            }
        });
    }
});