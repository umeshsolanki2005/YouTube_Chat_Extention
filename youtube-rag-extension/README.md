# YouTube Transcript RAG Chatbot - Chrome Extension + Python Backend

A complete Chrome extension that lets you ask questions about YouTube video transcripts using AI. The extension detects the current video, sends your question to a Python backend, and returns AI-generated answers based on the video content.

## 🎯 Features

- **Chrome Manifest V3** extension with side panel UI
- **Real-time video detection** - Automatically detects YouTube videos as you navigate
- **Side panel chat interface** - Ask questions without leaving YouTube
- **Python FastAPI backend** - Handles all RAG processing
- **Smart caching** - Video data cached by ID to avoid reprocessing
- **Gemini integration** - Uses Google's Gemini API for answer generation
- **FAISS vector store** - Fast similarity search for relevant transcript chunks
- **Error handling** - Graceful handling of unavailable transcripts and API errors
- **CORS enabled** - Extension can communicate with backend
- **No API keys in extension** - All sensitive keys stay in Python backend

## 📁 Project Structure

```
youtube-rag-extension/
├── extension/                    # Chrome extension files
│   ├── manifest.json            # MV3 configuration
│   ├── service-worker.js        # Background service worker
│   ├── content.js               # Content script (video detection)
│   ├── sidepanel.html           # Side panel UI
│   ├── sidepanel.js             # Side panel logic
│   ├── sidepanel.css            # Styling
│   └── icons/                   # Extension icons
│       └── icon-128.png         # Icon placeholder
├── backend/                     # Python FastAPI backend
│   ├── app.py                   # FastAPI server & endpoints
│   ├── rag_pipeline.py          # RAG pipeline logic
│   ├── requirements.txt         # Python dependencies
│   └── .env.example            # Environment config template
└── README.md                    # This file
```

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- Chrome or Chromium browser
- Google Gemini API key (free tier available)

### Backend Setup

#### 1. Create Python Virtual Environment
```bash
cd backend
python -m venv venv

# On Windows:
venv\Scripts\activate

# On Mac/Linux:
source venv/bin/activate
```

#### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

#### 3. Configure Environment
Copy `.env.example` to `.env` and add your Gemini API key:
```bash
cp .env.example .env
```

Edit `.env`:
```
GEMINI_API_KEY=your_gemini_api_key_here
```

