/**
 * Side Panel Script for YouTube RAG Chatbot
 * Handles:
 * - Displaying current video info
 * - User input for questions
 * - Communication with Python backend
 * - Chat history display
 * - Loading and error states
 */

const BACKEND_URL = 'http://localhost:8000';
const DEBOUNCE_DELAY = 1000;

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

// Extract video ID from URL
function extractVideoIdFromUrl(url) {
  try {
    const urlObj = new URL(url);
    
    // Method 1: youtube.com/watch?v=VIDEO_ID
    if (urlObj.hostname.includes('youtube.com')) {
      const videoId = urlObj.searchParams.get('v');
      if (videoId) {
        console.log('[SidePanel] Video ID from youtube.com:', videoId);
        return videoId;
      }
    }
    
    // Method 2: youtu.be/VIDEO_ID
    if (urlObj.hostname.includes('youtu.be')) {
      const videoId = urlObj.pathname.slice(1);
      if (videoId) {
        console.log('[SidePanel] Video ID from youtu.be:', videoId);
        return videoId;
      }
    }
  } catch (error) {
    console.error('[SidePanel] Error extracting video ID:', error);
  }
  
  return null;
}

// Get current active tab's video info directly
function getTabVideoInfo() {
  console.log('[SidePanel] Getting tab info...');
  
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (tabs && tabs[0]) {
      const tab = tabs[0];
      console.log('[SidePanel] Current tab URL:', tab.url);
      
      const videoId = extractVideoIdFromUrl(tab.url);
      
      if (videoId) {
        currentVideoId = videoId;
        currentVideoUrl = tab.url;
        
        // Update UI
        videoIdEl.textContent = `ID: ${videoId}`;
        videoIdEl.style.display = 'block';
        questionInputEl.disabled = false;
        askButtonEl.disabled = false;
        
        console.log('[SidePanel] Successfully detected video:', videoId);
      } else {
        // No video detected
        videoIdEl.textContent = 'No video ID detected';
        videoIdEl.style.display = 'block';
        questionInputEl.disabled = true;
        askButtonEl.disabled = true;
        
        console.log('[SidePanel] No video detected on current tab');
      }
    }
    
    // Check backend health
    checkBackendHealth();
  });
}

console.log('[SidePanel] Script loaded');

// Initialize on panel open
getTabVideoInfo();

// Periodically refresh (every 2 seconds)
setInterval(() => {
  console.log('[SidePanel] Periodic refresh...');
  getTabVideoInfo();
}, 2000);

// Check if backend is running
async function checkBackendHealth() {
  try {
    const response = await fetch(`${BACKEND_URL}/health`);
    if (response.ok) {
      statusBadgeEl.textContent = 'Ready';
      statusBadgeEl.classList.remove('error');
      backendStatusEl.textContent = '✓ Backend connected';
      backendStatusEl.classList.remove('error');
    }
  } catch (error) {
    statusBadgeEl.textContent = 'Backend Error';
    statusBadgeEl.classList.add('error');
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
    if (error.message.includes('Failed to fetch')) {
      errorMsg = `Cannot connect to backend at ${BACKEND_URL}. Make sure the Python FastAPI server is running.`;
    }
    
    showError(errorMsg);
    updateBackendStatus('error', errorMsg);
    
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
  askButtonEl.disabled = loading;
  questionInputEl.disabled = loading;
  
  if (loading) {
    statusBadgeEl.textContent = 'Loading...';
  } else {
    statusBadgeEl.textContent = 'Ready';
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

// Backend status
function updateBackendStatus(status, message = '') {
  if (status === 'success') {
    backendStatusEl.textContent = '✓ Backend connected and responding';
    backendStatusEl.classList.remove('error');
  } else if (status === 'error') {
    backendStatusEl.textContent = '✗ Backend error: ' + message;
    backendStatusEl.classList.add('error');
  }
}

// Check backend health periodically
setInterval(checkBackendHealth, 10000);
