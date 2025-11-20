import { fetchVimeoLinks, fetchVideoStatus, fetchTranscript } from './modules/video-api.js';
import { renderTranscript, highlightTranscript } from './modules/transcript-ui.js';
import { updateButtonState, resetButton } from './modules/player-controls.js';

document.addEventListener('DOMContentLoaded', function() {
    const playerData = document.getElementById('player-data-container');
    if (!playerData) return;

    const provider = playerData.dataset.videoProvider;
    const vimeoId = playerData.dataset.vimeoId;
    const youtubeId = playerData.dataset.youtubeId;
    const platformId = vimeoId || youtubeId;
    
    const playerElement = document.getElementById('player');
    const transcriptBtn = document.getElementById('toggle-transcript-btn');
    const assistantBtn = document.getElementById('btn-assistant');
    const pinnedLineContainer = document.getElementById('transcript-current-line');

    let player;
    let transcripts = [];
    let pollingInterval = null;
    let isTranscriptLoaded = false;

    // --- Initialization ---

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
            playerConfig.youtube = { rel: 0, cc_load_policy: 1, noCookie: true };
            initPlayer(playerConfig);
        } else if (provider === 'vimeo') {
            playerConfig.settings.push('quality');
            initVimeo(playerElement, playerConfig);
        }
    }

    function initPlayer(config) {
        player = new Plyr(playerElement, config);
        window.videoPlayer = player; // Global reference for other scripts
        
        setupPlayerEvents(player);
        checkStatusAndInitialize();
    }

    async function initVimeo(element, config) {
        try {
            const data = await fetchVimeoLinks(vimeoId);
            
            if (data.links && data.links.length > 0) {
                element.innerHTML = data.links.map(link => 
                    `<source src="${link.url}" type="video/mp4" size="${link.quality}">`
                ).join('');
                
                initPlayer(config);
            } else {
                throw new Error("No video links found.");
            }
        } catch (error) {
            console.error('Error initializing Vimeo player:', error);
            element.parentElement.innerHTML = `<div class="alert alert-danger">Could not load video: ${error.message}</div>`;
        }
    }

    function setupPlayerEvents(playerInstance) {
        if (playerInstance) {
            playerInstance.on('timeupdate', () => {
                highlightTranscript(playerInstance.currentTime, transcripts, playerInstance.duration);
            });
        }
    }

    // --- Logic & Polling ---

    function checkStatusAndInitialize() {
        loadTranscriptData();
        startStatusPolling();
    }

    async function loadTranscriptData() {
        if (!platformId) return;

        if (pinnedLineContainer) {
             pinnedLineContainer.innerHTML = `<span class="text-content text-muted">Loading transcript...</span>`;
        }

        try {
            transcripts = await fetchTranscript(platformId);
            renderTranscript(transcripts, player);
            isTranscriptLoaded = (transcripts.length > 0);
        } catch (error) {
            console.error('Error loading transcript:', error);
            // Pass empty array to render empty state
            renderTranscript([], player);
            if (pinnedLineContainer) {
                pinnedLineContainer.innerHTML = `<span class="text-content text-muted">Error loading transcript.</span>`;
            }
            isTranscriptLoaded = false;
        }
    }

    function startStatusPolling() {
        pollStatus();
        pollingInterval = setInterval(pollStatus, 5000);
    }

    async function pollStatus() {
        if (!platformId) return;

        try {
            const statusData = await fetchVideoStatus(platformId);
            
            const tStatus = (statusData.transcript_status || '').toLowerCase();
            const iStatus = (statusData.index_status || '').toLowerCase();

            updateButtonState(transcriptBtn, tStatus, 'transcript');
            updateButtonState(assistantBtn, iStatus, 'assistant');

            // Auto-reload transcript if it just finished
            if (tStatus === 'complete' && !isTranscriptLoaded) {
                console.log("Transcript processing complete. Reloading...");
                loadTranscriptData();
            }

            // Stop polling if all done
            if (tStatus === 'complete' && iStatus === 'complete') {
                clearInterval(pollingInterval);
                resetButton(transcriptBtn, '<i class="far fa-file-alt"></i> <span class="btn-text">Transcript</span>');
                resetButton(assistantBtn, '<i class="fas fa-robot me-1"></i> <span class="btn-text">AI Assistant</span>');
            }

        } catch (error) {
            console.error("Error polling video status:", error);
        }
    }
});