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
from contextlib import asynccontextmanager
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
USE_CLOUD_PIPELINE = os.getenv('USE_CLOUD_PIPELINE', 'false').lower() == 'true'
LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'ollama')
# Render assigns PORT - we MUST use it
PORT = int(os.environ.get('PORT', 8000))
HOST = '0.0.0.0'  # Must bind to 0.0.0.0 for Render

print(f"🚀 Config: HOST={HOST}, PORT={PORT}, LLM={LLM_PROVIDER}, CLOUD={USE_CLOUD_PIPELINE}")

async def init_pipeline_async():
    """Initialize RAG pipeline asynchronously"""
    global rag_pipeline
    
    print("🔄 Starting RAG pipeline initialization...")
    
    try:
        if USE_CLOUD_PIPELINE:
            from rag_pipeline_cloud import RAGPipeline
            print("☁️  Using cloud-compatible RAG pipeline")
        else:
            from rag_pipeline import RAGPipeline
            print("💻 Using local RAG pipeline")
        
        # Run pipeline init in thread pool to not block
        loop = asyncio.get_event_loop()
        rag_pipeline = await loop.run_in_executor(None, RAGPipeline)
        print("✅ RAG pipeline ready!")
        
    except Exception as e:
        print(f"❌ Pipeline init failed: {e}")
        import traceback
        traceback.print_exc()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context - server starts immediately"""
    # Create background task for pipeline init
    task = asyncio.create_task(init_pipeline_async())
    yield
    # Cancel task on shutdown if still running
    if not task.done():
        task.cancel()
    print("🛑 Shutting down...")

# Initialize FastAPI app with lifespan
app = FastAPI(
    title="YouTube RAG Chatbot Backend",
    description="Backend for YouTube Transcript RAG Chatbot",
    version="2.0.0",
    lifespan=lifespan
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
        raise HTTPException(
            status_code=503, 
            detail="Backend is still initializing. Please wait 30-60 seconds for models to load."
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
