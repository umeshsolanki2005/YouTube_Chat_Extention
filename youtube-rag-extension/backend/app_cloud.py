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

# Load environment variables
load_dotenv()

# Global variables - initialized lazily
rag_pipeline = None
pipeline_loading = False

USE_CLOUD_PIPELINE = os.getenv('USE_CLOUD_PIPELINE', 'false').lower() == 'true'
LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'ollama')
PORT = int(os.getenv('PORT', 8000))
HOST = os.getenv('HOST', '0.0.0.0')

def init_pipeline():
    """Initialize RAG pipeline in background"""
    global rag_pipeline, pipeline_loading
    if pipeline_loading or rag_pipeline is not None:
        return
    
    pipeline_loading = True
    print("🔄 Initializing RAG pipeline...")
    
    try:
        if USE_CLOUD_PIPELINE:
            from rag_pipeline_cloud import RAGPipeline
            print("☁️  Using cloud-compatible RAG pipeline")
        else:
            from rag_pipeline import RAGPipeline
            print("💻 Using local RAG pipeline")
        
        rag_pipeline = RAGPipeline()
        print("✅ RAG pipeline ready")
    except Exception as e:
        print(f"⚠️  Pipeline init error: {e}")
    finally:
        pipeline_loading = False

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Server starts first, then models load"""
    import asyncio
    # Start pipeline initialization in background
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, init_pipeline)
    yield
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
    """Health check - responds immediately even during init"""
    if rag_pipeline is None:
        return {"status": "starting", "ready": False}
    return {"status": "healthy", "ready": True, "llm_configured": getattr(rag_pipeline, 'is_llm_configured', False)}

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
        raise HTTPException(status_code=503, detail="Backend initializing, please retry in 30 seconds")
    
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
