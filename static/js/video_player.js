document.addEventListener('DOMContentLoaded', function() {
    const playerData = document.getElementById('player-data-container');
    if (!playerData) return;

    const videoId = playerData.dataset.videoId;
    const provider = playerData.dataset.videoProvider;
    const vimeoId = playerData.dataset.vimeoId;
    const youtubeId = playerData.dataset.youtubeId;
    
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

    const playerElement = document.getElementById('player');

    if (playerElement) {
        let playerConfig = {
            controls: [
                'play-large', 'restart', 'play', 'progress', 'current-time', 
                'duration', 'mute', 'volume', 'captions', 'settings', 
                'pip', 'airplay', 'fullscreen'
            ],
            settings: ['captions', 'speed', 'loop']
        };

        if (provider === 'youtube') {
            playerConfig.youtube = {
                rel: 0,
                cc_load_policy: 1,
                noCookie: true,
            };
            player = new Plyr(playerElement, playerConfig);
            window.videoPlayer = player;
            setupPlayerEvents(player);
            loadTranscript(vimeoId || youtubeId);

        } else if (provider === 'vimeo') {
            playerConfig.settings.push('quality');
            initializeVimeoPlayer(playerElement, playerConfig, videoId);
        
        }
    }

    async function initializeVimeoPlayer(element, config, videoModelId) {
        try {
            const response = await fetch(`/api/get-vimeo-links/${videoModelId}/`);
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || `Error: ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.links && data.links.length > 0) {
                element.innerHTML = data.links.map(link => 
                    `<source src="${link.url}" type="video/mp4" size="${link.quality}">`
                ).join('');
                
                player = new Plyr(element, config);
                window.videoPlayer = player;
                setupPlayerEvents(player);
                loadTranscript(vimeoId || youtubeId);
            } else {
                throw new Error("No video links found.");
            }

        } catch (error) {
            console.error('Error initializing Vimeo player:', error);
            element.parentElement.innerHTML = `<div class="alert alert-danger">Could not load video: ${error.message}</div>`;
        }
    }

    async function loadTranscript(transcriptVideoId) {
        if (!transcriptVideoId) return;
        
        const transcriptContent = document.getElementById('transcript-content');
        if (!transcriptContent) return;

        transcriptContent.innerHTML = '<p>Loading transcript...</p>';

        try {
            const response = await fetch(`/api/transcripts/${transcriptVideoId}/`);
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
    
    function setupPlayerEvents(playerInstance) {
        if (playerInstance) {
            playerInstance.on('timeupdate', () => {
                highlightTranscript(playerInstance.currentTime);
            });
        }
    }
});