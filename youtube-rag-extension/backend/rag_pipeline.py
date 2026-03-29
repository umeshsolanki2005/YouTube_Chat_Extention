"""
RAG Pipeline for YouTube Transcript Processing
Handles:
- Transcript fetching from YouTube
- Text chunking and splitting
- Embedding generation
- Vector store creation (FAISS)
- Semantic similarity retrieval
- Answer generation with Gemini LLM
- Video-based caching for efficiency
"""

import os
from typing import Optional
from youtube_transcript_api import YouTubeTranscriptApi
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
import asyncio

class RAGPipeline:
    """
    Main RAG Pipeline for YouTube Video Question Answering
    
    Architecture:
    - Single-threaded cache dict (video_id -> vectorstore)
    - Lazy loading: processes only when needed
    - Configurable chunk size and retrieval count
    """
    
    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        retrieval_k: int = 3
    ):
        """
        Initialize RAG Pipeline.
        
        Args:
            chunk_size: Characters per chunk for text splitting
            chunk_overlap: Overlap between chunks for context continuity
            retrieval_k: Number of chunks to retrieve for answer generation
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.retrieval_k = retrieval_k
        
        # Cache: {video_id -> {"vectorstore": FAISS, "transcript": str}}
        self.cache = {}
        
        # Initialize LLM and embeddings
        self.embeddings = None
        self.llm = None
        self.is_gemini_configured = False
        self._initialize_models()
    
    def _initialize_models(self):
        """Initialize Gemini API models with error handling"""
        try:
            api_key = os.getenv('GEMINI_API_KEY')
            if not api_key:
                print("⚠️  Gemini API key not found in environment")
                return
            
            # Initialize embeddings
            self.embeddings = GooglePalmEmbeddings(
                google_api_key=api_key
            )
            
            # Initialize LLM
            self.llm = GooglePalm(
                temperature=0.3,  # Lower temp for more focused answers
                google_api_key=api_key
            )
            
            self.is_gemini_configured = True
            print("✓ Gemini models initialized successfully")
            
        except Exception as e:
            print(f"❌ Error initializing Gemini: {str(e)}")
            self.is_gemini_configured = False
    
    async def answer_question(
        self,
        video_id: str,
        video_url: str,
        question: str
    ) -> str:
        """
        Answer a question about a YouTube video transcript.
        
        Process:
        1. Check cache for existing vectorstore
        2. If not cached: fetch transcript → chunk → embed → create vectorstore
        3. Retrieve relevant chunks using similarity
        4. Generate answer using Gemini with retrieved context
        
        Args:
            video_id: YouTube video ID
            video_url: Full YouTube video URL
            question: User's question about the video
            
        Returns:
            Generated answer string
            
        Raises:
            ValueError: If transcript unavailable or models not initialized
        """
        if not self.is_gemini_configured:
            raise ValueError(
                "Gemini API not configured. Please set GEMINI_API_KEY in .env"
            )
        
        # Check cache first
        if video_id not in self.cache:
            print(f"📥 Processing video {video_id}...")
            await self._process_video(video_id, video_url)
        else:
            print(f"✓ Using cached data for video {video_id}")
        
        # Retrieve relevant chunks
        vectorstore = self.cache[video_id]["vectorstore"]
        docs = vectorstore.similarity_search(question, k=self.retrieval_k)
        
        if not docs:
            return "Sorry, I couldn't find relevant information about your question in the video transcript."
        
        # Generate answer using LLM
        answer = await self._generate_answer(question, docs)
        return answer
    
    async def _process_video(self, video_id: str, video_url: str):
        """
        Process a video: fetch transcript, chunk, embed, create vectorstore.
        Store in cache for future requests.
        
        Args:
            video_id: YouTube video ID
            video_url: Full YouTube URL
            
        Raises:
            ValueError: If transcript cannot be fetched
        """
        # Run blocking operations in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        
        # Fetch transcript
        print(f"  ⬇️  Fetching transcript...")
        transcript_text = await loop.run_in_executor(
            None,
            self._fetch_transcript,
            video_id
        )
        
        # Split into chunks
        print(f"  ✂️  Splitting into chunks...")
        chunks = await loop.run_in_executor(
            None,
            self._split_text,
            transcript_text
        )
        
        if not chunks:
            raise ValueError(f"No content found in transcript")
        
        # Create vectorstore
        print(f"  🧠 Creating embeddings and vector store...")
        vectorstore = await loop.run_in_executor(
            None,
            self._create_vectorstore,
            chunks
        )
        
        # Cache the vectorstore
        self.cache[video_id] = {
            "vectorstore": vectorstore,
            "transcript": transcript_text,
            "chunks": chunks
        }
        
        print(f"✓ Video {video_id} processed: {len(chunks)} chunks cached")
    
    def _fetch_transcript(self, video_id: str) -> str:
        """
        Fetch YouTube transcript for given video ID.
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            Full transcript text
            
        Raises:
            ValueError: If transcript unavailable
        """
        try:
            # Fetch transcript for the video
            transcript = YouTubeTranscriptApi.get_transcript(video_id)
            
            # Combine all transcript entries into single text
            transcript_text = " ".join([entry['text'] for entry in transcript])
            
            if not transcript_text.strip():
                raise ValueError("Transcript is empty")
            
            return transcript_text
            
        except Exception as e:
            error_msg = str(e).lower()
            
            if 'disabled' in error_msg or 'not available' in error_msg:
                raise ValueError(
                    f"Transcript not available for this video. "
                    f"The video creator may have disabled transcripts."
                )
            elif 'invalid' in error_msg or 'not found' in error_msg:
                raise ValueError(
                    f"Invalid video ID or video not found: {video_id}"
                )
            else:
                raise ValueError(
                    f"Failed to fetch transcript: {str(e)}"
                )
    
    def _split_text(self, text: str) -> list[str]:
        """
        Split transcript into chunks using recursive character splitter.
        This preserves semantic units (sentences/paragraphs) better than simple splitting.
        
        Args:
            text: Full transcript text
            
        Returns:
            List of text chunks
        """
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        chunks = splitter.split_text(text)
        return chunks
    
    def _create_vectorstore(self, chunks: list[str]):
        """
        Create FAISS vectorstore from chunks using Gemini embeddings.
        
        Args:
            chunks: List of text chunks
            
        Returns:
            FAISS vectorstore for similarity search
        """
        vectorstore = FAISS.from_texts(
            texts=chunks,
            embedding=self.embeddings,
            metadatas=[{"chunk_index": i} for i in range(len(chunks))]
        )
        return vectorstore
    
    async def _generate_answer(self, question: str, docs: list) -> str:
        """
        Generate answer using Gemini LLM with retrieved context.
        
        Args:
            question: User's question
            docs: Retrieved document chunks from vector store
            
        Returns:
            Generated answer
        """
        # Create custom prompt for RAG
        prompt_template = """Based only on the provided transcript context, answer the following question. 
        If the answer cannot be found in the context, clearly state that the information is not available in the transcript.
        Keep your answer concise and directly relevant to the question.

