// Wait for the main assistant script to be loaded
document.addEventListener('DOMContentLoaded', function () {
    
    // Ensure the main assistant object exists
    if (typeof InCuiseNixAssistant === 'undefined') {
        console.error('Main assistant script not loaded.');
        return;
    }

    const historyButton = document.getElementById('assistant-history-btn');
    const historyList = document.getElementById('assistant-history-list');
    const historyView = document.getElementById('assistant-history-view');

    // Function to load the list of past conversations (global)
    async function loadConversationHistory() {
        historyList.innerHTML = '<p class="text-center">Loading history...</p>';
        const apiUrl = '/api/conversations/'; 
        
        try {
            const response = await fetch(apiUrl);
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to fetch history.');
            }
            const conversations = await response.json();

            if (!Array.isArray(conversations)) {
                 throw new Error('Invalid history format received.');
            }

            if (conversations.length === 0) {
                historyList.innerHTML = '<p class="text-center">No conversation history found.</p>';
                return;
            }

            historyList.innerHTML = ''; 
            conversations.forEach(convo => {
                const card = document.createElement('div');
                card.className = 'conversation-card';
                card.dataset.conversationId = convo.id;
                card.dataset.videoId = convo.video_id; 
                
                card.innerHTML = `
                    <div class="conversation-card-title">${convo.title}</div>
                    <small class="conversation-card-video text-muted" title="${convo.course_title} | ${convo.video_title}">
                        ${convo.video_title} 
                    </small>
                    <div class="conversation-card-date">${convo.created_at}</div>
                `;
                
                // Add click event listener directly here
                card.addEventListener('click', () => {
                    // Pass the necessary data directly
                    loadConversationMessages(convo.id, convo.video_id); 
                });
                
                historyList.appendChild(card);
            });

        } catch (error) {
            console.error('Error loading history:', error);
            historyList.innerHTML = `<p class="text-center text-danger">Error loading history: ${error.message}</p>`;
        }
    }

    // --- UPDATED: Accepts conversationId and videoId directly ---
    async function loadConversationMessages(conversationId, videoId) { 
        if (!conversationId || !videoId) {
             console.error("Missing conversationId or videoId when loading messages");
             InCuiseNixAssistant.clearChatBox();
             InCuiseNixAssistant.appendMessage('Sorry, could not load this conversation due to missing data.', 'assistant');
             return;
        }

        console.log(`Loading messages for conversation ${conversationId} (video ${videoId})`); // Debug log

        InCuiseNixAssistant.clearChatBox();
        InCuiseNixAssistant.appendMessage('Loading history...', 'assistant');
        
        try {
            const response = await fetch(`/api/conversations/${conversationId}/messages/`);
            if (!response.ok) {
                 const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to fetch messages.');
            }
            const messages = await response.json();

             if (!Array.isArray(messages)) {
                 throw new Error('Invalid messages format received.');
            }

            InCuiseNixAssistant.clearChatBox(); // Clear loading message
            
            // --- FIX: Set active conversation *before* appending messages ---
            // This ensures the main script knows the context *before* display
            InCuiseNixAssistant.setActiveConversation(videoId, conversationId);

            // Append messages *after* setting the state
            messages.forEach(msg => {
                InCuiseNixAssistant.appendMessage(msg.query, 'user');
                InCuiseNixAssistant.appendMessage(msg.answer, 'assistant');
            });
            
            // Switch back to the chat view *after* messages are added
            InCuiseNixAssistant.toggleHistoryView(false); 

        } catch (error) {
            console.error('Error loading messages:', error);
            InCuiseNixAssistant.clearChatBox();
            InCuiseNixAssistant.appendMessage(`Sorry, an error occurred while loading this conversation: ${error.message}`, 'assistant');
             // Optionally switch back to history view on error
            // InCuiseNixAssistant.toggleHistoryView(true); 
        }
    }

    // --- Event Listener ---

    if (historyButton) {
        historyButton.addEventListener('click', () => {
            const isHistoryVisible = historyView.style.display === 'flex';
            if (!isHistoryVisible) {
                loadConversationHistory();
            }
            InCuiseNixAssistant.toggleHistoryView(!isHistoryVisible);
        });
    }
});