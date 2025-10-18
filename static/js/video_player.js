document.addEventListener('DOMContentLoaded', function() {
    const playerData = document.getElementById('player-data-container');
    const videoId = playerData.dataset.videoId;
    let transcripts = []; // Store transcripts
    let player; // Plyr instance

    /**
     * Formats seconds into HH:MM:SS or MM:SS.
     * @param {number} seconds - The time in seconds.
     * @returns {string} - The formatted timestamp.
     */
    function formatTimestamp(seconds) {
        const h = Math.floor(seconds / 3600).toString().padStart(2, '0');
        const m = Math.floor((seconds % 3600) / 60).toString().padStart(2, '0');
        const s = Math.floor(seconds % 60).toString().padStart(2, '0');

        if (h !== '00') {
            return `${h}:${m}:${s}`;
        }
        return `${m}:${s}`;
    }

    // Initialize Plyr
    if (document.getElementById('player')) {
        player = new Plyr('#player', {
            controls: [
                'play-large', 'restart', 'play', 'progress', 'current-time', 
                'duration', 'mute', 'volume', 'captions', 'settings', 
                'pip', 'airplay', 'fullscreen'
            ],
            settings: ['captions', 'speed', 'loop'],
            youtube: {
                rel: 0,
                cc_load_policy: 1,
                noCookie: true,
            }
        });
        window.videoPlayer = player; // Expose player globally for assistant
    }

    // Function to load and display transcript
    async function loadTranscript(videoId) {
        if (!videoId) return;
        
        const transcriptContent = document.getElementById('transcript-content');
        if (!transcriptContent) return;

        transcriptContent.innerHTML = '<p>Loading transcript...</p>';

        try {
            const response = await fetch(`/api/transcripts/${videoId}/`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            transcripts = await response.json();

            if (transcripts.length === 0) {
                transcriptContent.innerHTML = '<p>No transcript available for this video.</p>';
                return;
            }

            transcriptContent.innerHTML = '';

            transcripts.forEach(line => {
                const lineElement = document.createElement('div');
                lineElement.classList.add('transcript-line');
                lineElement.dataset.start = line.start;
                
                const timestamp = formatTimestamp(line.start);
                
                lineElement.innerHTML = `
                    <span class="transcript-timestamp">${timestamp}</span>
                    <span class="transcript-text">${line.content}</span>
                `;
                
                // Add click event to seek video
                lineElement.addEventListener('click', () => {
                    if (player) {
                        player.currentTime = line.start;
                        player.play();
                    }
                });
                
                transcriptContent.appendChild(lineElement);
            });

        } catch (error) {
            console.error('Error loading transcript:', error);
            transcriptContent.innerHTML = '<p>Sorry, an error occurred while loading the transcript.</p>';
        }
    }

    // Function to highlight active transcript line
    function highlightTranscript(currentTime) {
        const transcriptContent = document.getElementById('transcript-content');
        if (!transcriptContent) return;

        const lines = transcriptContent.querySelectorAll('.transcript-line');
        let activeLine = null;

        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];
            const nextLine = lines[i + 1];
            
            const startTime = parseFloat(line.dataset.start);
            const endTime = nextLine ? parseFloat(nextLine.dataset.start) : (player.duration || startTime + 5);

            if (currentTime >= startTime && currentTime < endTime) {
                line.classList.add('active');
                activeLine = line;
            } else {
                line.classList.remove('active');
            }
        }

        // Scroll active line into view
        if (activeLine && !isElementInView(activeLine)) {
             activeLine.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }

    // Helper to check if element is in view
    function isElementInView(el) {
        const rect = el.getBoundingClientRect();
        const parentRect = el.parentElement.getBoundingClientRect();
        return (
            rect.top >= parentRect.top &&
            rect.bottom <= parentRect.bottom
        );
    }

    // Load transcript on page load
    loadTranscript(videoId);

    // Add timeupdate listener to player
    if (player) {
        player.on('timeupdate', () => {
            highlightTranscript(player.currentTime);
        });
    }
});