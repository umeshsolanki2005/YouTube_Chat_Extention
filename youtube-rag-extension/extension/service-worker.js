/**
 * Service Worker for YouTube RAG Chatbot Extension
 * Handles:
 * - Opening/managing side panel
 * - Storing current video information
 * - Receiving video updates from content script
 */

console.log('[ServiceWorker] Service worker loaded');

// Listen for messages from content script with video info updates
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  console.log('[ServiceWorker] Message received:', request, 'From:', sender.url);
  
  try {
    if (request.type === 'UPDATE_VIDEO_INFO') {
      console.log('[ServiceWorker] Updating video info:', request);
      
      // Store the current video information
      chrome.storage.local.set({
        currentVideoId: request.videoId,
        currentVideoUrl: request.videoUrl,
        currentVideoTitle: request.videoTitle,
        tabId: sender.tab.id
      }, () => {
        if (chrome.runtime.lastError) {
          console.error('[ServiceWorker] Storage error:', chrome.runtime.lastError);
          sendResponse({ success: false, error: chrome.runtime.lastError.message });
        } else {
          console.log('[ServiceWorker] Stored successfully');
          sendResponse({ success: true });
        }
      });
      return true; // Will respond asynchronously
    }
  } catch (error) {
    console.error('[ServiceWorker] Error in message listener:', error);
    sendResponse({ success: false, error: error.message });
  }
});

// Open side panel when extension icon is clicked
chrome.action.onClicked.addListener((tab) => {
  console.log('[ServiceWorker] Extension icon clicked on tab:', tab.id, 'URL:', tab.url);
  
  // Open side panel on YouTube
  if (tab.url && tab.url.includes('youtube.com')) {
    try {
      chrome.sidePanel.open({ tabId: tab.id }).then(() => {
        console.log('[ServiceWorker] Side panel opened');
      }).catch((err) => {
        console.error('[ServiceWorker] Failed to open side panel:', err);
      });
    } catch (err) {
      console.error('[ServiceWorker] Error opening side panel:', err);
    }
  } else {
    console.log('[ServiceWorker] Not a YouTube URL');
  }
});
