/**
 * Content Script for YouTube RAG Chatbot
 * Detects current YouTube video and notifies the service worker (per-tab storage).
 */

let transcriptCache = {
  videoId: null,
  transcript: null,
};

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

  try {
    chrome.runtime.sendMessage(
      {
        type: 'UPDATE_VIDEO_INFO',
        videoId,
        videoUrl: window.location.href,
        videoTitle,
      },
      (response) => {
        if (chrome.runtime.lastError) {
          console.warn('[Content] Message error (non-critical):', chrome.runtime.lastError.message);
        }
      }
    );
  } catch (err) {
    // Extension context invalidated - extension was reloaded
    console.warn('[Content] Extension context invalidated, reloading...');
    // Silently ignore - page will need refresh to reconnect
  }
}

function scheduleNotify() {
  if (notifyTimer) clearTimeout(notifyTimer);
  notifyTimer = setTimeout(() => {
    notifyTimer = null;
    notifyVideoInfo();
  }, 120);
}

function extractJsonArrayByMarker(text, marker) {
  const markerIndex = text.indexOf(marker);
  if (markerIndex === -1) return null;

  const arrayStart = text.indexOf('[', markerIndex + marker.length);
  if (arrayStart === -1) return null;

  let depth = 0;
  let inString = false;
  let escaped = false;

  for (let i = arrayStart; i < text.length; i += 1) {
    const ch = text[i];

    if (inString) {
      if (escaped) {
        escaped = false;
      } else if (ch === '\\') {
        escaped = true;
      } else if (ch === '"') {
        inString = false;
      }
      continue;
    }

    if (ch === '"') {
      inString = true;
      continue;
    }

    if (ch === '[') {
      depth += 1;
      continue;
    }

    if (ch === ']') {
      depth -= 1;
      if (depth === 0) {
        return text.slice(arrayStart, i + 1);
      }
    }
  }

  return null;
}

function extractCaptionTracksFromDocument() {
  const scripts = Array.from(document.scripts || []);
  const markers = [
    '"captionTracks":',
    '"captionTracks" :',
  ];

  for (const script of scripts) {
    const text = script.textContent || '';
    if (!text.includes('captionTracks')) continue;

    for (const marker of markers) {
      const jsonArray = extractJsonArrayByMarker(text, marker);
      if (!jsonArray) continue;

      try {
        const tracks = JSON.parse(jsonArray);
        if (Array.isArray(tracks) && tracks.length > 0) {
          return tracks;
        }
      } catch (error) {
        // Keep scanning other scripts.
      }
    }
  }

  return [];
}

function pickCaptionTrack(tracks) {
  if (!Array.isArray(tracks) || tracks.length === 0) return null;

  const english = tracks.find((track) =>
    String(track.languageCode || '').toLowerCase().startsWith('en')
  );
  return english || tracks[0] || null;
}

function decodeTranscriptXml(xmlText) {
  const matches = xmlText.match(/<text[^>]*>([\s\S]*?)<\/text>/g) || [];
  const parser = new DOMParser();
  const cleaned = [];

  for (const match of matches) {
    const doc = parser.parseFromString(match, 'text/xml');
    const text = doc.documentElement?.textContent || '';
    const value = text.replace(/\s+/g, ' ').trim();
    if (value) cleaned.push(value);
  }

  return cleaned.join(' ').trim();
}

async function fetchTranscriptFromCaptionTrack(track) {
  if (!track?.baseUrl) {
    throw new Error('caption track missing baseUrl');
  }

  const response = await fetch(track.baseUrl, {
    method: 'GET',
    credentials: 'include',
  });
  if (!response.ok) {
    throw new Error(`caption request failed with ${response.status}`);
  }

  const body = await response.text();
  const transcript = decodeTranscriptXml(body);
  if (!transcript) {
    throw new Error('caption payload was empty');
  }

  return transcript;
}

async function fetchTranscriptForCurrentVideo() {
  const videoId = getVideoIdFromUrl(window.location.href);
  if (!videoId) {
    throw new Error('no video id');
  }

  if (transcriptCache.videoId === videoId && transcriptCache.transcript) {
    return transcriptCache.transcript;
  }

  const tracks = extractCaptionTracksFromDocument();
  const selectedTrack = pickCaptionTrack(tracks);
  if (!selectedTrack) {
    throw new Error('no caption tracks found on page');
  }

  const transcript = await fetchTranscriptFromCaptionTrack(selectedTrack);
  transcriptCache = { videoId, transcript };
  return transcript;
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type === 'YT_FORCE_REFRESH') {
    transcriptCache = { videoId: null, transcript: null };
    scheduleNotify();
    try {
      sendResponse({ ok: true });
    } catch (err) {
      // Extension context invalidated
    }
    return false;
  }

  if (msg.type === 'YT_GET_TRANSCRIPT') {
    fetchTranscriptForCurrentVideo()
      .then((transcript) => {
        sendResponse({ ok: true, transcript });
      })
      .catch((error) => {
        sendResponse({ ok: false, error: String(error?.message || error) });
      });
    return true;
  }
  return false;
});

let lastUrl = window.location.href;

const urlCheckInterval = setInterval(() => {
  const href = window.location.href;
  if (href !== lastUrl) {
    lastUrl = href;
    transcriptCache = { videoId: null, transcript: null };
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
