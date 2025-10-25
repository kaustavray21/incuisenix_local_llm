document.addEventListener('DOMContentLoaded', function() {
    const playerData = document.getElementById('player-data-container');
    const videoId = playerData.dataset.videoId;
    let transcripts = [];
    let player;

    function formatTimestamp(seconds) {
        const h = Math.floor(seconds / 3600).toString().padStart(2, '0');
        const m = Math.floor((seconds % 3600) / 60).toString().padStart(2, '0');
        const s = Math.floor(seconds % 60).toString().padStart(2, '0');

        if (h !== '00') {
            return `${h}:${m}:${s}`;
        }
        return `${m}:${s}`;
    }

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
        window.videoPlayer = player;
    }

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

    function highlightTranscript(currentTime) {
        const transcriptContent = document.getElementById('transcript-content');
        if (!transcriptContent || !player) return;

        const lines = transcriptContent.querySelectorAll('.transcript-line');
        let activeLine = null;

        const duration = player.duration; 

        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];
            const nextLine = lines[i + 1];
            
            const startTime = parseFloat(line.dataset.start);
            const endTime = nextLine ? parseFloat(nextLine.dataset.start) : (duration || startTime + 5); 

            if (currentTime >= startTime && currentTime < endTime) {
                line.classList.add('active');
                activeLine = line;
            } else {
                line.classList.remove('active');
            }
        }

        if (activeLine && !isElementInView(activeLine)) {
             activeLine.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }

    function isElementInView(el) {
        const rect = el.getBoundingClientRect();
        const parentRect = el.parentElement.getBoundingClientRect();
        return (
            rect.top >= parentRect.top &&
            rect.bottom <= parentRect.bottom
        );
    }

    loadTranscript(videoId);

    if (player) {
        player.on('timeupdate', () => {
            highlightTranscript(player.currentTime);
        });
    }
});