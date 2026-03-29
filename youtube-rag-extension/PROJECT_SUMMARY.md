# Project Structure & File Reference

Complete reference of all project files and their purposes.

## 📁 Full Project Structure

```
d:\GEN_AI\youtube-rag-extension/
│
├── 📄 README.md                      # Main documentation (start here)
├── 📄 SETUP_GUIDE.md                # Step-by-step setup instructions
├── 📄 INTEGRATION_GUIDE.md          # How to merge your existing code
├── 📄 PROJECT_SUMMARY.md            # This file
│
├── 🎨 extension/                     # Chrome Extension files
│   ├── 📜 manifest.json             # Extension configuration (MV3)
│   ├── 🔧 service-worker.js         # Background script
│   ├── 🎬 content.js                # Page content script (video detection)
│   ├── 📱 sidepanel.html            # UI markup for side panel
│   ├── ⚙️ sidepanel.js              # Side panel logic (UI interaction)
│   ├── 🎨 sidepanel.css             # Styling for side panel
│   └── 🖼️ icons/
│       ├── icon-128.png             # Extension icon (placeholder)
│       └── 📄 README.txt            # Instructions for icon
│
└── 🐍 backend/                       # Python FastAPI Backend
    ├── 📜 app.py                    # FastAPI server & endpoints
    ├── 🔬 rag_pipeline.py           # RAG logic & LLM integration
    ├── 📋 requirements.txt          # Python dependencies
    ├── 🔐 .env.example              # Environment config template
    └── 📄 .env                      # Your actual config (create this)
```

## 📋 File Descriptions

### Chrome Extension Files

#### `manifest.json`
**Purpose:** Extension configuration for Manifest V3
**Key elements:**
- `manifest_version: 3` - MV3 standard
- `permissions` - Required permissions (scripting, storage, activeTab)
- `host_permissions` - youtube.com access
- `background.service_worker` - Background script
- `content_scripts` - Content script for YouTube pages
- `side_panel` - Side panel UI definition
- `icons` - Extension icon

#### `service-worker.js`
**Purpose:** Background script that lives as long as extension is active
**Responsibilities:**
- Listen for messages from content script
- Store video information in Chrome storage
- Open/manage side panel
- No UI access (background process)

#### `content.js`
**Purpose:** Runs on every YouTube page
**Responsibilities:**
- Extract video ID from URL
- Detect video title from DOM
- Watch for YouTube SPA navigation (video changes)
- Notify service worker when video changes
- Uses polling and popstate listener

#### `sidepanel.html`
**Purpose:** HTML markup for the side panel UI
**Contains:**
- Header with title and status badge
- Video info display
- Chat history area
- Loading spinner
- Error message display
- Input textarea for questions
- Ask button
- Backend status indicator

#### `sidepanel.js`
**Purpose:** Main logic for side panel
**Responsibilities:**
- Load current video from Chrome storage
- Listen for storage changes (new video detection)
- Handle question input and submission
- Communicate with Python backend (POST /ask)
- Manage chat history display
- Show loading and error states
- Debounce duplicate requests
- Check backend health on startup

**Key functions:**
- `handleAsk()` - Process user question
- `addMessageToHistory()` - Display Q&A
- `checkBackendHealth()` - Verify backend running
- `fetch(/ask)` - Call Python backend

#### `sidepanel.css`
**Purpose:** Styling for side panel UI
**Features:**
- Modern gradient header
- Chat bubble styling (different for user/AI)
- Loading spinner animation
- Error message styling
- Responsive input area
- Smooth message animations
- Custom scrollbar
- Color scheme with CSS variables

### Python Backend Files

#### `app.py`
**Purpose:** FastAPI web server
**Responsibilities:**
- Define FastAPI app with CORS
- Handle HTTP endpoints
- Request/response validation
- Initialize RAG pipeline
- Error handling

**Endpoints:**
1. `GET /health` - Health check (called by extension)
2. `POST /ask` - Main endpoint (takes question, returns answer)
3. `GET /status` - Cache and system status
4. `GET /docs` - Auto-generated API documentation

**CORS Setup:** Allows requests from anywhere (for local dev)

