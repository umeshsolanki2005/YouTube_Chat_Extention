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

import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (OSError, ValueError, AttributeError):
        pass

import os
from typing import Optional
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound, VideoUnavailable, RequestBlocked, IpBlocked
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_ollama import OllamaLLM
from langchain_core.prompts import PromptTemplate
import asyncio
import requests
import re
import time
import random
import json
from urllib.parse import urlparse, parse_qs
import html
from bs4 import BeautifulSoup
from googleapiclient.discovery import build

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
        self.youtube_api = None
        self.is_huggingface_configured = False
        self.is_youtube_api_configured = False
        self._initialize_models()
    
    def _initialize_models(self):
        """Initialize Ollama local LLM and embeddings"""
        try:
            # Initialize embeddings (using local model)
            self.embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2",
                model_kwargs={'device': 'cpu'},
                encode_kwargs={'normalize_embeddings': True}
            )
            print("✓ Embeddings model loaded")
            
            # Initialize Ollama LLM
            try:
                self.llm = OllamaLLM(
                    model="llama3.2",
                    temperature=0.7,
                    num_ctx=4096
                )
                # Test the LLM
                test_response = self.llm.invoke("Hello")
                self.is_huggingface_configured = True
                print("✓ Ollama LLM (llama3.2) initialized successfully")
            except Exception as e:
                print(f"⚠️  Ollama LLM failed: {e}")
                print("   Make sure Ollama is running: ollama serve")
                self.llm = self._create_mock_llm()
                self.is_huggingface_configured = True
                
        except Exception as e:
            print(f"❌ Error initializing models: {str(e)}")
            self.is_huggingface_configured = False
        
        # Initialize YouTube Data API
        try:
            youtube_api_key = os.getenv('YOUTUBE_DATA_API_KEY')
            if not youtube_api_key:
                print("⚠️  YouTube Data API key not found in environment")
                return
            
            self.youtube_api = build('youtube', 'v3', developerKey=youtube_api_key)
            self.is_youtube_api_configured = True
            print("✓ YouTube Data API initialized successfully")
        except Exception as e:
            print(f"❌ Error initializing YouTube Data API: {str(e)}")
            self.is_youtube_api_configured = False
    
    def _create_mock_llm(self):
        """Create a mock LLM for testing when API fails"""
        class MockLLM:
            def invoke(self, prompt):
                # Extract question from the prompt
                lines = prompt.split('\n')
                question = ""
                for line in lines:
                    if line.startswith("Question:"):
                        question = line.replace("Question:", "").strip()
                        break
                
                # Return a mock response based on the context provided
                return f"Based on the video transcript provided, I can see this video contains a transcript with the content you're asking about. To answer your question '{question}', the video appears to discuss the topic mentioned in the available context. For more detailed answers, please ensure the HuggingFace API is properly configured or use a local LLM like Ollama."
        
        return MockLLM()
    
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
        if not self.is_huggingface_configured:
            raise ValueError(
                "HuggingFace API not configured. Please set HUGGINGFACEHUB_API_TOKEN in .env"
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
        Fetch YouTube transcript for given video ID with multiple fallback strategies.
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            Full transcript text
            
        Raises:
            ValueError: If transcript unavailable after all fallback attempts
        """
        # Strategy 0: Try YouTube Data API first (most reliable)
        if self.is_youtube_api_configured:
            try:
                return self._fetch_transcript_youtube_data_api(video_id)
            except Exception as e:
                print(f"  ⚠️  YouTube Data API failed: {str(e)}")
        
        # Strategy 1: Try youtube-transcript-api with different language preferences
        try:
            return self._fetch_transcript_youtube_api(video_id)
        except Exception as e:
            print(f"  ⚠️  YouTube API failed: {str(e)}")
        
        # Strategy 2: Try with auto-generated captions
        try:
            return self._fetch_transcript_auto_generated(video_id)
        except Exception as e:
            print(f"  ⚠️  Auto-generated captions failed: {str(e)}")
        
        # Strategy 3: Web scraping method
        try:
            return self._fetch_transcript_web_scraping(video_id)
        except Exception as e:
            print(f"  ⚠️  Web scraping failed: {str(e)}")
        
        # Strategy 4: YouTube internal API method
        try:
            return self._fetch_transcript_internal_api(video_id)
        except Exception as e:
            print(f"  ⚠️  Internal API failed: {str(e)}")
        
        # Strategy 5: Try with different proxy/user agent approach
        try:
            return self._fetch_transcript_with_retry(video_id)
        except Exception as e:
            print(f"  ⚠️  Retry approach failed: {str(e)}")
        
        # All strategies failed
        raise ValueError(
            f"Unable to retrieve transcript for video {video_id}. This may be due to:\n"
            f"• YouTube blocking requests from your IP address\n"
            f"• Video creator has disabled transcripts\n"
            f"• No captions available for this video\n"
            f"• Network connectivity issues\n\n"
            f"Suggestions:\n"
            f"• Try again in a few minutes\n"
            f"• Use a different network connection\n"
            f"• Try a different video that has captions enabled"
        )
    
    def _fetch_transcript_youtube_api(self, video_id: str) -> str:
        """Primary method using youtube-transcript-api"""
        ytt = YouTubeTranscriptApi()
        
        # Try multiple language combinations
        language_combinations = [
            ("en", "en-US", "en-GB"),  # English variants
            ("en",),                     # English only
            ("en-US",),                  # US English
            ("hi", "en"),                # Hindi + English
            ("es", "en"),                # Spanish + English
            ("fr", "en"),                # French + English
            ("de", "en"),                # German + English
            ("ja", "en"),                # Japanese + English
            ("pt", "en"),                # Portuguese + English
            ("it", "en"),                # Italian + English
        ]
        
        for languages in language_combinations:
            try:
                fetched = ytt.fetch(video_id, languages=languages)
                transcript_text = " ".join(s.text for s in fetched)
                
                if transcript_text.strip():
                    print(f"  ✓ Transcript fetched using languages: {languages}")
                    return transcript_text
                    
            except (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable):
                continue
            except (RequestBlocked, IpBlocked) as e:
                raise e  # Re-raise IP blocking errors
            except Exception as e:
                continue
        
        raise NoTranscriptFound(f"No transcript found for video {video_id}")
    
    def _fetch_transcript_auto_generated(self, video_id: str) -> str:
        """Try to fetch auto-generated captions"""
        ytt = YouTubeTranscriptApi()
        
        try:
            # Get list of available transcripts
            transcript_list = ytt.list_transcripts(video_id)
            
            # Try to find auto-generated English transcript
            try:
                transcript = transcript_list.find_manually_created_transcript(['en'])
                fetched = transcript.fetch()
                transcript_text = " ".join(s.text for s in fetched)
                if transcript_text.strip():
                    print(f"  ✓ Manual transcript fetched")
                    return transcript_text
            except:
                pass
            
            # Try auto-generated transcripts
            try:
                transcript = transcript_list.find_generated_transcript(['en'])
                fetched = transcript.fetch()
                transcript_text = " ".join(s.text for s in fetched)
                if transcript_text.strip():
                    print(f"  ✓ Auto-generated transcript fetched")
                    return transcript_text
            except:
                pass
            
            # Try any available transcript
            try:
                transcript = transcript_list.find_transcript(['en'])
                fetched = transcript.fetch()
                transcript_text = " ".join(s.text for s in fetched)
                if transcript_text.strip():
                    print(f"  ✓ Any available transcript fetched")
                    return transcript_text
            except:
                pass
                
        except Exception as e:
            raise Exception(f"Auto-generated transcript fetch failed: {str(e)}")
        
        raise NoTranscriptFound(f"No auto-generated transcript found for video {video_id}")
    
    def _fetch_transcript_with_retry(self, video_id: str) -> str:
        """Retry with exponential backoff and random delays"""
        max_retries = 3
        base_delay = 1
        
        for attempt in range(max_retries):
            try:
                # Add random delay to avoid rate limiting
                if attempt > 0:
                    delay = base_delay * (2 ** attempt) + random.uniform(0.5, 2.0)
                    print(f"  ⏳ Retry attempt {attempt + 1}/{max_retries} after {delay:.1f}s delay...")
                    time.sleep(delay)
                
                # Try the primary method again
                return self._fetch_transcript_youtube_api(video_id)
                
            except (RequestBlocked, IpBlocked) as e:
                if attempt == max_retries - 1:
                    raise e
                print(f"  ⚠️  Rate blocked, waiting before retry...")
                
            except Exception as e:
                if attempt == max_retries - 1:
                    raise e
                print(f"  ⚠️  Attempt {attempt + 1} failed, retrying...")
        
        raise Exception(f"All {max_retries} retry attempts failed")
    
    def _fetch_transcript_youtube_data_api(self, video_id: str) -> str:
        """Fetch transcript using YouTube Data API - most reliable method that bypasses IP blocking"""
        try:
            # First, get video details to check if captions are available
            video_response = self.youtube_api.videos().list(
                part='snippet,contentDetails',
                id=video_id
            ).execute()
            
            if not video_response['items']:
                raise ValueError(f"Video {video_id} not found")
            
            video = video_response['items'][0]
            print(f"  📹 Found video: {video['snippet']['title']}")
            
            # Get caption tracks for this video
            captions_response = self.youtube_api.captions().list(
                part='snippet',
                videoId=video_id
            ).execute()
            
            if not captions_response['items']:
                raise ValueError("No captions available for this video")
            
            # Find English caption track
            english_caption = None
            for caption in captions_response['items']:
                snippet = caption['snippet']
                if 'en' in snippet.get('language', '').lower():
                    english_caption = caption
                    break
            
            if not english_caption:
                # Try any available caption if English not found
                english_caption = captions_response['items'][0]
                print(f"  ⚠️  Using {english_caption['snippet']['language']} captions (English not available)")
            
            # Download the caption content
            caption_download_url = english_caption['snippet']['downloadUrl']
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(caption_download_url, headers=headers)
            response.raise_for_status()
            
            # Parse XML caption content
            soup = BeautifulSoup(response.content, 'xml')
            text_elements = soup.find_all('text')
            
            if not text_elements:
                raise ValueError("No text content found in captions")
            
            # Extract and clean transcript text
            transcript_parts = []
            for element in text_elements:
                if element.text:
                    # Clean up HTML entities and formatting
                    text = html.unescape(element.text)
                    text = re.sub(r'\s+', ' ', text).strip()
                    if text and text not in ['[Music]', '[Applause]']:  # Filter out common non-speech
                        transcript_parts.append(text)
            
            if not transcript_parts:
                raise ValueError("No valid transcript content found")
            
            transcript_text = ' '.join(transcript_parts)
            print(f"  ✓ YouTube Data API transcript fetched ({len(transcript_parts)} segments)")
            
            return transcript_text
            
        except Exception as e:
            raise Exception(f"YouTube Data API method failed: {str(e)}")
    
    def _fetch_transcript_web_scraping(self, video_id: str) -> str:
        """Fetch transcript by scraping YouTube video page"""
        try:
            # Get video page
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(video_url, headers=headers)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for transcript data in script tags
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string and 'captionTracks' in script.string:
                    # Extract JSON data
                    try:
                        # Find the JSON part containing captionTracks
                        json_text = script.string
                        start = json_text.find('"captionTracks":')
                        if start == -1:
                            continue
                            
                        # Find the end of this object
                        brace_count = 0
                        end = start
                        for i, char in enumerate(json_text[start:], start):
                            if char == '{':
                                brace_count += 1
                            elif char == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    end = i + 1
                                    break
                        
                        if end <= start:
                            continue
                            
                        caption_json = json_text[start:end]
                        caption_data = json.loads('{' + caption_json + '}')
                        
                        # Find English caption track
                        captions = caption_data.get('captionTracks', [])
                        for caption in captions:
                            if 'en' in caption.get('languageCode', '').lower():
                                caption_url = caption.get('baseUrl')
                                if caption_url:
                                    # Fetch caption content
                                    caption_response = requests.get(caption_url, headers=headers)
                                    caption_response.raise_for_status()
                                    
                                    # Parse XML caption content
                                    caption_soup = BeautifulSoup(caption_response.content, 'xml')
                                    text_elements = caption_soup.find_all('text')
                                    
                                    transcript_text = []
                                    for element in text_elements:
                                        if element.text:
                                            # Clean up HTML entities and formatting
                                            text = html.unescape(element.text)
                                            text = re.sub(r'\s+', ' ', text).strip()
                                            if text:
                                                transcript_text.append(text)
                                    
                                    if transcript_text:
                                        full_transcript = ' '.join(transcript_text)
                                        print(f"  ✓ Web scraping transcript fetched")
                                        return full_transcript
                                        
                    except json.JSONDecodeError:
                        continue
                    except Exception as e:
                        continue
            
            raise Exception("No caption tracks found in video page")
            
        except Exception as e:
            raise Exception(f"Web scraping failed: {str(e)}")
    
    def _fetch_transcript_internal_api(self, video_id: str) -> str:
        """Fetch transcript using YouTube's internal API"""
        try:
            # Get video page to extract internal data
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(video_url, headers=headers)
            response.raise_for_status()
            
            # Extract ytInitialData from the page
            match = re.search(r'var ytInitialData = ({.+?});', response.text)
            if not match:
                match = re.search(r'window["ytInitialData"] = ({.+?});', response.text)
            
            if not match:
                raise Exception("Could not find ytInitialData")
            
            initial_data = json.loads(match.group(1))
            
            # Navigate through the data structure to find captions
            try:
                # Path to captions in the data structure
                captions_path = initial_data['contents']['twoColumnWatchNextResults']['results']['results']['contents'][0]['videoPrimaryInfoRenderer']['captionTracks']
                
                for caption in captions_path:
                    if 'en' in caption.get('languageCode', '').lower():
                        caption_url = caption.get('baseUrl')
                        if caption_url:
                            # Fetch caption content
                            caption_response = requests.get(caption_url, headers=headers)
                            caption_response.raise_for_status()
                            
                            # Parse XML caption content
                            caption_soup = BeautifulSoup(caption_response.content, 'xml')
                            text_elements = caption_soup.find_all('text')
                            
                            transcript_text = []
                            for element in text_elements:
                                if element.text:
                                    # Clean up HTML entities and formatting
                                    text = html.unescape(element.text)
                                    text = re.sub(r'\s+', ' ', text).strip()
                                    if text:
                                        transcript_text.append(text)
                            
                            if transcript_text:
                                full_transcript = ' '.join(transcript_text)
                                print(f"  ✓ Internal API transcript fetched")
                                return full_transcript
                                
            except (KeyError, IndexError):
                # Try alternative path
                try:
                    # Another possible path for captions
                    renderer_data = initial_data['contents']['twoColumnWatchNextResults']['results']['results']['contents']
                    for content in renderer_data:
                        if 'videoPrimaryInfoRenderer' in content:
                            captions = content['videoPrimaryInfoRenderer'].get('captionTracks', [])
                            for caption in captions:
                                if 'en' in caption.get('languageCode', '').lower():
                                    caption_url = caption.get('baseUrl')
                                    if caption_url:
                                        caption_response = requests.get(caption_url, headers=headers)
                                        caption_response.raise_for_status()
                                        
                                        caption_soup = BeautifulSoup(caption_response.content, 'xml')
                                        text_elements = caption_soup.find_all('text')
                                        
                                        transcript_text = []
                                        for element in text_elements:
                                            if element.text:
                                                text = html.unescape(element.text)
                                                text = re.sub(r'\s+', ' ', text).strip()
                                                if text:
                                                    transcript_text.append(text)
                                        
                                        if transcript_text:
                                            full_transcript = ' '.join(transcript_text)
                                            print(f"  ✓ Internal API transcript fetched")
                                            return full_transcript
                except (KeyError, IndexError):
                    pass
            
            raise Exception("No captions found in internal API data")
            
        except Exception as e:
            raise Exception(f"Internal API method failed: {str(e)}")
    
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
                f"Error generating answer from HuggingFace: {str(e)}"
            )
    
    def _call_llm(self, prompt: str) -> str:
        """
        Call LLM synchronously.
        
        Args:
            prompt: Formatted prompt with context
            
        Returns:
            LLM response text
        """
        response = self.llm.invoke(prompt)
        # Handle both string responses and object responses with content attribute
        if isinstance(response, str):
            return response
        elif hasattr(response, 'content'):
            return response.content
        else:
            return str(response)
    
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
