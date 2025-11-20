export async function fetchVimeoLinks(vimeoId) {
    const response = await fetch(`/api/get-vimeo-links/${vimeoId}/`);
    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || `Error: ${response.status}`);
    }
    return await response.json();
}

export async function fetchVideoStatus(platformId) {
    const response = await fetch(`/api/video-status/${platformId}/`);
    if (!response.ok) {
        throw new Error(`Status check failed: ${response.status}`);
    }
    return await response.json();
}

export async function fetchTranscript(platformId) {
    const response = await fetch(`/api/transcripts/${platformId}/`);
    if (!response.ok) {
        throw new Error(`Transcript fetch failed: ${response.status}`);
    }
    return await response.json();
}