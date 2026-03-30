# 🚀 Deployment Guide - YouTube RAG Chatbot

Host your YouTube RAG Chatbot for **FREE** on cloud platforms!

## 📋 Quick Deployment Options

| Platform | Free Tier | Ease of Use | Best For |
|----------|-----------|-------------|----------|
| **Render** | ✅ Generous | ⭐⭐⭐ Easy | Beginners |
| **Railway** | ✅ $5 credit/month | ⭐⭐⭐ Easy | Developers |
| **Fly.io** | ✅ $5 credit/month | ⭐⭐ Medium | Advanced |
| **HuggingFace Spaces** | ✅ Unlimited | ⭐⭐⭐ Easy | ML demos |

---

## 🎯 Recommended: Render (Easiest)

### Step 1: Sign Up
1. Go to [render.com](https://render.com)
2. Sign up with GitHub account
3. Connect your repository

### Step 2: Prepare Your Code
```bash
# Make sure your repo has these files:
# - youtube-rag-extension/backend/
# - render.yaml (already created)
# - Dockerfile (optional, for Docker deployment)
```

### Step 3: Create Web Service
1. Click "New +" → "Web Service"
2. Connect your GitHub repository
3. Configure:
   - **Name**: `youtube-rag-bot`
   - **Environment**: `Python 3`
   - **Build Command**: `cd backend && pip install -r requirements.txt`
   - **Start Command**: `cd backend && python app_cloud.py`
   - **Plan**: Free

### Step 4: Add Environment Variables
In Render Dashboard → Environment:
```
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-v1-your-key-here
OPENROUTER_MODEL=meta-llama/llama-3.2-3b-instruct:free
YOUTUBE_DATA_API_KEY=your-youtube-api-key
USE_CLOUD_PIPELINE=true
ALLOWED_ORIGINS=*
```

### Step 5: Deploy!
Click "Create Web Service" - Render will auto-deploy!

---

## 🚂 Alternative: Railway

### Step 1: Sign Up
1. Go to [railway.app](https://railway.app)
2. Sign up with GitHub

### Step 2: Deploy
1. Click "New Project" → "Deploy from GitHub repo"
2. Select your repository
3. Railway auto-detects `railway.json`
4. Add environment variables in Variables tab

---

## 🆓 Getting Free API Keys

### OpenRouter (Recommended - FREE)
1. Visit [openrouter.ai/keys](https://openrouter.ai/keys)
2. Create account (GitHub login)
3. Generate API key - **NO CREDIT CARD REQUIRED**
4. Use free models:
   - `meta-llama/llama-3.2-3b-instruct:free`
   - `google/gemma-2-9b-it:free`
   - `mistralai/mistral-7b-instruct:free`

### YouTube Data API (FREE)
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create project → Enable "YouTube Data API v3"
3. Create API key (no billing required for basic usage)
4. Quota: 10,000 requests/day

---

## 🔧 Updating Chrome Extension

After deploying backend, update your extension:

### Option 1: Update service-worker.js
```javascript
// Change from localhost to your deployed URL
const BACKEND_URL = 'https://your-app-name.onrender.com';
// const BACKEND_URL = 'http://localhost:8000'; // Local
```

### Option 2: Extension Settings (Recommended)
Add a settings page where users can enter their backend URL.

---

## 📊 Architecture Options

### Option A: Cloud Backend + Cloud LLM (Fully Cloud)
```
Chrome Extension → Render/Railway Backend → OpenRouter LLM API
```
✅ Works from anywhere
✅ No local setup needed
✅ Free tier available

### Option B: Cloud Backend + Local Ollama (Hybrid)
```
Chrome Extension → Render Backend → User's Local Ollama
```
⚠️ Requires user to run Ollama locally
⚠️ Complex networking (localhost from cloud)
❌ Not recommended

### Option C: Everything Local (Original)
```
Chrome Extension → localhost:8000 → Local Ollama
```
✅ Free forever
✅ Complete privacy
❌ Must run backend locally

---

## 🛠️ Local Development with Cloud Features

```bash
# Use cloud pipeline locally for testing
cd youtube-rag-extension/backend

# Create local env with cloud provider
cp .env.cloud.example .env

# Edit .env:
# LLM_PROVIDER=openrouter
# OPENROUTER_API_KEY=your_key
# USE_CLOUD_PIPELINE=true

# Run
python app_cloud.py
```

---

## 🔍 Troubleshooting

### "LLM not configured" error
- Check environment variables are set correctly
- Verify API keys are valid
- Check provider status page

### CORS errors in Chrome
- Add your extension ID to ALLOWED_ORIGINS
- Or use `*` for development (not production)

### Deployment fails
- Check `requirements.txt` has all dependencies
- Verify Python version compatibility
- Check Render/Railway logs

### Slow responses
- Use smaller LLM models on free tier
- Enable caching (videos are cached after first query)
- Consider upgrading paid plan for better performance

---

## 💡 Pro Tips

1. **Start with OpenRouter**: Easiest setup, truly free tier
2. **Use Caching**: First query for a video is slow, subsequent ones are fast
3. **Monitor Usage**: Free tiers have limits
4. **Keep Local Option**: Always maintain ability to run locally

---

## 🔗 Useful Links

- [Render Documentation](https://render.com/docs)
- [Railway Documentation](https://docs.railway.app)
- [OpenRouter Models](https://openrouter.ai/models)
- [OpenRouter Pricing](https://openrouter.ai/docs#free-models)

---

## ✅ Deployment Checklist

- [ ] Code pushed to GitHub
- [ ] Chose platform (Render recommended)
- [ ] Created account and connected repo
- [ ] Set environment variables
- [ ] Deployed successfully
- [ ] Tested `/health` endpoint
- [ ] Updated Chrome extension with deployed URL
- [ ] Tested end-to-end flow
- [ ] Checked CORS settings

---

**Ready to deploy? Start with [Render](https://render.com) - easiest path to free cloud hosting!**