Context from transcript:
{context}

Question: {question}

Answer:"""
        
        prompt = PromptTemplate(
            template=prompt_template,
            input_variables=["context", "question"]
        )
        
        # Build context from retrieved docs
        context = "\n---\n".join([doc.page_content for doc in docs])
        
        # Run LLM in thread pool (it's a blocking operation)
        loop = asyncio.get_event_loop()
        
        try:
            # Prepare the prompt with context and question
            formatted_prompt = prompt_template.format(
                context=context,
                question=question
            )
            
            # Call LLM synchronously in executor to avoid blocking
            response = await loop.run_in_executor(
                None,
                self._call_llm,
                formatted_prompt
            )
            
            return response
            
        except Exception as e:
            print(f"❌ Error generating answer: {str(e)}")
            raise ValueError(
                f"Error generating answer from Gemini: {str(e)}"
            )
    
    def _call_llm(self, prompt: str) -> str:
        """
        Call Gemini LLM synchronously.
        
        Args:
            prompt: Formatted prompt with context
            
        Returns:
            LLM response
        """
        response = self.llm.invoke(prompt)
        return response.content
    
    def clear_cache(self, video_id: Optional[str] = None):
        """
        Clear cache for specific video or all videos.
        
        Args:
            video_id: Specific video to clear, or None to clear all
        """
        if video_id:
            if video_id in self.cache:
                del self.cache[video_id]
                print(f"✓ Cleared cache for video {video_id}")
        else:
            self.cache.clear()
            print("✓ Cleared all cache")
    
    def get_cache_info(self) -> dict:
        """Get information about current cache"""
        return {
            "cached_videos": len(self.cache),
            "videos": list(self.cache.keys())
        }
