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

    // --- Button Elements ---
    const transcriptBtn = document.getElementById('toggle-transcript-btn');
    const assistantBtn = document.getElementById('btn-assistant');
    
    let pollingInterval = null;
    let isTranscriptLoaded = false;

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
            checkStatusAndInitialize();

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
                checkStatusAndInitialize();
            } else {
                throw new Error("No video links found.");
            }

        } catch (error) {
            console.error('Error initializing Vimeo player:', error);
            element.parentElement.innerHTML = `<div class="alert alert-danger">Could not load video: ${error.message}</div>`;
        }
    }

    // --- Combined Initialization and Polling Logic ---
    function checkStatusAndInitialize() {
        loadTranscript(vimeoId || youtubeId);
        startStatusPolling();
    }

    function startStatusPolling() {
        pollVideoStatus();
        pollingInterval = setInterval(pollVideoStatus, 5000);
    }

    async function pollVideoStatus() {
        try {
            const response = await fetch(`/api/video-status/${videoId}/`);
            if (!response.ok) return;
            const statusData = await response.json();

            const tStatus = (statusData.transcript_status || '').toLowerCase();
            const iStatus = (statusData.index_status || '').toLowerCase();

            // Update Transcript Button
            updateButtonState(
                transcriptBtn, 
                tStatus, 
                'transcript'
            );

            if (tStatus === 'complete' && !isTranscriptLoaded) {
                console.log("Transcript processing complete. Reloading...");
                loadTranscript(vimeoId || youtubeId);
            }

            // Update Assistant Button
            updateButtonState(
                assistantBtn, 
                iStatus, 
                'assistant'
            );

            // Stop polling if everything is done
            if (tStatus === 'complete' && iStatus === 'complete') {
                clearInterval(pollingInterval);
                
                // Ensure icons are reset to their final static state
                resetButton(transcriptBtn, '<i class="far fa-file-alt"></i> <span class="btn-text">Transcript</span>');
                resetButton(assistantBtn, '<i class="fas fa-robot me-1"></i> <span class="btn-text">AI Assistant</span>');
            }

        } catch (error) {
            console.error("Error polling video status:", error);
        }
    }

    function updateButtonState(btn, rawStatus, type) {
        if (!btn) return;
        const status = (rawStatus || 'none').toLowerCase();

        if (status === 'processing' || status === 'indexing') {
            // --- PROCESSING STATE: Show Spinner ---
            btn.disabled = true;
            btn.classList.add('disabled');
            
            const verb = (type === 'transcript') ? 'Generating...' : 'Indexing...';
            // Replaces the icon with a spinning circle
            btn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> <span class="btn-text">${verb}</span>`;

        } else if (status === 'pending' || status === 'none') {
            // --- PENDING STATE ---
            btn.disabled = true;
            btn.classList.add('disabled');
            const text = (type === 'assistant') ? 'Waiting...' : 'Pending...';
            btn.innerHTML = `<i class="far fa-clock"></i> <span class="btn-text">${text}</span>`;

        } else if (status === 'complete') {
            // --- COMPLETE STATE ---
            btn.disabled = false;
            btn.classList.remove('disabled');
            
            // Restore Original Icons
            if (type === 'transcript') {
                btn.innerHTML = '<i class="far fa-file-alt"></i> <span class="btn-text">Transcript</span>';
            } else {
                btn.innerHTML = '<i class="fas fa-robot me-1"></i> <span class="btn-text">AI Assistant</span>';
            }

        } else if (status === 'failed') {
            // --- FAILED STATE ---
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-exclamation-triangle"></i> <span class="btn-text">Failed</span>';
        }
    }

    function resetButton(btn, html) {
        if (btn) {
            btn.disabled = false;
            btn.classList.remove('disabled');
            btn.innerHTML = html;
        }
    }
    // -----------------------------------------------------


    async function loadTranscript(transcriptVideoId) {
        if (!transcriptVideoId) return;
        
        const transcriptContent = document.getElementById('transcript-content');
        const loadingSpinner = document.getElementById('transcript-loading-spinner');
        const unavailableTemplate = document.getElementById('transcript-unavailable-template');

        if(pinnedLineContainer) {
             pinnedLineContainer.innerHTML = `<span class="text-content text-muted">Loading transcript...</span>`;
        }

        if (!transcriptContent || !loadingSpinner || !unavailableTemplate) return;

        try {
            const response = await fetch(`/api/transcripts/${transcriptVideoId}/`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            transcripts = await response.json();

            if(loadingSpinner) loadingSpinner.remove();

            if (transcripts.length === 0) {
                transcriptContent.innerHTML = ''; 
                const unavailableEl = unavailableTemplate.content.cloneNode(true);
                transcriptContent.appendChild(unavailableEl);
                if(pinnedLineContainer) {
                    pinnedLineContainer.innerHTML = `<span class="text-content text-muted">Transcript not available yet.</span>`;
                }
                isTranscriptLoaded = false;
                return;
            }
            
            isTranscriptLoaded = true;
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
                lineElement.innerHTML = `
                    <span class="transcript-timestamp">${formatTimestamp(line.start)}</span>
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
            if(loadingSpinner) loadingSpinner.remove();
            transcriptContent.innerHTML = '';
            const unavailableEl = unavailableTemplate.content.cloneNode(true);
            transcriptContent.appendChild(unavailableEl);
            if(pinnedLineContainer) {
                pinnedLineContainer.innerHTML = `<span class="text-content text-muted">Error loading transcript.</span>`;
            }
            isTranscriptLoaded = false;
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
            pinnedLineContainer.innerHTML = `
                <span class="transcript-timestamp">${formatTimestamp(activeLineData.start)}</span>
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