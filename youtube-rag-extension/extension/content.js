/**
 * Content Script for YouTube RAG Chatbot
 * Detects current YouTube video and notifies the service worker (per-tab storage).
 */

function getVideoIdFromUrl(url) {
  try {
    const urlObj = new URL(url);

    if (urlObj.hostname.includes('youtube.com')) {
      const videoId = urlObj.searchParams.get('v');
      if (videoId) return videoId;
    }

    if (urlObj.hostname.includes('youtu.be')) {
      const videoId = urlObj.pathname.replace(/^\//, '').split('/')[0];
      if (videoId && videoId.length >= 6) return videoId;
    }
  } catch (error) {
    console.error('[Content] URL parsing error:', error);
  }

  return null;
}

function getVideoTitle() {
  const selectors = [
    'ytd-watch-metadata h1 yt-formatted-string',
    'h1.ytd-watch-metadata yt-formatted-string',
    'ytd-video-primary-info-renderer h1 yt-formatted-string',
    'h1.title yt-formatted-string',
    'yt-formatted-string.title',
    'h1 yt-formatted-string',
    'h1',
  ];

  for (const selector of selectors) {
    const elements = document.querySelectorAll(selector);
    for (const element of elements) {
      const text = element.textContent && element.textContent.trim();
      if (text && text.length > 0 && !text.includes('YouTube')) {
        return text;
      }
    }
  }

  return 'YouTube Video';
}

let notifyTimer = null;

function notifyVideoInfo() {
  const videoId = getVideoIdFromUrl(window.location.href);
  const videoTitle = getVideoTitle();

  if (!videoId) {
    console.warn('[Content] No video ID for URL:', window.location.href);
    return;
  }

  chrome.runtime.sendMessage(
    {
      type: 'UPDATE_VIDEO_INFO',
      videoId,
      videoUrl: window.location.href,
      videoTitle,
    },
    (response) => {
      if (chrome.runtime.lastError) {
        console.error('[Content] Message error:', chrome.runtime.lastError.message);
      }
    }
  );
}

function scheduleNotify() {
  if (notifyTimer) clearTimeout(notifyTimer);
  notifyTimer = setTimeout(() => {
    notifyTimer = null;
    notifyVideoInfo();
  }, 120);
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type === 'YT_FORCE_REFRESH') {
    scheduleNotify();
    sendResponse({ ok: true });
  }
  return false;
});

let lastUrl = window.location.href;

const urlCheckInterval = setInterval(() => {
  const href = window.location.href;
  if (href !== lastUrl) {
    lastUrl = href;
    scheduleNotify();
  }
}, 400);

setTimeout(scheduleNotify, 300);

window.addEventListener('yt-navigate-finish', () => scheduleNotify());

window.addEventListener('popstate', () => scheduleNotify());

document.addEventListener('yt-page-data-updated', () => scheduleNotify());

window.addEventListener('beforeunload', () => {
  clearInterval(urlCheckInterval);
});

console.log('[Content] YouTube RAG content script ready');
