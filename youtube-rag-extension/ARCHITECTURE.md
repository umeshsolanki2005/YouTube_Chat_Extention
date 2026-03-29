# Architecture Diagram & System Overview

## 🏗️ Complete System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CHROME BROWSER                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              CHROME EXTENSION (MV3)                           │   │
│  │  ┌────────────────────────────────────────────────────────┐  │   │
│  │  │  BACKGROUND: service-worker.js                         │  │   │
│  │  │  • Stores video info in Chrome storage                 │  │   │
│  │  │  • Manages side panel opening                          │  │   │
│  │  │  • Listens for content script messages                 │  │   │
│  │  └────────────────────────────────────────────────────────┘  │   │
│  │                                                                │   │
│  │  ┌────────────────────────────────────────────────────────┐  │   │
│  │  │  CONTENT SCRIPT: content.js (runs on YouTube)          │  │   │
│  │  │  • Detects current video ID from URL                   │  │   │
│  │  │  • Gets video title from DOM                           │  │   │
│  │  │  • Monitors YouTube navigation (SPA)                   │  │   │
│  │  │  • Notifies service worker of video changes            │  │   │
│  │  └────────────────────────────────────────────────────────┘  │   │
│  │                                                                │   │
│  │  ┌────────────────────────────────────────────────────────┐  │   │
│  │  │  SIDE PANEL UI: sidepanel.html/js/css                  │  │   │
│  │  │  • Displays current video info                          │  │   │
│  │  │  • Text input for user questions                        │  │   │
│  │  │  • Chat history display                                 │  │   │
│  │  │  • Loading/error states                                 │  │   │
│  │  │  • Calls backend API                                    │  │   │
│  │  └────────────────────────────────────────────────────────┘  │   │
│  │                                                                │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  Chrome Storage:                                                      │
│  • currentVideoId                                                    │
│  • currentVideoUrl                                                   │
│  • currentVideoTitle                                                 │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  │ HTTP POST /ask
                                  │ {video_id, video_url, question}
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    PYTHON BACKEND (localhost:8000)                   │
│                                  FastAPI                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │  HTTP ENDPOINTS:                                           │    │
│  │  • GET  /health           (health check)                   │    │
│  │  • POST /ask              (main endpoint)                  │    │
│  │  • GET  /status           (cache info)                     │    │
│  │  • GET  /docs             (API documentation)              │    │
│  └────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │  RAG PIPELINE: rag_pipeline.py                             │    │
│  │                                                             │    │
│  │  1. CHECK CACHE                                            │    │
│  │     └─ Key: video_id                                       │    │
│  │     └─ If found: Skip to retrieval                         │    │
│  │                                                             │    │
│  │  2. PROCESS NEW VIDEO (First request)                      │    │
│  │     ├─ Fetch Transcript                                    │    │
│  │     │  └─ youtube-transcript-api                           │    │
│  │     │  └─ Combines all captions into text                  │    │
│  │     │                                                       │    │
│  │     ├─ Split Text                                          │    │
│  │     │  └─ RecursiveCharacterTextSplitter (LangChain)       │    │
│  │     │  └─ Chunks: 1000 chars, 200 char overlap             │    │
│  │     │  └─ Preserves semantic units (paragraphs)            │    │
│  │     │                                                       │    │
│  │     ├─ Create Embeddings                                   │    │
│  │     │  └─ GoogleGenerativeAIEmbeddings                     │    │
│  │     │  └─ Converts each chunk to vector                    │    │
│  │     │                                                       │    │
│  │     └─ Build Vector Store                                  │    │
│  │        └─ FAISS (Facebook AI Similarity Search)            │    │
│  │        └─ Enables fast semantic search                     │    │
│  │        └─ Store in cache[video_id]                         │    │
│  │                                                             │    │
│  │  3. RETRIEVE (All requests)                                │    │
│  │     ├─ Similarity Search                                   │    │
│  │     │  └─ Find top-k chunks similar to question            │    │
│  │     │  └─ k=3 by default (configurable)                    │    │
│  │     │  └─ Returns ranked documents                         │    │
│  │     │                                                       │    │
│  │  4. GENERATE ANSWER (All requests)                         │    │
│  │     ├─ Format Prompt                                       │    │
│  │     │  └─ System: "Answer only from context"               │    │
│  │     │  └─ Context: Retrieved chunks                        │    │
│  │     │  └─ Question: User's question                        │    │
│  │     │                                                       │    │
│  │     └─ Call LLM                                            │    │
│  │        └─ ChatGoogleGenerativeAI (Gemini)                  │    │
│  │        └─ Returns generated answer                         │    │
│  │                                                             │    │
│  └────────────────────────────────────────────────────────────┘    │
│                                                                       │
│  Memory Cache (in-memory dict):                                      │
│  {                                                                   │
│    "video_id_1": {                                                  │
│      "vectorstore": FAISS,                                          │
│      "transcript": "full transcript text",                          │
│      "chunks": ["chunk1", "chunk2", ...]                           │
│    },                                                               │
│    "video_id_2": { ... }                                            │
│  }                                                                   │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  │ HTTP Response
                                  │ {answer: "..."}
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      RESPONSE → SIDE PANEL                           │
│                    Display answer in chat                            │
└─────────────────────────────────────────────────────────────────────┘
```

## 📊 Data Flow Sequence

### User Asks a Question

```
1. User types "What is this video about?"
   └─ In sidepanel.html textarea
   
