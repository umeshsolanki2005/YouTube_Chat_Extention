"""
YouTube RAG Chatbot - Python Backend
FastAPI server that handles:
- Transcript fetching and processing
- Embedding creation and vector store management
- RAG retrieval and Gemini-based answer generation
- Video-based caching to avoid reprocessing
"""

import sys

# Windows consoles often use cp1252; emoji in print() would crash startup.
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
from rag_pipeline import RAGPipeline

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="YouTube RAG Chatbot Backend",
    description="Backend for YouTube Transcript RAG Chatbot Chrome Extension",
    version="1.0.0"
)

# Add CORS middleware to allow Chrome extension requests
# In production, replace with specific origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for local development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize RAG pipeline (handles caching and retrieval)
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

@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint to verify backend is running.
    Chrome extension will call this to check connectivity.
    """
    return {
        "status": "healthy",
        "message": "YouTube RAG Backend is running"
    }

@app.post("/ask", response_model=AskResponse, tags=["RAG"])
async def ask_question(request: AskRequest) -> AskResponse:
    """
    Main endpoint: Answer a question about a YouTube video.
    
    Flow:
    1. Check if video is cached
    2. If not cached: fetch transcript → chunk → embed → create vector store
    3. Retrieve relevant chunks using similarity search
    4. Generate answer using Gemini with retrieved context
    5. Cache the vector store for future questions on this video
    
    Args:
        request: Contains video_id, video_url, and question
        
    Returns:
        AskResponse with the generated answer
        
    Raises:
        HTTPException: If transcript unavailable, API errors, or internal issues
    """
    try:
        # Validate inputs
        if not request.video_id or not request.question:
            raise HTTPException(
                status_code=400,
                detail="video_id and question are required"
            )
        
        # Get answer from RAG pipeline
        # Pipeline handles caching internally
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
        
        # Provide more user-friendly error messages
        if "Unable to retrieve transcript" in error_msg:
            detail = (
                f"Transcript Error: {error_msg}\n\n"
                f"This is a common issue with YouTube's transcript service. "
                f"The suggestions above usually help resolve it."
            )
        elif "HuggingFace API not configured" in error_msg:
            detail = (
                f"Configuration Error: {error_msg}\n\n"
                f"Please set up your HUGGINGFACEHUB_API_TOKEN in the .env file "
                f"in the backend directory."
            )
        elif "Error generating answer from HuggingFace" in error_msg:
            detail = (
                f"AI Generation Error: {error_msg}\n\n"
                f"Please check your HuggingFace API token and internet connection, "
                f"then try again."
            )
        else:
            detail = f"Error processing your question: {error_msg}"
        
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
        "llm_configured": rag_pipeline.is_huggingface_configured
    }

if __name__ == "__main__":
    import uvicorn
    
    # Check if HuggingFace API token is configured
    if not os.getenv('HUGGINGFACEHUB_API_TOKEN'):
        print("⚠️  WARNING: HUGGINGFACEHUB_API_TOKEN not set in .env file")
        print("   The backend will fail when trying to generate answers.")
        print("   Please add your HuggingFace API token to .env")
    
    print("🚀 Starting YouTube RAG Backend...")
    print("📍 Server: http://localhost:8000")
    print("📚 API Docs: http://localhost:8000/docs")
    print("✓ Ready to accept requests from Chrome extension")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
