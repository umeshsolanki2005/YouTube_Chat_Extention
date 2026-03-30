/**
 * Side Panel Script for YouTube RAG Chatbot
 * Handles:
 * - Displaying current video info
 * - User input for questions
 * - Communication with deployed backend
 * - Chat history display
 * - Loading and error states
 */

// Backend URL - Update this after deploying to Render
// const BACKEND_URL = 'http://localhost:8000'; // Local development
const BACKEND_URL = 'https://youtube-rag-bot.onrender.com'; // Production

const DEBOUNCE_DELAY = 1000;

/** Last known result of GET /health — used so loading state and badges stay consistent */
let backendReachable = false;

// DOM elements
const videoTitleEl = document.getElementById('videoTitle');
const videoIdEl = document.getElementById('videoId');
const questionInputEl = document.getElementById('questionInput');
const askButtonEl = document.getElementById('askButton');
const chatHistoryEl = document.getElementById('chatHistory');
const errorMessageEl = document.getElementById('errorMessage');
const loadingSpinnerEl = document.getElementById('loadingSpinner');
const statusBadgeEl = document.getElementById('statusBadge');
const backendStatusEl = document.getElementById('backendStatus');

// State management
let currentVideoId = null;
let currentVideoUrl = null;
let isLoading = false;
let lastRequestTime = 0;
let chatHistory = [];

function applyVideoPayload(payload) {
  if (payload?.videoId) {
    currentVideoId = payload.videoId;
    currentVideoUrl = payload.videoUrl || null;
    videoTitleEl.textContent = payload.videoTitle || 'YouTube Video';
    videoIdEl.textContent = `ID: ${payload.videoId}`;
    videoIdEl.style.display = 'block';
    questionInputEl.disabled = false;
    askButtonEl.disabled = false;
    console.info('[SidePanel] Video:', payload.videoId, payload.videoTitle);
  } else {
    currentVideoId = null;
    currentVideoUrl = null;
    videoTitleEl.textContent = 'No video selected';
    videoIdEl.textContent = '';
    videoIdEl.style.display = 'none';
    questionInputEl.disabled = true;
    askButtonEl.disabled = true;
  }
}

/**
 * Resolve video from the service worker using the real tab URL + per-tab cache (avoids stale titles/IDs).
 */
function refreshVideoInfoFromStorage() {
  chrome.runtime.sendMessage({ type: 'GET_VIDEO_FOR_PANEL' }, (response) => {
    if (chrome.runtime.lastError) {
      console.warn('[SidePanel] GET_VIDEO_FOR_PANEL:', chrome.runtime.lastError.message);
      refreshVideoInfoFromStorageFallback(() => checkBackendHealth());
      return;
    }

    if (response?.ok && response.videoId) {
      applyVideoPayload(response);
      checkBackendHealth();
    } else {
      refreshVideoInfoFromStorageFallback(() => checkBackendHealth());
    }
  });
}

function refreshVideoInfoFromStorageFallback(done) {
  chrome.storage.local.get(
    ['currentVideoId', 'currentVideoUrl', 'currentVideoTitle'],
    (data) => {
      if (chrome.runtime.lastError) {
        console.error('[SidePanel] storage:', chrome.runtime.lastError);
        if (done) done();
        return;
      }
      if (data.currentVideoId) {
        applyVideoPayload({
          videoId: data.currentVideoId,
          videoUrl: data.currentVideoUrl,
          videoTitle: data.currentVideoTitle,
        });
      } else {
        applyVideoPayload(null);
      }
      if (done) done();
    }
  );
}

console.log('[SidePanel] Script loaded');

// Initialize on panel open
refreshVideoInfoFromStorage();

chrome.storage.onChanged.addListener((changes, areaName) => {
  if (areaName !== 'local') return;
  if (changes.currentVideoId || changes.currentVideoUrl || changes.currentVideoTitle) {
    refreshVideoInfoFromStorage();
  }
});

// Periodically refresh storage + health (every 2 seconds)
setInterval(() => {
  refreshVideoInfoFromStorage();
}, 2000);

// Check if backend is running
async function checkBackendHealth() {
  try {
    const response = await fetch(`${BACKEND_URL}/health`);
    if (response.ok) {
      backendReachable = true;
      if (!isLoading) {
        statusBadgeEl.textContent = 'Ready';
        statusBadgeEl.classList.remove('error');
      }
      backendStatusEl.textContent = '✓ Backend connected';
      backendStatusEl.classList.remove('error');
      // Stale banner from a failed /ask "connection" error should not contradict health
      const errText = errorMessageEl.textContent || '';
      if (errText.includes('Cannot connect to backend')) {
        clearError();
      }
    } else {
      backendReachable = false;
      if (!isLoading) {
        statusBadgeEl.textContent = 'Backend Error';
        statusBadgeEl.classList.add('error');
      }
      backendStatusEl.textContent = '✗ Backend returned ' + response.status;
      backendStatusEl.classList.add('error');
    }
  } catch (error) {
    backendReachable = false;
    if (!isLoading) {
      statusBadgeEl.textContent = 'Backend offline';
      statusBadgeEl.classList.add('error');
    }
    backendStatusEl.textContent = '✗ Backend not reachable at ' + BACKEND_URL;
    backendStatusEl.classList.add('error');
  }
}

