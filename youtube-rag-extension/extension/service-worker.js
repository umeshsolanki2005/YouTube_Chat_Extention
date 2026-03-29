/**
 * Service Worker for YouTube RAG Chatbot Extension
 * Handles:
 * - Opening/managing side panel
 * - Per-tab video storage (avoids stale global storage)
 * - Resolving which video the side panel should show (tab URL + oEmbed fallback)
 */

console.log('[ServiceWorker] Service worker loaded');

function extractVideoIdFromUrl(urlString) {
  try {
    const u = new URL(urlString);
    if (u.hostname.includes('youtube.com')) {
      const v = u.searchParams.get('v');
      if (v) return v;
    }
    if (u.hostname.includes('youtu.be')) {
      const id = u.pathname.replace(/^\//, '').split('/')[0];
      if (id && id.length >= 6) return id;
    }
  } catch (e) {
    /* ignore */
  }
  return null;
}

async function fetchTitleOembed(videoUrl) {
  try {
    const oembedUrl = `https://www.youtube.com/oembed?url=${encodeURIComponent(
      videoUrl
    )}&format=json`;
    const r = await fetch(oembedUrl);
    if (!r.ok) return null;
    const j = await r.json();
    return j.title || null;
  } catch (e) {
    return null;
  }
}

/**
 * Pick the YouTube watch tab the user is actually watching in the focused window.
 */
async function getTargetYoutubeTab() {
  try {
    const win = await chrome.windows.getLastFocused({ populate: true });
    if (!win?.tabs?.length) return null;

    const tabs = win.tabs;
    const active = tabs.find((t) => t.active);
    if (active?.url) {
      const v = extractVideoIdFromUrl(active.url);
      if (v) return active;
    }
    return tabs.find((t) => t.url && extractVideoIdFromUrl(t.url)) || null;
  } catch (e) {
    console.warn('[ServiceWorker] getTargetYoutubeTab', e);
    return null;
  }
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.type === 'UPDATE_VIDEO_INFO') {
    const tabId = sender.tab?.id;
    if (!tabId) {
      sendResponse({ success: false, error: 'no_tab' });
      return false;
    }

    const key = `video_${tabId}`;
    const payload = {
      videoId: request.videoId,
      videoUrl: request.videoUrl,
      videoTitle: request.videoTitle,
      updated: Date.now(),
    };

    chrome.storage.local.set(
      {
        [key]: payload,
        currentVideoId: request.videoId,
        currentVideoUrl: request.videoUrl,
        currentVideoTitle: request.videoTitle,
      },
      () => {
        if (chrome.runtime.lastError) {
          console.error('[ServiceWorker] Storage error:', chrome.runtime.lastError);
          sendResponse({ success: false, error: chrome.runtime.lastError.message });
        } else {
          sendResponse({ success: true });
        }
      }
    );
    return true;
  }

  if (request.type === 'GET_VIDEO_FOR_PANEL') {
    (async () => {
      try {
        // Prefer the watch tab in the focused window (what the user is actually viewing)
        let tab = await getTargetYoutubeTab();

        if (!tab) {
          const session = await chrome.storage.session.get('sidePanelTabId');
          const dockedId = session.sidePanelTabId;
          if (dockedId != null) {
            try {
              const t = await chrome.tabs.get(dockedId);
              if (t?.url && extractVideoIdFromUrl(t.url)) tab = t;
            } catch (e) {
              /* tab closed */
            }
          }
        }

        if (!tab?.url) {
          sendResponse({ ok: false, reason: 'no_tab' });
          return;
        }

        const videoId = extractVideoIdFromUrl(tab.url);
        if (!videoId) {
          sendResponse({ ok: false, reason: 'no_video_in_url' });
          return;
        }

        const key = `video_${tab.id}`;
        const data = await chrome.storage.local.get(key);
        const stored = data[key];

        let videoTitle = stored?.videoTitle || 'YouTube Video';
        let videoUrl = tab.url;

        if (!stored || stored.videoId !== videoId) {
          const oembedTitle = await fetchTitleOembed(videoUrl);
          if (oembedTitle) videoTitle = oembedTitle;

          await chrome.storage.local.set({
            [key]: {
              videoId,
              videoUrl,
              videoTitle,
              updated: Date.now(),
            },
            currentVideoId: videoId,
            currentVideoUrl: videoUrl,
            currentVideoTitle: videoTitle,
          });

          chrome.tabs.sendMessage(tab.id, { type: 'YT_FORCE_REFRESH' }).catch(() => {});
        }

        sendResponse({
          ok: true,
          videoId,
          videoUrl,
          videoTitle,
          tabId: tab.id,
        });
      } catch (e) {
        console.error('[ServiceWorker] GET_VIDEO_FOR_PANEL', e);
        sendResponse({ ok: false, reason: String(e) });
      }
    })();
    return true;
  }

  return false;
});

chrome.action.onClicked.addListener((tab) => {
  if (tab.id != null) {
    chrome.storage.session.set({ sidePanelTabId: tab.id });
  }

  if (tab.url && tab.url.includes('youtube.com')) {
    chrome.sidePanel.open({ tabId: tab.id }).catch((err) => {
      console.error('[ServiceWorker] Failed to open side panel:', err);
    });
  } else {
    console.log('[ServiceWorker] Not a YouTube URL');
  }
});

// YouTube SPA: history.pushState navigation does not always fire events the content script listens to.
chrome.webNavigation.onHistoryStateUpdated.addListener((details) => {
  if (details.frameId !== 0) return;
  const url = details.url || '';
  if (!url.includes('youtube.com/watch') && !url.includes('youtu.be/')) return;

  chrome.tabs
    .sendMessage(details.tabId, { type: 'YT_FORCE_REFRESH' })
    .catch(() => {});
});
