// static/js/modules/assistant-state.js

let videoConversationMap = {};
let currentVideoId = null;
let currentConversationId = null;

export function getState() {
  return {
    currentVideoId: currentVideoId,
    currentConversationId: currentConversationId,
    // videoConversationMap is internal, not usually needed externally
  };
}

export function setActiveConversation(videoId, convId) {
  console.log(
    `State: Setting active conversation - Video: ${videoId}, ConvID: ${convId}`
  );
  currentVideoId = videoId;
  currentConversationId = convId;
  if (videoId) {
    videoConversationMap[videoId] = convId;
  }
}

export function resetCurrentConversation() {
  // --- UPDATED: clearer logging to confirm Video ID persistence ---
  console.log(`State: Resetting conversation. Preserving Video ID: ${currentVideoId}`);
  
  if (currentVideoId) {
    videoConversationMap[currentVideoId] = null;
  }
  currentConversationId = null;
}

export function getConversationForVideo(videoId) {
  return videoConversationMap[videoId] || null;
}