// Ask button click handler
askButtonEl.addEventListener('click', handleAsk);

// Enter key support (Shift+Enter for new line, Enter to submit)
questionInputEl.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    handleAsk();
  }
});

// Debounced ask function
async function handleAsk() {
  const question = questionInputEl.value.trim();
  
  if (!question) {
    showError('Please enter a question');
    return;
  }
  
  if (!currentVideoId) {
    showError('No video detected. Please open a YouTube video first.');
    return;
  }
  
  // Debounce: prevent duplicate requests
  const now = Date.now();
  if (now - lastRequestTime < DEBOUNCE_DELAY) {
    return;
  }
  lastRequestTime = now;
  
  // Disable input while processing
  setLoading(true);
  clearError();
  
  try {
    // Add user message to chat history
    addMessageToHistory('user', question);
    questionInputEl.value = '';
    
    // Call backend
    const response = await fetch(`${BACKEND_URL}/ask`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        video_id: currentVideoId,
        video_url: currentVideoUrl,
        question: question
      })
    });
    
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || `Backend error: ${response.status}`);
    }
    
    const data = await response.json();
    
    // Add assistant message to chat history
    addMessageToHistory('assistant', data.answer);
    
    updateBackendStatus('success');
    
  } catch (error) {
    console.error('Error calling backend:', error);
    
    let errorMsg = error.message;
    
    // Handle specific error types with better user messages
    if (error.message.includes('Failed to fetch')) {
      errorMsg = `Cannot connect to backend at ${BACKEND_URL}. Make sure the Python FastAPI server is running.`;
      backendReachable = false;
    } else if (error.message.includes('Transcript Error')) {
      // Extract the transcript error and provide actionable suggestions
      const transcriptError = error.message.replace('Transcript Error: ', '');
      errorMsg = `📝 Transcript Issue: ${transcriptError.split('\n\n')[0]}`;
      
      // Add suggestions to the error display
      if (transcriptError.includes('Suggestions:')) {
        const suggestions = transcriptError.split('Suggestions:')[1].trim();
        errorMsg += `\n\n💡 Suggestions: ${suggestions}`;
      }
    } else if (error.message.includes('Configuration Error')) {
      errorMsg = `⚙️ Configuration Error: Please check your backend setup and API keys.`;
    } else if (error.message.includes('AI Generation Error')) {
      errorMsg = `🤖 AI Error: Unable to generate response. Please try again.`;
    }
    
    showError(errorMsg);
    // Short footer only — full text stays in the banner (avoids two identical red blocks)
    backendStatusEl.textContent = '✗ Last request failed — see message above';
    backendStatusEl.classList.add('error');
    
    // Remove the user message from history on error
    if (chatHistory.length > 0 && chatHistory[chatHistory.length - 1].role === 'user') {
      chatHistory.pop();
      renderChatHistory();
    }
  } finally {
    setLoading(false);
  }
}

// Add message to chat history
function addMessageToHistory(role, content) {
  chatHistory.push({ role, content });
  renderChatHistory();
  
  // Auto-scroll to bottom
  setTimeout(() => {
    chatHistoryEl.scrollTop = chatHistoryEl.scrollHeight;
  }, 100);
}

// Render chat history
function renderChatHistory() {
  chatHistoryEl.innerHTML = '';
  
  chatHistory.forEach((msg) => {
    const msgEl = document.createElement('div');
    msgEl.className = `message ${msg.role}-message`;
    
    const contentEl = document.createElement('div');
    contentEl.className = 'message-content';
    contentEl.textContent = msg.content;
    
    msgEl.appendChild(contentEl);
    chatHistoryEl.appendChild(msgEl);
  });
}

// Clear chat history
function clearChatHistory() {
  chatHistory = [];
  chatHistoryEl.innerHTML = '';
  clearError();
}

// Loading state
function setLoading(loading) {
  isLoading = loading;
  loadingSpinnerEl.style.display = loading ? 'flex' : 'none';
  const blockInput = loading || !currentVideoId;
  askButtonEl.disabled = blockInput;
  questionInputEl.disabled = blockInput;
  
  if (loading) {
    statusBadgeEl.textContent = 'Loading...';
    statusBadgeEl.classList.remove('error');
  } else {
    statusBadgeEl.textContent = backendReachable ? 'Ready' : 'Backend offline';
    if (backendReachable) {
      statusBadgeEl.classList.remove('error');
    } else {
      statusBadgeEl.classList.add('error');
    }
  }
}

// Error display
function showError(message) {
  errorMessageEl.textContent = '⚠️ ' + message;
  errorMessageEl.style.display = 'block';
}

function clearError() {
  errorMessageEl.style.display = 'none';
  errorMessageEl.textContent = '';
}

// Backend status (after a successful /ask only; connection errors use the banner + short footer)
function updateBackendStatus(status) {
  if (status === 'success') {
    backendStatusEl.textContent = '✓ Backend connected and responding';
    backendStatusEl.classList.remove('error');
  }
}