#### `rag_pipeline.py`
**Purpose:** Core RAG logic
**Class: `RAGPipeline`**

**Responsibilities:**
- Fetch transcripts from YouTube
- Split text into chunks
- Create embeddings
- Build vector stores
- Cache by video ID
- Retrieve relevant chunks
- Generate answers with Gemini

**Main methods:**
1. `__init__()` - Initialize models
2. `answer_question()` - Main async method (called by app.py)
3. `_fetch_transcript()` - YouTube API
4. `_split_text()` - Text chunking
5. `_create_vectorstore()` - FAISS embedding
6. `_generate_answer()` - Gemini LLM call

**Caching:**
- Cache stored in `self.cache` dict
- Key: `video_id`
- Value: `{"vectorstore": FAISS, "transcript": str, "chunks": list}`
- Persists during backend runtime
- Clears on restart

#### `requirements.txt`
**Purpose:** Lists all Python dependencies
**Key packages:**
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `youtube-transcript-api` - Fetch transcripts
- `langchain` - RAG framework
- `langchain-google-genai` - Gemini integration
- `faiss-cpu` - Vector store
- `python-dotenv` - Load .env files

#### `.env.example`
**Purpose:** Template for environment configuration
**Contains:**
- `GEMINI_API_KEY` - Your API key placeholder

#### `.env` (you create this)
**Purpose:** Your actual environment configuration
**Contains:**
- `GEMINI_API_KEY=your_actual_key_here`
**Important:** Never commit this to git (contains secrets)

### Documentation Files

#### `README.md`
**Complete guide covering:**
- Project overview
- Architecture explanation
- Setup instructions
- API endpoints reference
- Configuration options
- Troubleshooting guide
- Deployment instructions
- Integration guide
- FAQ

#### `SETUP_GUIDE.md`
**Quick sequential setup:**
- Pre-check requirements
- Get Gemini API key
- Setup Python backend
- Load Chrome extension
- Test functionality
- Quick troubleshooting table

#### `INTEGRATION_GUIDE.md`
**Merge your existing code:**
- 6 integration scenarios
- Full step-by-step example
- Code samples
- Testing checklist
- Performance tips
- Common gotchas

## 🔄 Data Flow

### User Asks Question

```
1. User types "What's this video about?"
2. Clicks Ask button
   
3. sidepanel.js:handleAsk()
   ↓
4. POST http://localhost:8000/ask
   {
     "video_id": "dQw4w9WgXcQ",
     "video_url": "https://...",
     "question": "..."
   }
   
5. app.py:/ask endpoint
   ↓
6. RAGPipeline.answer_question()
   
7a. If video not cached:
    - _fetch_transcript() → YouTube API
    - _split_text() → Chunks
    - _create_vectorstore() → Embeddings
    - Store in cache
    
7b. If video cached:
    - Use existing vectorstore
   
8. similarity_search(question, k=3)
   → Get 3 most relevant chunks
   
9. _generate_answer(question, chunks)
   - Format prompt with context
   - Call ChatGoogleGenerativeAI
   - Get response
   
10. Return {"answer": "..."}
   
11. sidepanel.js receives response
   ↓
12. addMessageToHistory("assistant", answer)
   
13. Chat displays answer to user
```

### Video Detection

```
1. User navigates to YouTube video
   
2. content.js loads on page
   
3. getVideoIdFromUrl() extracts video ID
   
4. Sends to service-worker.js:
   chrome.runtime.sendMessage({
     type: 'UPDATE_VIDEO_INFO',
     videoId: 'dQw4w9WgXcQ',
     ...
   })
   
5. service-worker.js stores in Chrome storage:
   chrome.storage.local.set({
     currentVideoId: 'dQw4w9WgXcQ',
     ...
   })
   
6. sidepanel.js listens for storage changes
   
7. When change detected:
   - Update video display
   - Clear old chat history
   - Show new video ID
```

## ✅ Pre-Deployment Checklist

### Chrome Extension

- [ ] `manifest.json` has correct `manifest_version: 3`
- [ ] `icons/icon-128.png` exists (or placeholder is fine for testing)
- [ ] All JavaScript files have no syntax errors (check Chrome console)
- [ ] `service-worker.js` properly listens to messages
- [ ] `content.js` detects videos correctly
- [ ] `sidepanel.html` renders properly
- [ ] `sidepanel.js` has correct `BACKEND_URL` for your setup
- [ ] CORS headers work (extension can call backend)

