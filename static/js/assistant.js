document.addEventListener('DOMContentLoaded', function () {
    const assistantForm = document.getElementById('assistant-form');
    const assistantInput = document.getElementById('assistant-input');
    const chatBox = document.getElementById('assistant-chat-box');
    const sendButton = document.getElementById('assistant-send-btn');
    const assistantChat = document.getElementById('assistantOffcanvas'); 

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
                    timestamp: timestamp
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
            } else {
                appendMessage('Sorry, an error occurred. The assistant did not provide a valid answer.', 'assistant');
            }

        } catch (error) {
            console.error('Error:', error);
            removeLoadingIndicator();
            appendMessage(`Sorry, an error occurred: ${error.message}`, 'assistant');
        }
    };

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

    function removeLoadingIndicator() {
        if (sendButton) sendButton.disabled = false;
        const loadingElement = document.getElementById('loading-indicator');
        if (loadingElement) {
            loadingElement.remove();
        }
    }

    if (assistantForm) {
        assistantForm.addEventListener('submit', handleSubmit);
    }
    
    if (assistantChat) {
        assistantChat.addEventListener('show.bs.offcanvas', function () {
            chatBox.innerHTML = '';
            appendMessage("Hi! How can I help you with this video?", 'assistant');
        });
    }
});