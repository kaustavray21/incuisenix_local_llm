export function updateButtonState(btn, rawStatus, type) {
    if (!btn) return;
    const status = (rawStatus || 'none').toLowerCase();

    if (status === 'processing' || status === 'indexing') {
        btn.disabled = true;
        btn.classList.add('disabled');
        
        const verb = (type === 'transcript') ? 'Generating...' : 'Indexing...';
        btn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> <span class="btn-text">${verb}</span>`;

    } else if (status === 'pending' || status === 'none') {
        btn.disabled = true;
        btn.classList.add('disabled');
        const text = (type === 'assistant') ? 'Waiting...' : 'Pending...';
        btn.innerHTML = `<i class="far fa-clock"></i> <span class="btn-text">${text}</span>`;

    } else if (status === 'complete') {
        btn.disabled = false;
        btn.classList.remove('disabled');
        
        if (type === 'transcript') {
            btn.innerHTML = '<i class="far fa-file-alt"></i> <span class="btn-text">Transcript</span>';
        } else {
            btn.innerHTML = '<i class="fas fa-robot me-1"></i> <span class="btn-text">AI Assistant</span>';
        }

    } else if (status === 'failed') {
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-exclamation-triangle"></i> <span class="btn-text">Failed</span>';
    }
}

export function resetButton(btn, html) {
    if (btn) {
        btn.disabled = false;
        btn.classList.remove('disabled');
        btn.innerHTML = html;
    }
}