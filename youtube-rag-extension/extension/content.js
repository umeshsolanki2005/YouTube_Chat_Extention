/**
 * Content Script for YouTube RAG Chatbot
 * Detects current YouTube video and notifies background script
 */

// Extract video ID from YouTube URL - simplified version
function getVideoIdFromUrl(url) {
  console.log('[Content] Parsing URL:', url);
  
  // Parse URL
  try {
    const urlObj = new URL(url);
    
    // Method 1: youtube.com/watch?v=VIDEO_ID
    if (urlObj.hostname.includes('youtube.com')) {
      const videoId = urlObj.searchParams.get('v');
      if (videoId) {
        console.log('[Content] Found video ID via searchParams:', videoId);
        return videoId;
      }
    }
    
    // Method 2: youtu.be/VIDEO_ID
    if (urlObj.hostname.includes('youtu.be')) {
      const videoId = urlObj.pathname.slice(1);
      if (videoId) {
        console.log('[Content] Found video ID via youtu.be:', videoId);
        return videoId;
      }
    }
  } catch (error) {
    console.error('[Content] URL parsing error:', error);
  }
  
  console.log('[Content] No video ID found');
  return null;
}

// Get video title from page
function getVideoTitle() {
  // YouTube video title - try multiple selectors
  const selectors = [
    'h1.title yt-formatted-string',
    'yt-formatted-string.title',
    'h1 yt-formatted-string',
    'ytd-video-primary-info-renderer h1 yt-formatted-string',
    'h1'
  ];
  
  for (const selector of selectors) {
    const elements = document.querySelectorAll(selector);
    for (const element of elements) {
      if (element.textContent && element.textContent.trim().length > 0) {
        const title = element.textContent.trim();
        if (!title.includes('YouTube')) { // Avoid generic titles
          console.log('[Content] Found title:', title);
          return title;
        }
      }
    }
  }
  
  console.log('[Content] Using default title');
  return 'YouTube Video';
}

// Send video information to service worker
function notifyVideoInfo() {
  const videoId = getVideoIdFromUrl(window.location.href);
  const videoTitle = getVideoTitle();
  
  console.log('[Content] Notifying - Video ID:', videoId, 'Title:', videoTitle);
  
  if (videoId) {
    try {
      chrome.runtime.sendMessage({
        type: 'UPDATE_VIDEO_INFO',
        videoId: videoId,
        videoUrl: window.location.href,
        videoTitle: videoTitle
      }, (response) => {
        if (chrome.runtime.lastError) {
          console.error('[Content] Message error:', chrome.runtime.lastError);
        } else {
          console.log('[Content] Message sent successfully:', response);
        }
      });
    } catch (error) {
      console.error('[Content] Failed to send message:', error);
    }
  } else {
    console.warn('[Content] Cannot send message - no video ID detected');
  }
}

console.log('[Content] Script loaded');

// Initial notification
setTimeout(notifyVideoInfo, 500);

// Watch for URL changes
let lastUrl = window.location.href;
const urlCheckInterval = setInterval(() => {
  if (window.location.href !== lastUrl) {
    console.log('[Content] URL changed from', lastUrl, 'to', window.location.href);
    lastUrl = window.location.href;
    setTimeout(notifyVideoInfo, 500);
  }
}, 1000);

// YouTube navigation event
window.addEventListener('yt-navigate-finish', () => {
  console.log('[Content] YouTube navigation detected');
  setTimeout(notifyVideoInfo, 500);
});

// History changes (back/forward)
window.addEventListener('popstate', () => {
  console.log('[Content] History changed');
  setTimeout(notifyVideoInfo, 500);
});

// Cleanup
window.addEventListener('beforeunload', () => {
  clearInterval(urlCheckInterval);
});
