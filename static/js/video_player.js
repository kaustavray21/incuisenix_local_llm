document.addEventListener('DOMContentLoaded', function() {
    const playerData = document.getElementById('player-data-container');
    if (!playerData) return;

    const videoId = playerData.dataset.videoId;
    const provider = playerData.dataset.videoProvider;
    const vimeoId = playerData.dataset.vimeoId;
    const youtubeId = playerData.dataset.youtubeId;
    
    let transcripts = [];
    let player;

    let pinnedLineContainer = document.getElementById('transcript-current-line');
    let lastActiveLine = null;

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
        const loadingSpinner = document.getElementById('transcript-loading-spinner');
        const unavailableTemplate = document.getElementById('transcript-unavailable-template');

        if(pinnedLineContainer) {
             pinnedLineContainer.innerHTML = `
                <span class="text-content text-muted">Loading transcript...</span>
             `;
        }

        if (!transcriptContent || !loadingSpinner || !unavailableTemplate) return;

        try {
            const response = await fetch(`/api/transcripts/${transcriptVideoId}/`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            transcripts = await response.json();

            loadingSpinner.remove();

            if (transcripts.length === 0) {
                const unavailableEl = unavailableTemplate.content.cloneNode(true);
                transcriptContent.appendChild(unavailableEl);
                if(pinnedLineContainer) {
                    pinnedLineContainer.innerHTML = `
                        <span class="text-content text-muted">No transcript available.</span>
                    `;
                }
                return;
            }
            
            transcriptContent.innerHTML = '';
            
            if(pinnedLineContainer && transcripts.length > 0) {
                pinnedLineContainer.innerHTML = `
                    <span class="transcript-timestamp">${formatTimestamp(transcripts[0].start)}</span>
                    <span class="text-content">${transcripts[0].content}</span>
                `;
            }

            transcripts.forEach(line => {
                const lineElement = document.createElement('div');
                lineElement.classList.add('transcript-line');
                lineElement.dataset.start = line.start;
                
                const timestamp = formatTimestamp(line.start);
                
                lineElement.innerHTML = `
                    <span class="transcript-timestamp">${timestamp}</span>
                    <span class="text-content">${line.content}</span>
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
            
            loadingSpinner.remove();
            const unavailableEl = unavailableTemplate.content.cloneNode(true);
            transcriptContent.appendChild(unavailableEl);
            if(pinnedLineContainer) {
                pinnedLineContainer.innerHTML = `
                    <span class="text-content text-muted">Error loading transcript.</span>
                `;
            }
        }
    }

    function highlightTranscript(currentTime) {
        if (!pinnedLineContainer || !player || transcripts.length === 0) return;

        const duration = player.duration; 
        let activeLineData = null;

        for (let i = 0; i < transcripts.length; i++) {
            const line = transcripts[i];
            const nextLine = transcripts[i + 1];
            
            const startTime = line.start;
            const endTime = nextLine ? nextLine.start : (duration || Infinity); 

            if (currentTime >= startTime && currentTime < endTime) {
                activeLineData = line;
                break;
            }
        }

        if (activeLineData && activeLineData !== lastActiveLine) {
            lastActiveLine = activeLineData;
            
            const timestamp = formatTimestamp(activeLineData.start);
            
            pinnedLineContainer.innerHTML = `
                <span class="transcript-timestamp">${timestamp}</span>
                <span class="text-content">${activeLineData.content}</span>
            `;
        } else if (!activeLineData && lastActiveLine !== null) {
            lastActiveLine = null;
            pinnedLineContainer.innerHTML = `<span class="text-content text-muted">...</span>`;
        }
    }
    
    function setupPlayerEvents(playerInstance) {
        if (playerInstance) {
            playerInstance.on('timeupdate', () => {
                highlightTranscript(playerInstance.currentTime);
            });
        }
    }
});