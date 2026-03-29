# Quick Setup Guide - YouTube RAG Chatbot Extension

Complete step-by-step instructions to get the extension running locally.

## 📋 Pre-Check

- [ ] Python 3.9+ installed (`python --version`)
- [ ] Chrome browser installed
- [ ] Have a Google Gemini API key (free tier available)

## 🔑 Step 1: Get Gemini API Key (5 minutes)

1. Go to [Google AI Studio](https://ai.google.dev/)
2. Click **"Get API Key"**
3. Click **"Create API key in new project"**
4. Copy your API key (save it somewhere safe)

## 📦 Step 2: Setup Python Backend (10 minutes)

### 2a. Open Terminal and Navigate to Backend

**Windows PowerShell:**
```powershell
cd d:\GEN_AI\youtube-rag-extension\backend
```

**Mac/Linux Terminal:**
```bash
cd ~/path/to/youtube-rag-extension/backend
```

### 2b. Create Virtual Environment

**Windows:**
```powershell
python -m venv venv
venv\Scripts\activate
```

**Mac/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

You should see `(venv)` at start of terminal line.

### 2c. Install Dependencies

```bash
pip install -r requirements.txt
```

This will take 2-3 minutes. Wait for it to complete.

### 2d. Create .env File

**Windows PowerShell:**
```powershell
Copy-Item .env.example .env
```

**Mac/Linux:**
```bash
cp .env.example .env
```

### 2e. Configure API Key

Open `.env` file with any text editor and replace:

```
GEMINI_API_KEY=your_gemini_api_key_here_replace_this
```

With your actual API key from Step 1:

```
GEMINI_API_KEY=AIzaSy_________________your_key_here
```

**Save the file.**

### 2f. Start Backend Server

```bash
python app.py
```

You should see:
```
🚀 Starting YouTube RAG Backend...
📍 Server: http://localhost:8000
📚 API Docs: http://localhost:8000/docs
✓ Ready to accept requests from Chrome extension
```

**✓ Leave this terminal running** (keep it open!)

## 🧩 Step 3: Load Chrome Extension (5 minutes)

**In a NEW terminal/Chrome window** (keep Python running):

1. **Open Chrome**
2. **Go to:** `chrome://extensions/`
3. **Enable "Developer mode"** (toggle in top-right corner)
4. **Click "Load unpacked"**
5. **Navigate to:** `youtube-rag-extension/extension` folder
6. **Select the folder** and click "Open"

You should see the extension appear in your list with a blue icon.

## ✅ Step 4: Test It Out (5 minutes)

1. **Go to a YouTube video:**
   - Example: https://www.youtube.com/watch?v=dQw4w9WgXcQ
   
2. **Click extension icon** in Chrome toolbar (top-right)
   - If not visible, click the puzzle icon → pin the extension

3. **The side panel should open** on the right with:
   - "Ready" status (green)
   - Current video ID shown
   - Input box for questions

4. **Type a question** like:
   - "What is this video about?"
   - "Who is speaking?"
   - "What are the main topics discussed?"

5. **Click "Ask"** or press **Enter**
   - First question takes 5-10 seconds (processing & caching transcript)
   - Subsequent questions take 1-2 seconds
   - Answer appears in chat below

## 🎉 Success!

If you see:
- ✓ "Ready" status in green
- ✓ Backend connected message
- ✓ Chat history with Q&A
- ✓ Answers appearing

**You're all set!**

## 🐛 Quick Troubleshooting

| Problem | Solution |
|---------|----------|
| "Backend not reachable" | Make sure `python app.py` is still running in terminal |
| "No video detected" | Make sure you're on youtube.com and page loaded fully |
| "Gemini API error" | Check that `.env` file has correct API key (no spaces) |
| Extension won't load | Make sure Developer Mode is ON and you selected `/extension` folder |
| Port 8000 already in use | Close other apps using port 8000, or restart computer |

## 📝 How to Use More Features

**View API docs:** http://localhost:8000/docs

**Check backend status:** http://localhost:8000/status

**Clear cache** (restart): Just restart the Python backend

## 🔄 Stopping/Restarting

**To stop backend:**
- Press `Ctrl+C` in the terminal running `python app.py`

**To restart:**
- Run `python app.py` again

**To reload extension:**
- Go to `chrome://extensions/`
- Find your extension
- Click the refresh icon 🔄

## 🚀 Next Steps

- **Integrate your existing RAG code:** See README.md section "How to Integrate Your Existing RAG Code"
- **Deploy backend:** See README.md section "Deploying to Production"
- **Publish extension:** See README.md for Chrome Web Store instructions

---

**Need help?** Check README.md for detailed documentation and FAQ.
