"""
YouTube RAG Chatbot - Cloud-Compatible Python Backend
FastAPI server that supports both local and cloud LLM providers
"""

import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (OSError, ValueError, AttributeError):
        pass

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from dotenv import load_dotenv
import asyncio

# Load environment variables
load_dotenv()

# Debug: Print environment variables
print("🔧 Environment Variables:")
print(f"   PORT: {os.getenv('PORT', 'NOT SET')}")
print(f"   LLM_PROVIDER: {os.getenv('LLM_PROVIDER', 'NOT SET')}")
print(f"   USE_CLOUD_PIPELINE: {os.getenv('USE_CLOUD_PIPELINE', 'NOT SET')}")
print(f"   OPENROUTER_API_KEY: {'SET' if os.getenv('OPENROUTER_API_KEY') else 'NOT SET'}")

# Global variables - MUST use Render's PORT env var
rag_pipeline = None
# NOTE: Don't create asyncio primitives at import-time.
# Render starts Python before the event loop exists; creating `asyncio.Lock()`
# can crash the process and prevent binding to `PORT`.
pipeline_init_lock = None

# Fallback to render.yaml values if env vars not set
USE_CLOUD_PIPELINE = os.getenv('USE_CLOUD_PIPELINE', 'true').lower() == 'true'
LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'openrouter')

# CRITICAL: Render assigns PORT via environment variable
# MUST use os.environ.get() not os.getenv() for PORT
PORT = int(os.environ.get('PORT', 10000))
HOST = '0.0.0.0'  # Must bind to 0.0.0.0 for Render

print(f"🚀 Config: HOST={HOST}, PORT={PORT}, LLM={LLM_PROVIDER}, CLOUD={USE_CLOUD_PIPELINE}")

async def init_pipeline_async():
    """Initialize RAG pipeline asynchronously (used for lazy init)."""
    global rag_pipeline

    print("🔄 Starting RAG pipeline initialization...")

    try:
        if USE_CLOUD_PIPELINE:
            from rag_pipeline_cloud import RAGPipeline
            print("☁️  Using cloud-compatible RAG pipeline")
        else:
            from rag_pipeline import RAGPipeline
            print("💻 Using local RAG pipeline")

        loop = asyncio.get_event_loop()
        rag_pipeline = await loop.run_in_executor(None, RAGPipeline)
        print("✅ RAG pipeline ready!")
    except Exception as e:
        print(f"❌ Pipeline init failed: {e}")
        import traceback
        traceback.print_exc()

async def ensure_pipeline_initialized():
    """Lazy init so the server binds ports immediately on Render."""
    global rag_pipeline
    global pipeline_init_lock
    if rag_pipeline is not None:
        return
    if pipeline_init_lock is None:
        pipeline_init_lock = asyncio.Lock()

    async with pipeline_init_lock:
        if rag_pipeline is not None:
            return
        await init_pipeline_async()

app = FastAPI(
    title="YouTube RAG Chatbot Backend",
    description="Backend for YouTube Transcript RAG Chatbot",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response models
class AskRequest(BaseModel):
    """Request body for /ask endpoint"""
    video_id: str
    video_url: str
    question: str

class AskResponse(BaseModel):
    """Response body for /ask endpoint"""
    answer: str

class ConfigResponse(BaseModel):
    """Configuration response"""
    llm_provider: str
    llm_configured: bool
    youtube_api_configured: bool
    cached_videos: int

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint - API info"""
    return {
        "name": "YouTube RAG Chatbot Backend",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/health",
        "config": "/config"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    if rag_pipeline is None:
        return {"status": "starting", "ready": False, "message": "Backend initializing"}
    return {
        "status": "healthy", 
        "ready": True, 
        "llm_configured": getattr(rag_pipeline, 'is_llm_configured', False)
    }

@app.get("/config")
async def get_config():
    """Get current configuration"""
    return {
        "llm_provider": LLM_PROVIDER,
        "llm_configured": getattr(rag_pipeline, 'is_llm_configured', False) if rag_pipeline else False,
        "youtube_api_configured": getattr(rag_pipeline, 'is_youtube_api_configured', False) if rag_pipeline else False,
        "cached_videos": len(rag_pipeline.cache) if rag_pipeline else 0
    }

@app.post("/ask", response_model=AskResponse)
async def ask_question(request: AskRequest):
    """Answer question about video"""
    global rag_pipeline

    if rag_pipeline is None:
        await ensure_pipeline_initialized()
        if rag_pipeline is None:
            raise HTTPException(
                status_code=503,
                detail="Backend initialization failed. Check server logs."
            )
    
    if not request.video_id or not request.question:
        raise HTTPException(status_code=400, detail="video_id and question are required")
    
    try:
        answer = await rag_pipeline.answer_question(
            video_id=request.video_id,
            video_url=request.video_url,
            question=request.question
        )
        return AskResponse(answer=answer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status")
async def get_status():
    """Get current status"""
    return {
        "status": "running" if rag_pipeline else "initializing",
        "cached_videos": len(rag_pipeline.cache) if rag_pipeline else 0,
        "llm_provider": LLM_PROVIDER,
        "llm_configured": getattr(rag_pipeline, 'is_llm_configured', False) if rag_pipeline else False
    }

@app.post("/clear-cache")
async def clear_cache(video_id: str = None):
    """Clear cache"""
    if rag_pipeline:
        rag_pipeline.clear_cache(video_id)
    return {"message": "Cache cleared", "video_id": video_id}

if __name__ == "__main__":
    import uvicorn
    
    # Print configuration
    print("🚀 Starting YouTube RAG Backend...")
    print(f"📍 Server: http://{HOST}:{PORT}")
    print(f"📚 API Docs: http://{HOST}:{PORT}/docs")
    print(f"🔧 LLM Provider: {LLM_PROVIDER}")
    print(f"☁️  Cloud Mode: {USE_CLOUD_PIPELINE}")
    print(f"✓ Ready to accept requests")
    
    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        log_level="info"
    )