2. User clicks "Ask" button
   └─ Triggers sidepanel.js:handleAsk()
   
3. sidepanel.js validates input
   └─ Checks video_id exists
   └─ Checks question is not empty
   └─ Checks debounce (prevent rapid duplicate requests)
   
4. Add user message to chat history
   └─ Show in UI immediately
   
5. Fetch POST http://localhost:8000/ask
   └─ Body: {video_id, video_url, question}
   └─ Shows loading spinner
   └─ Disables input while loading
   
6. Backend receives request in app.py:/ask
   └─ Validates inputs
   └─ Calls RAGPipeline.answer_question()
   
7a. Check if video_id in cache
    └─ YES: Use cached vectorstore
    └─ NO: Call _process_video()
    
7b. _process_video() steps (5-10 seconds):
    ├─ _fetch_transcript(video_id)
    │  └─ YouTube API returns captions
    │  └─ Combine into single text
    │
    ├─ _split_text(text)
    │  └─ Recursive character splitting
    │  └─ Returns list of chunks
    │
    ├─ _create_vectorstore(chunks)
    │  └─ Generate embeddings for each chunk
    │  └─ Build FAISS index
    │  └─ Cache[video_id] = vectorstore
    │
    └─ Return from _process_video()
    
8. vectorstore.similarity_search(question, k=3)
   └─ Find 3 most similar chunks
   └─ Uses semantic similarity
   └─ Returns LangChain Document objects
   
9. _generate_answer(question, docs)
   └─ Format prompt with context
   └─ Call ChatGoogleGenerativeAI.invoke()
   └─ LLM generates answer
   └─ Return as string
   
10. Return {"answer": "..."} to frontend
    └─ HTTP 200 response
    
11. sidepanel.js receives response
    └─ Remove loading spinner
    └─ Enable input
    └─ addMessageToHistory("assistant", answer)
    
12. Display answer in chat
    └─ User sees answer immediately
    
Time breakdown:
- First question on new video: 5-10 seconds
  ├─ Fetch transcript: 2-3 seconds
  ├─ Create embeddings: 2-3 seconds
  └─ Retrieve + generate: 1-2 seconds
  
- Subsequent questions on same video: 1-2 seconds
  ├─ Skip to retrieval (cache hit)
  └─ Retrieve + generate: 1-2 seconds
```

### Video Detection Process

```
1. Browser navigates to YouTube
   └─ content.js script loads
   
2. getVideoIdFromUrl()
   └─ Tries different URL patterns:
      ├─ youtube.com/watch?v=ID
      ├─ youtu.be/ID
      └─ youtube.com/embed/ID
   └─ Extracts video ID
   
3. getVideoTitle()
   └─ Query DOM for title element
   └─ Try multiple selectors
   └─ Fallback to "YouTube Video"
   
4. notifyVideoInfo()
   └─ Send message to service worker
   └─ chrome.runtime.sendMessage({
       type: 'UPDATE_VIDEO_INFO',
       videoId: "dQw4w9WgXcQ",
       videoUrl: "https://...",
       videoTitle: "Video Title"
     })
   
5. service-worker.js receives message
   └─ Extract video info
   └─ Store in Chrome storage
   └─ chrome.storage.local.set({
       currentVideoId: "dQw4w9WgXcQ",
       ...
     })
   
6. sidepanel.js listens for storage changes
   └─ chrome.storage.onChanged.addListener()
   └─ Update video display
   └─ Clear old chat history
   
Continuous monitoring:
- setInterval: Check URL every 1 second
- popstate listener: Detect back/forward
- Updates when URL changes
- Handles YouTube SPA navigation
```

## 🔄 Cache Behavior

```
Video 1 (dQw4w9WgXcQ):
├─ First question: "How long is this?"
│  └─ Cache miss
│  └─ Fetch transcript (3s)
│  └─ Create embeddings (3s)
│  └─ Retrieve + answer (2s)
│  └─ Total: ~8 seconds
│  └─ Store in cache[video_id]
│
├─ Second question: "Who is in this?"
│  └─ Cache hit!
│  └─ Use cached vectorstore
│  └─ Retrieve + answer (1s)
│  └─ Total: ~1 second (7s faster!)
│
├─ Third question: "What's the topic?"
│  └─ Cache hit!
│  └─ Retrieve + answer (1s)
│  └─ Total: ~1 second
│
└─ Cache persists until:
   ├─ User restarts backend (python app.py)
   └─ Programmatic clear_cache() call

