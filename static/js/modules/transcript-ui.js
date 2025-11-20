import { formatTimestamp } from './utils.js';

let lastActiveLine = null;

export function renderTranscript(transcripts, player) {
    const transcriptContent = document.getElementById('transcript-content');
    const loadingSpinner = document.getElementById('transcript-loading-spinner');
    const unavailableTemplate = document.getElementById('transcript-unavailable-template');
    const pinnedLineContainer = document.getElementById('transcript-current-line');

    if (loadingSpinner) loadingSpinner.remove();

    if (!transcriptContent) return;

    // Clear existing content
    transcriptContent.innerHTML = '';

    if (!transcripts || transcripts.length === 0) {
        if (unavailableTemplate) {
            const unavailableEl = unavailableTemplate.content.cloneNode(true);
            transcriptContent.appendChild(unavailableEl);
        }
        if (pinnedLineContainer) {
            pinnedLineContainer.innerHTML = `<span class="text-content text-muted">Transcript not available yet.</span>`;
        }
        return;
    }

    // Initialize pinned line with first segment
    if (pinnedLineContainer && transcripts.length > 0) {
        pinnedLineContainer.innerHTML = `
            <span class="transcript-timestamp">${formatTimestamp(transcripts[0].start)}</span>
            <span class="text-content">${transcripts[0].content}</span>
        `;
    }

    // Render full list
    transcripts.forEach(line => {
        const lineElement = document.createElement('div');
        lineElement.classList.add('transcript-line');
        lineElement.dataset.start = line.start;
        lineElement.innerHTML = `
            <span class="transcript-timestamp">${formatTimestamp(line.start)}</span>
            <span class="text-content">${line.content}</span>
        `;
        
        // Add seek functionality
        lineElement.addEventListener('click', () => {
            if (player) {
                player.currentTime = line.start;
                player.play();
            }
        });
        transcriptContent.appendChild(lineElement);
    });
}

export function highlightTranscript(currentTime, transcripts, playerDuration) {
    const pinnedLineContainer = document.getElementById('transcript-current-line');
    if (!pinnedLineContainer || !transcripts || transcripts.length === 0) return;

    const duration = playerDuration || Infinity;
    let activeLineData = null;

    for (let i = 0; i < transcripts.length; i++) {
        const line = transcripts[i];
        const nextLine = transcripts[i + 1];
        
        const startTime = line.start;
        const endTime = nextLine ? nextLine.start : duration;

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