**Get a free Gemini API key:**
1. Go to [Google AI Studio](https://ai.google.dev/)
2. Click "Get API Key"
3. Create a new API key
4. Copy and paste it into `.env`

#### 4. Run the Backend Server
```bash
python app.py
```

You should see:
```
🚀 Starting YouTube RAG Backend...
📍 Server: http://localhost:8000
✓ Ready to accept requests from Chrome extension
```

The backend will be running on `http://localhost:8000`

### Chrome Extension Setup

#### 1. Navigate to Extension Management
1. Open Chrome
2. Go to `chrome://extensions/`
3. Enable "Developer mode" (top right toggle)

#### 2. Load the Extension
1. Click "Load unpacked"
2. Navigate to your `youtube-rag-extension/extension` folder and select it
3. The extension should appear in your list

#### 3. Verify Installation
- You should see the extension icon in your Chrome toolbar
- Try visiting a YouTube video

### Usage

1. **Go to a YouTube video**
   - Navigate to any YouTube video URL
   - The extension will automatically detect the video ID

2. **Open the Side Panel**
   - Click the extension icon in the toolbar (or press keyboard shortcut)
   - The side panel will open on the right

3. **Ask Questions**
   - Type your question in the text area
   - Click "Ask" or press Enter
   - Wait for the backend to process (first request takes ~5-10s to fetch & process transcript)
   - Your answer appears in the chat

4. **View Chat History**
   - Previous Q&A in current session are shown
   - Chat clears when you navigate to a different video

## 🔧 Architecture

### Backend Flow

```
User Question
      ↓
Chrome Extension (sidepanel.js)
      ↓
FastAPI POST /ask (with video_id, question)
      ↓
RAG Pipeline (rag_pipeline.py)
      ├─ Check: Is video in cache?
      │   ├─ YES → Skip to retrieval
      │   └─ NO ↓
      └─ Fetch & Process:
         ├─ Get YouTube transcript
         ├─ Split into chunks
         ├─ Generate embeddings (Gemini)
         ├─ Create FAISS vector store
         └─ Cache for future use
      ↓
Retrieve (Semantic Search)
      ├─ Find top-k similar chunks to question
      └─ Return relevant context
      ↓
Generate Answer
      ├─ Format prompt: context + question
      ├─ Call Gemini (ChatGoogleGenerativeAI)
      └─ Return answer
      ↓
Response: {"answer": "..."}
      ↓
Chrome Extension displays answer in chat
```

### Caching Strategy

**First request for a video:**
- Fetch transcript (~3-5 seconds)
- Create embeddings (~2-3 seconds)
- Total: ~5-10 seconds

**Subsequent requests for same video:**
- Use cached vector store
- Answer in ~1-2 seconds

Cache stored in memory (resets when backend restarts).

### CORS Setup

The backend uses FastAPI CORS middleware to allow requests from the Chrome extension:

```python
CORSMiddleware(
    allow_origins=["*"],  # In production: specify actual origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

For production deployment, change `allow_origins` to your actual domain.

## 📱 API Endpoints

### POST /ask
**Takes user question, returns AI answer**

Request:
```json
{
  "video_id": "dQw4w9WgXcQ",
  "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "question": "What's the main topic of this video?"
}
```

Response:
```json
{
  "answer": "The video discusses..."
}
```

### GET /health
**Health check - returns 200 if backend is running**

Response:
```json
{
  "status": "healthy",
  "message": "YouTube RAG Backend is running"
}
```

### GET /status
**Get cache info and system status**

Response:
```json
{
  "status": "running",
  "cached_videos": 3,
  "gemini_configured": true
}
```

## ⚙️ Configuration

### Adjusting RAG Parameters

In `backend/rag_pipeline.py`, modify the `RAGPipeline` initialization:

```python
# Constructor parameters:
rag_pipeline = RAGPipeline(
    chunk_size=1000,        # Characters per chunk
    chunk_overlap=200,      # Overlap between chunks
    retrieval_k=3          # Number of chunks to retrieve
)
```

**Recommendations:**
- **chunk_size**: 500-2000 chars (smaller = more chunks, larger = more context)
- **chunk_overlap**: 100-500 chars (prevents losing context at boundaries)
- **retrieval_k**: 2-5 chunks (more chunks = more context but slower)

### Changing Backend URL

For production deployment:

1. **Update extension URL** in `extension/sidepanel.js`:
```javascript
const BACKEND_URL = 'https://your-production-backend.com';
```

2. **Update CORS** in `backend/app.py`:
```python
CORSMiddleware(
    allow_origins=["https://your-extension-domain.com"],
    ...
)
```

## 🔌 How to Integrate Your Existing RAG Code

If you already have a working RAG chatbot from Colab/VS Code, here's how to merge it:

### Option 1: Replace the RAG Pipeline

In `backend/rag_pipeline.py`, replace the `_generate_answer` method:

```python
async def _generate_answer(self, question: str, docs: list) -> str:
    # Your existing answer generation code here
    # Make sure it returns a string
    
    context = "\n".join([doc.page_content for doc in docs])
    # ... your prompt formatting ...
    # ... your LLM call ...
    return final_answer
```

### Option 2: Keep Your Existing Embeddings/Chunking

If you have custom text splitting or embeddings:

```python
def _split_text(self, text: str) -> list[str]:
    # Replace with your text splitting code
    # Should return list of strings
    pass

def _create_vectorstore(self, chunks: list[str]):
    # Replace with your vectorstore creation
    # Should return a vectorstore with .similarity_search() method
    pass
```

### Option 3: Use Different LLM

Replace Gemini with your LLM (OpenAI, etc.):

```python
def _initialize_models(self):
    # Instead of Gemini:
    from langchain_openai import ChatOpenAI
    
    self.llm = ChatOpenAI(
        model="gpt-4",
        api_key=os.getenv('OPENAI_API_KEY')
    )
```

Update `requirements.txt` accordingly:
```
langchain-openai>=0.0.1
```

### Example: Bringing Over Your Prompt Template

If you have a custom prompt from your existing code:

```python
# Your existing prompt
YOUR_PROMPT = """You are a helpful assistant...
Context: {context}
Question: {question}"""

# In rag_pipeline.py, replace prompt_template:
async def _generate_answer(self, question: str, docs: list) -> str:
    context = "\n".join([doc.page_content for doc in docs])
    formatted_prompt = YOUR_PROMPT.format(
        context=context,
        question=question
    )
    response = await loop.run_in_executor(
        None,
        self._call_llm,
        formatted_prompt
    )
    return response.content
```

## 🐛 Troubleshooting

### "Backend not reachable at http://localhost:8000"
- ✓ Backend server is running? (`python app.py`)
- ✓ Port 8000 is not in use? (`netstat -an | find ":8000"` on Windows)
- ✓ Try `curl http://localhost:8000/health` in terminal

### "Gemini API key not found"
- ✓ `.env` file exists in `backend/` folder?
- ✓ `GEMINI_API_KEY` is correctly set?
- ✓ No spaces around the `=` sign?
- ✓ Restart backend after changing `.env`

### "Transcript not available for this video"
- Some videos have captions disabled by creator
- The API will return a clear error message
- Try a different video (search for '[video title] subtitles')

### "No video ID detected" in extension
- ✓ You're on www.youtube.com (not youtube.com)?
- ✓ Page loaded completely?
- ✓ Refresh the page and try again
- ✓ Open DevTools (F12) and check console for errors

### Extension not loading in Chrome
- ✓ You're in Developer Mode?
- ✓ Selected correct folder (`/extension` not root)?
- ✓ manifest.json is there?
- ✓ No JavaScript syntax errors? (Check Chrome errors for details)

### First question takes 10+ seconds
- Normal! First request fetches & processes transcript
- Subsequent questions on same video are ~1-2 seconds
- This is expected with the free tier

## 🚀 Deploying to Production

### Backend Deployment (Heroku / AWS / GCP)

1. **Create `Procfile`:**
```
web: uvicorn app:app --host 0.0.0.0 --port $PORT
```

2. **Set environment variable:**
```bash
heroku config:set GEMINI_API_KEY=your_key_here
```

3. **Update extension sidepanel.js:**
```javascript
const BACKEND_URL = 'https://your-app-name.herokuapp.com';
```

### Extension Distribution

To publish on Chrome Web Store:
1. Create a Google account if needed
2. Go to [Chrome Web Store Developer Dashboard](https://chrome.google.com/webstore/devconsole)
3. Click "New Item"
4. Upload your extension ZIP file
5. Fill in description, screenshots, privacy policy
6. Pay $5 one-time developer fee
7. Submit for review (24-48 hours)

## 📝 Code Quality

The code follows these principles:
- **Clean separation** - Extension and backend are independent
- **Error handling** - All user-facing errors have helpful messages
- **Security** - API keys never in extension code
- **Performance** - Caching prevents redundant processing
- **Type hints** - Functions are documented with types
- **Async support** - Backend uses async for non-blocking operations

## 📚 Key Files Explained

### `service-worker.js`
- Handles side panel opening
- Stores video info in Chrome storage
- Background execution (no UI)

### `content.js`
- Runs on every YouTube page
- Detects current video ID
- Handles SPA navigation updates
- Communicates with service worker

### `sidepanel.js`
- Side panel UI logic
- Sends questions to backend
- Displays chat history
- Shows loading/error states

### `rag_pipeline.py`
- Core RAG logic
- Transcript fetching and processing
- Vector store management
- LLM integration

### `app.py`
- FastAPI server setup
- CORS configuration
- Endpoint definitions
- Error handling

## 🔒 Security Considerations

- ✓ API keys never sent to extension
- ✓ Extension doesn't process transcripts (backend does)
- ✓ All network requests go through CORS-protected backend
- ✓ No localStorage of sensitive data
- ✓ For production: enable HTTPS and restrict CORS origins

## 📞 Common Questions

**Q: Why cache videos in memory?**
A: Fast retrieval for repeated questions. For production, use Redis or database.

**Q: Can I use different embeddings models?**
A: Yes! Replace `GoogleGenerativeAIEmbeddings` with `OpenAIEmbeddings`, `HuggingFaceEmbeddings`, etc.

**Q: How do I update the extension after changes?**
A: Go to `chrome://extensions/`, find your extension, click the refresh icon.

**Q: Can I deploy the backend to Replit / Railway / Render?**
A: Yes! These platforms support FastAPI Python apps. Follow their deployment guides.

**Q: What if I want to add authentication?**
A: Add FastAPI security middleware or API key validation in `/ask` endpoint.

## 📄 License

This project is open source. Feel free to modify and use for your needs.

## 🎓 Learning Resources

- [Chrome Extension MV3 Docs](https://developer.chrome.com/docs/extensions/mv3/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [LangChain Docs](https://docs.langchain.com/)
- [Google Gemini API](https://ai.google.dev/)
- [FAISS Documentation](https://github.com/facebookresearch/faiss)

---

**Ready to go!** 🚀

Start the backend, load the extension, and start asking questions about YouTube videos!