Video 2 (different video):
├─ Switch to Video 2
├─ Storage change detected
├─ Chat history cleared
├─ First question on Video 2
│  └─ Cache(Video 2) = miss
│  └─ Process Video 2 (8s)
│  └─ Answer (2s)
└─ Now both videos cached for fast retrieval

Cache memory usage:
- Small transcripts: ~1-5 MB per video
- With FAISS index
- Most videos fit easily in RAM
```

## 🔌 API Endpoints Detailed

### POST /ask (Main Endpoint)

```
REQUEST:
POST http://localhost:8000/ask
Content-Type: application/json

{
  "video_id": "dQw4w9WgXcQ",
  "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "question": "What is this video about?"
}

RESPONSE (200 OK):
{
  "answer": "This video is a popular rickroll which typically plays... [LLM-generated answer]"
}

ERROR RESPONSES:
400 Bad Request:
  {
    "detail": "video_id and question are required"
  }

500 Internal Server Error:
  {
    "detail": "Error processing your question: [specific error]"
  }

Possible errors:
- "Transcript not available for this video"
- "Invalid video ID or video not found"
- "Failed to fetch transcript: [error]"
- "Error generating answer from Gemini: [error]"
- "Error processing your question: [error]"
```

### GET /health (Health Check)

```
REQUEST:
GET http://localhost:8000/health

RESPONSE (200 OK):
{
  "status": "healthy",
  "message": "YouTube RAG Backend is running"
}

Used by:
- Chrome extension on startup
- To verify backend is running
- Called when extension first opens
```

### GET /status (Status Info)

```
REQUEST:
GET http://localhost:8000/status

RESPONSE (200 OK):
{
  "status": "running",
  "cached_videos": 3,
  "gemini_configured": true
}

Shows:
- System status
- Number of cached videos
- Whether Gemini is properly configured
- Useful for debugging
```

### GET /docs (API Documentation)

```
REQUEST:
GET http://localhost:8000/docs

Shows:
- Interactive Swagger UI
- All available endpoints
- Request/response schemas
- Try it out feature
- Useful for debugging API

URL: http://localhost:8000/docs
```

## ⚙️ Configuration Points

```
sidepanel.js (Frontend):
- Line 7: BACKEND_URL = 'http://localhost:8000'
  └─ Change for production

sidepanel.js (Frontend):
- Line 11: DEBOUNCE_DELAY = 1000
  └─ Prevent rapid duplicate requests

rag_pipeline.py (Backend):
- Line 18: chunk_size = 1000
  └─ Characters per chunk
  └─ Smaller = more chunks, larger = more context
  
- Line 19: chunk_overlap = 200
  └─ Overlap between chunks
  └─ Prevents context loss at boundaries
  
- Line 20: retrieval_k = 3
  └─ Number of chunks to retrieve
  └─ More = more context but slower

rag_pipeline.py (Backend):
- Line 61: "models/embedding-001"
  └─ Gemini embedding model
  └─ Only option from Google
  
- Line 66: "gemini-pro"
  └─ Gemini model for chat
  └─ Could upgrade to gemini-pro-vision
  
- Line 68: temperature = 0.3
  └─ Determines randomness
  └─ Lower (0.1) = more deterministic
  └─ Higher (0.9) = more creative

rag_pipeline.py (Backend):
- Line 69: convert_system_message_to_human = True
  └─ Gemini doesn't support system messages
  └─ Convert to human messages

app.py (Backend):
- Line 13: allow_origins = ["*"]
  └─ CORS setting
  └─ Change to specific domain for production
  └─ Example: ["https://example.com"]
```

## 🎬 Component Interaction Map

```
     User Types Question
              │
              ▼
       sidepanel.js UI
    (handleAsk function)
              │
              ▼
    Validate + Debounce
              │
              ▼
    POST /ask to Backend
              │
              ▼
    app.py:/ask endpoint
              │
              ▼
    rag_pipeline.answer_question()
              │
              ├─ Check Cache
              │  └─ Hit? Use cached vectorstore
              │  └─ Miss? Call _process_video()
              │
              ├─ _fetch_transcript()
              │  └─ youtube-transcript-api
              │
              ├─ _split_text()
              │  └─ RecursiveCharacterTextSplitter
              │
              ├─ _create_vectorstore()
              │  └─ GoogleGenerativeAIEmbeddings
              │  └─ FAISS
              │  └─ Store in cache
              │
              ├─ vectorstore.similarity_search()
              │  └─ Get top-k chunks
              │
              └─ _generate_answer()
                 ├─ Format prompt
                 └─ ChatGoogleGenerativeAI
                    └─ Gemini API
                       └─ Generates answer
              │
              ▼
    Return {"answer": "..."}
              │
              ▼
    sidepanel.js receives
              │
              ▼
    addMessageToHistory()
              │
              ▼
    Display in chat UI
              │
              ▼
    User sees answer!
```

---

**This architecture is designed for:**
- ✓ Security (no API keys in extension)
- ✓ Performance (caching reduces latency)
- ✓ Reliability (error handling at each layer)
- ✓ Scalability (backend can be deployed separately)
- ✓ Maintainability (clean separation of concerns)
