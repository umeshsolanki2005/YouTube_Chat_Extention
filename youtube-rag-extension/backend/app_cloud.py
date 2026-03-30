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

# Load environment variables
load_dotenv()

# Check which RAG pipeline to use
USE_CLOUD_PIPELINE = os.getenv('USE_CLOUD_PIPELINE', 'false').lower() == 'true'

if USE_CLOUD_PIPELINE:
    from rag_pipeline_cloud import RAGPipeline
    print("☁️  Using cloud-compatible RAG pipeline")
else:
    from rag_pipeline import RAGPipeline
    print("💻 Using local RAG pipeline")

# Get configuration
LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'ollama')
PORT = int(os.getenv('PORT', 8000))
HOST = os.getenv('HOST', '0.0.0.0')

# Initialize FastAPI app
app = FastAPI(
    title="YouTube RAG Chatbot Backend",
    description="Backend for YouTube Transcript RAG Chatbot Chrome Extension",
    version="2.0.0"
)

# CORS - Allow Chrome extension and deployed frontend
ALLOWED_ORIGINS = os.getenv('ALLOWED_ORIGINS', '*').split(',')
if '*' in ALLOWED_ORIGINS:
    allow_origins = ["*"]
else:
    allow_origins = ALLOWED_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize RAG pipeline
rag_pipeline = RAGPipeline()

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

@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "message": "YouTube RAG Backend is running",
        "llm_provider": LLM_PROVIDER,
        "llm_configured": rag_pipeline.is_llm_configured
    }

@app.get("/config", response_model=ConfigResponse, tags=["Config"])
async def get_config():
    """Get current configuration (safe to expose)"""
    return ConfigResponse(
        llm_provider=LLM_PROVIDER,
        llm_configured=rag_pipeline.is_llm_configured,
        youtube_api_configured=rag_pipeline.is_youtube_api_configured,
        cached_videos=len(rag_pipeline.cache)
    )

@app.post("/ask", response_model=AskResponse, tags=["RAG"])
async def ask_question(request: AskRequest) -> AskResponse:
    """Main endpoint: Answer a question about a YouTube video"""
    try:
        # Validate inputs
        if not request.video_id or not request.question:
            raise HTTPException(
                status_code=400,
                detail="video_id and question are required"
            )
        
        # Get answer from RAG pipeline
        answer = await rag_pipeline.answer_question(
            video_id=request.video_id,
            video_url=request.video_url,
            question=request.question
        )
        
        return AskResponse(answer=answer)
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        print(f"Error processing question: {error_msg}")
        
        # User-friendly error messages
        if "Unable to retrieve transcript" in error_msg:
            detail = f"Transcript Error: {error_msg}"
        elif "LLM not configured" in error_msg:
            detail = (
                f"Configuration Error: {error_msg}\n\n"
                f"Please set LLM_PROVIDER in environment variables. "
                f"Options: ollama (local), openrouter (free cloud), huggingface"
            )
        elif "Error generating answer" in error_msg:
            detail = f"AI Generation Error: {error_msg}"
        else:
            detail = f"Error: {error_msg}"
        
        raise HTTPException(
            status_code=500,
            detail=detail
        )

@app.get("/status", tags=["Status"])
async def get_status():
    """Get current status including cache info"""
    return {
        "status": "running",
        "cached_videos": len(rag_pipeline.cache),
        "llm_provider": LLM_PROVIDER,
        "llm_configured": rag_pipeline.is_llm_configured,
        "youtube_api_configured": rag_pipeline.is_youtube_api_configured
    }

@app.post("/clear-cache", tags=["Admin"])
async def clear_cache(video_id: str = None):
    """Clear cache (for maintenance)"""
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