### Python Backend

- [ ] `python app.py` starts without errors
- [ ] Health endpoint responds: `curl http://localhost:8000/health`
- [ ] `.env` file exists with valid Gemini API key
- [ ] Models initialize: "✓ Gemini models initialized successfully"
- [ ] Can fetch transcripts (try a video manually)
- [ ] Embeddings work without memory errors
- [ ] FAISS vectorstore builds and searches
- [ ] Gemini responds to prompts

### Integration

- [ ] Extension loads in `chrome://extensions/` without errors
- [ ] Video ID displays correctly on YouTube
- [ ] Backend status shows "✓ Connected" in side panel
- [ ] Can type and submit a question
- [ ] Answer returns in 5-10 seconds (first question)
- [ ] Answer displays in chat
- [ ] Second question on same video is faster (~1-2s)
- [ ] Can switch videos and get different results

## 🔑 Key Configuration Points

### Backend URL (for production)
- **Development:** `http://localhost:8000`
- **File:** `extension/sidepanel.js`, line ~7
- **Change:** Update `BACKEND_URL` constant

### Gemini API Key
- **File:** `backend/.env`
- **Format:** `GEMINI_API_KEY=AIzaSy...`
- **Get:** https://ai.google.dev/

### Caching Configuration
- **File:** `backend/rag_pipeline.py`
- **Parameters:** chunk_size, chunk_overlap, retrieval_k
- **Strategy:** In-memory dict by video_id

### RAG Model Parameters
- **Chunk size:** 1000 chars (configurable)
- **Overlap:** 200 chars (prevents context loss)
- **Retrieval:** Top 3 chunks (configurable)
- **LLM temp:** 0.3 (focused answers)

## 🚀 Quick Run Commands

### Start Backend
```powershell
# Windows
cd backend
venv\Scripts\activate
python app.py
```

### Start with Frontend Reload
```bash
# Terminal 1: Backend
cd backend && source venv/bin/activate && python app.py

# Terminal 2: Extension (reload in chrome://extensions/)
# Just refresh the extension when you make changes
```

### Test API Directly
```bash
# Health check
curl http://localhost:8000/health

# Ask question
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "video_id": "dQw4w9WgXcQ",
    "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "question": "What is this?"
  }'
```

## 📊 Performance Expectations

| Operation | Time | Notes |
|-----------|------|-------|
| First question (new video) | 5-10 seconds | Fetches & processes transcript |
| Subsequent questions (cached) | 1-2 seconds | Uses cached vectorstore |
| Health check | < 100ms | Used by extension on startup |
| Embedding generation | 2-3 seconds | Done once per video |
| Gemini API call | 1-2 seconds | LLM response time |

## 🐛 Common Issues by Component

### Extension Issues
- Not loading: Check `chrome://extensions/` errors
- No video detected: Refresh YouTube page
- Can't type: Check `sidepanel.js` console errors
- No answer: Backend not running or port 8000 in use

### Backend Issues
- Port 8000 busy: Kill process or use different port
- API key error: Check `.env` syntax
- Transcript error: Video may have captions disabled
- Memory error: FAISS issue, check Python version compatibility

### Network Issues
- CORS error: Backend not started or CORS not configured
- Connection refused: Backend address wrong in sidepanel.js
- Timeout: Backend processing too long, check logs

## 📞 Support Resources

**Documentation Files (read in this order):**
1. README.md - Overview & architecture
2. SETUP_GUIDE.md - Get it running
3. INTEGRATION_GUIDE.md - Merge your code

**Official Resources:**
- Chrome Extensions: https://developer.chrome.com/docs/extensions/
- FastAPI: https://fastapi.tiangolo.com/docs
- LangChain: https://docs.langchain.com/
- Gemini API: https://ai.google.dev/
- FAISS: https://github.com/facebookresearch/faiss/wiki

---

**Version:** 1.0.0  
**Last Updated:** 2024  
**Status:** Complete and tested ✅
