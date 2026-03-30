"""
Cloud-compatible RAG Pipeline for YouTube Transcript Processing
Supports both local (Ollama) and cloud (OpenRouter, HuggingFace) LLM providers
"""

import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (OSError, ValueError, AttributeError):
        pass

import os
from typing import Optional, Dict, Any
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.proxies import GenericProxyConfig
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound, VideoUnavailable, RequestBlocked, IpBlocked
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
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
    Cloud-compatible RAG Pipeline for YouTube Video Question Answering
    Supports multiple LLM providers: Ollama (local), OpenRouter, HuggingFace
    """
    
    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        retrieval_k: int = 3
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.retrieval_k = retrieval_k
        
        # Cache: {video_id -> {"vectorstore": FAISS, "transcript": str}}
        self.cache = {}
        
        # Initialize LLM and embeddings
        self.embeddings = None
        self.llm = None
        self.youtube_api = None
        self.llm_provider = os.getenv('LLM_PROVIDER', 'ollama')  # ollama, openrouter, huggingface
        self.is_llm_configured = False
        self.is_youtube_api_configured = False
        self._initialize_models()
    
    def _initialize_models(self):
        """Initialize LLM based on provider selection"""
        try:
            # Initialize embeddings (always local)
            self.embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2",
                model_kwargs={'device': 'cpu'},
                encode_kwargs={'normalize_embeddings': True}
            )
            print("✓ Embeddings model loaded")
            
            # Initialize LLM based on provider
            if self.llm_provider == 'ollama':
                self._init_ollama()
            elif self.llm_provider == 'openrouter':
                self._init_openrouter()
            elif self.llm_provider == 'huggingface':
                self._init_huggingface()
            else:
                print(f"⚠️  Unknown LLM provider: {self.llm_provider}, falling back to mock")
                self.llm = self._create_mock_llm()
                self.is_llm_configured = True
                
        except Exception as e:
            print(f"❌ Error initializing models: {str(e)}")
            self.is_llm_configured = False
        
        # Initialize YouTube Data API
        try:
            youtube_api_key = os.getenv('YOUTUBE_DATA_API_KEY')
            if youtube_api_key:
                self.youtube_api = build('youtube', 'v3', developerKey=youtube_api_key)
                self.is_youtube_api_configured = True
                print("✓ YouTube Data API initialized")
        except Exception as e:
            print(f"⚠️  YouTube Data API not configured: {e}")

    def _build_youtube_transcript_api(self) -> YouTubeTranscriptApi:
        """
        Build a YouTubeTranscriptApi instance that can route through a proxy.
        Set either:
          - `YT_TRANSCRIPT_PROXY_HTTP` / `YT_TRANSCRIPT_PROXY_HTTPS`, or
          - `HTTP_PROXY` / `HTTPS_PROXY`
        """
        http_proxy = (
            os.getenv("YT_TRANSCRIPT_PROXY_HTTP")
            or os.getenv("HTTP_PROXY")
            or os.getenv("http_proxy")
        )
        https_proxy = (
            os.getenv("YT_TRANSCRIPT_PROXY_HTTPS")
            or os.getenv("HTTPS_PROXY")
            or os.getenv("https_proxy")
        )

        proxy_config = None
        if http_proxy or https_proxy:
            proxy_config = GenericProxyConfig(http_url=http_proxy, https_url=https_proxy)

        return YouTubeTranscriptApi(proxy_config=proxy_config)

    def _get_requests_proxies(self) -> Optional[dict]:
        """
        Helper for explicit proxy routing for `requests` calls.
        """
        http_proxy = (
            os.getenv("YT_TRANSCRIPT_PROXY_HTTP")
            or os.getenv("HTTP_PROXY")
            or os.getenv("http_proxy")
        )
        https_proxy = (
            os.getenv("YT_TRANSCRIPT_PROXY_HTTPS")
            or os.getenv("HTTPS_PROXY")
            or os.getenv("https_proxy")
        )
        if not http_proxy and not https_proxy:
            return None
        return {"http": http_proxy or https_proxy, "https": https_proxy or http_proxy}
    
    def _init_ollama(self):
        """Initialize Ollama (local) LLM"""
        try:
            from langchain_ollama import OllamaLLM
            model = os.getenv('OLLAMA_MODEL', 'llama3.2')
            base_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
            
            self.llm = OllamaLLM(
                model=model,
                base_url=base_url,
                temperature=0.7,
                num_ctx=4096
            )
            # Test the LLM
            self.llm.invoke("Hello")
            self.is_llm_configured = True
            print(f"✓ Ollama LLM ({model}) initialized")
        except Exception as e:
            print(f"⚠️  Ollama failed: {e}")
            print("   Make sure Ollama is running or switch to cloud provider")
            self.llm = self._create_mock_llm()
            self.is_llm_configured = True
    
    def _init_openrouter(self):
        """Initialize OpenRouter (cloud) LLM - FREE TIER AVAILABLE"""
        try:
            from langchain_openai import ChatOpenAI
            api_key = os.getenv('OPENROUTER_API_KEY')
            if not api_key:
                raise ValueError("OPENROUTER_API_KEY not set")
            
            model = os.getenv('OPENROUTER_MODEL', 'meta-llama/llama-3.2-3b-instruct:free')
            
            self.llm = ChatOpenAI(
                model=model,
                openai_api_key=api_key,
                openai_api_base="https://openrouter.ai/api/v1",
                temperature=0.7,
                max_tokens=512
            )
            # Test the LLM
            self.llm.invoke("Hello")
            self.is_llm_configured = True
            print(f"✓ OpenRouter LLM ({model}) initialized")
        except Exception as e:
            print(f"⚠️  OpenRouter failed: {e}")
            self.llm = self._create_mock_llm()
            self.is_llm_configured = True
    
    def _init_huggingface(self):
        """Initialize HuggingFace Inference API (cloud)"""
        try:
            from langchain_huggingface import HuggingFaceEndpoint
            api_token = os.getenv('HUGGINGFACEHUB_API_TOKEN')
            if not api_token:
                raise ValueError("HUGGINGFACEHUB_API_TOKEN not set")
            
            self.llm = HuggingFaceEndpoint(
                repo_id="google/flan-t5-large",
                task="text-generation",
                max_new_tokens=512,
                temperature=0.7,
                huggingfacehub_api_token=api_token,
                timeout=60
            )
            self.llm.invoke("Hello")
            self.is_llm_configured = True
            print("✓ HuggingFace LLM initialized")
        except Exception as e:
            print(f"⚠️  HuggingFace failed: {e}")
            self.llm = self._create_mock_llm()
            self.is_llm_configured = True
    
    def _create_mock_llm(self):
        """Create a mock LLM for testing/fallback"""
        class MockLLM:
            def invoke(self, prompt):
                lines = prompt.split('\n')
                question = ""
                for line in lines:
                    if line.startswith("Question:"):
                        question = line.replace("Question:", "").strip()
                        break
                return f"Mock response for: {question}. Please configure a real LLM provider (Ollama, OpenRouter, or HuggingFace)."
        return MockLLM()
    
    async def answer_question(self, video_id: str, video_url: str, question: str) -> str:
        """Answer a question about a YouTube video transcript"""
        if not self.is_llm_configured:
            raise ValueError(f"LLM not configured. Set LLM_PROVIDER in .env (options: ollama, openrouter, huggingface)")
        
        # Check cache
        if video_id not in self.cache:
            print(f"📥 Processing video {video_id}...")
            await self._process_video(video_id, video_url)
        else:
            print(f"✓ Using cached data for video {video_id}")
        
        # Retrieve relevant chunks
        vectorstore = self.cache[video_id]["vectorstore"]
        docs = vectorstore.similarity_search(question, k=self.retrieval_k)
        
        if not docs:
            return "Sorry, I couldn't find relevant information in the video transcript."
        
        # Generate answer
        answer = await self._generate_answer(question, docs)
        return answer
    
    async def _process_video(self, video_id: str, video_url: str):
        """Process a video: fetch transcript, chunk, embed, create vectorstore"""
        loop = asyncio.get_event_loop()
        
        # Fetch transcript
        print(f"  ⬇️  Fetching transcript...")
        transcript_text = await loop.run_in_executor(None, self._fetch_transcript, video_id)
        
        # Split into chunks
        print(f"  ✂️  Splitting into chunks...")
        chunks = await loop.run_in_executor(None, self._split_text, transcript_text)
        
        if not chunks:
            raise ValueError(f"No content found in transcript")
        
        # Create vectorstore
        print(f"  🧠 Creating embeddings and vector store...")
        vectorstore = await loop.run_in_executor(None, self._create_vectorstore, chunks)
        
        # Cache
        self.cache[video_id] = {
            "vectorstore": vectorstore,
            "transcript": transcript_text,
            "chunks": chunks
        }
        
        print(f"✓ Video {video_id} processed: {len(chunks)} chunks cached")
    
    def _fetch_transcript(self, video_id: str) -> str:
        """Fetch YouTube transcript with multiple fallback strategies"""
        # Try YouTube Data API first
        if self.is_youtube_api_configured:
            try:
                return self._fetch_transcript_youtube_data_api(video_id)
            except Exception as e:
                print(f"  ⚠️  YouTube Data API failed: {str(e)}")
        
        # Try youtube-transcript-api
        try:
            return self._fetch_transcript_youtube_api(video_id)
        except Exception as e:
            print(f"  ⚠️  YouTube API failed: {str(e)}")
        
        # Try web scraping
        try:
            return self._fetch_transcript_web_scraping(video_id)
        except Exception as e:
            print(f"  ⚠️  Web scraping failed: {str(e)}")
        
        raise ValueError(f"Unable to retrieve transcript for video {video_id}")
    
    def _fetch_transcript_youtube_data_api(self, video_id: str) -> str:
        """Fetch using YouTube Data API"""
        try:
            video_response = self.youtube_api.videos().list(
                part="snippet,contentDetails",
                id=video_id,
            ).execute()

            if not video_response.get("items"):
                raise ValueError(f"Video {video_id} not found")

            video = video_response["items"][0]
            print(f"  📹 Found video: {video['snippet'].get('title')}")

            captions_response = self.youtube_api.captions().list(
                part="snippet",
                videoId=video_id,
            ).execute()

            items = captions_response.get("items") or []
            if not items:
                raise ValueError("No captions available for this video")

            english_caption = None
            for caption in items:
                snippet = caption.get("snippet") or {}
                if "en" in (snippet.get("language") or "").lower():
                    english_caption = caption
                    break

            if not english_caption:
                english_caption = items[0]
                print(f"  ⚠️  Using {english_caption['snippet'].get('language')} captions (English not available)")

            caption_download_url = english_caption["snippet"]["downloadUrl"]
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }

            proxies = self._get_requests_proxies()
            response = requests.get(
                caption_download_url,
                headers=headers,
                proxies=proxies,
                timeout=30,
            )
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "xml")
            text_elements = soup.find_all("text")
            if not text_elements:
                raise ValueError("No text content found in captions")

            transcript_parts = []
            for element in text_elements:
                if element.text:
                    text = html.unescape(element.text)
                    text = re.sub(r"\s+", " ", text).strip()
                    if text and text not in ["[Music]", "[Applause]"]:
                        transcript_parts.append(text)

            if not transcript_parts:
                raise ValueError("No valid transcript content found")

            transcript_text = " ".join(transcript_parts)
            print(f"  ✓ YouTube Data API transcript fetched ({len(transcript_parts)} segments)")
            return transcript_text

        except Exception as e:
            raise Exception(f"YouTube Data API method failed: {str(e)}")
    
    def _fetch_transcript_youtube_api(self, video_id: str) -> str:
        """Fetch using youtube-transcript-api"""
        ytt = self._build_youtube_transcript_api()
        
        language_combinations = [
            ("en", "en-US", "en-GB"),
            ("en",),
            ("en-US",),
            ("hi", "en"),
            ("es", "en"),
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
            except Exception as e:
                continue
        
        raise NoTranscriptFound(f"No transcript found for video {video_id}")
    
    def _fetch_transcript_web_scraping(self, video_id: str) -> str:
        """Fetch using web scraping as fallback"""
        import urllib.request
        import json
        
        url = f"https://www.youtube.com/watch?v={video_id}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            html_content = response.read().decode('utf-8')
        
        # Try to find caption tracks in the page
        if '"captions":' in html_content:
            try:
                captions_json = json.loads(html_content.split('"captions":')[1].split(']')[0] + ']')
                if captions_json and len(captions_json) > 0:
                    caption_track = captions_json[0]
                    if 'baseUrl' in caption_track:
                        caption_url = caption_track['baseUrl']
                        caption_req = urllib.request.Request(caption_url, headers=headers)
                        with urllib.request.urlopen(caption_req, timeout=10) as response:
                            caption_xml = response.read().decode('utf-8')
                        
                        # Parse XML to extract text
                        import xml.etree.ElementTree as ET
                        root = ET.fromstring(caption_xml)
                        texts = [elem.text for elem in root.iter() if elem.text]
                        return " ".join(texts)
            except Exception as e:
                print(f"Web scraping parse error: {e}")
        
        raise ValueError("Could not fetch transcript via web scraping")
    
    def _split_text(self, text: str) -> list:
        """Split text into chunks"""
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        return text_splitter.split_text(text)
    
    def _create_vectorstore(self, chunks: list) -> FAISS:
        """Create FAISS vectorstore from chunks"""
        return FAISS.from_texts(chunks, self.embeddings)
    
    async def _generate_answer(self, question: str, docs: list) -> str:
        """Generate answer using LLM with retrieved context"""
        context = "\n\n".join([doc.page_content for doc in docs])
        
        prompt_template = PromptTemplate(
            input_variables=["context", "question"],
            template="""Based on the following video transcript excerpts, please answer the question.

Context from video transcript:
{context}

Question: {question}

Please provide a concise, accurate answer based only on the context provided. If the context doesn't contain enough information to answer the question, say so.

Answer:"""
        )
        
        loop = asyncio.get_event_loop()
        
        try:
            formatted_prompt = prompt_template.format(
                context=context,
                question=question
            )
            
            response = await loop.run_in_executor(
                None,
                self._call_llm,
                formatted_prompt
            )
            
            return response
            
        except Exception as e:
            print(f"❌ Error generating answer: {str(e)}")
            raise ValueError(f"Error generating answer: {str(e)}")
    
    def _call_llm(self, prompt: str) -> str:
        """Call LLM and handle response"""
        response = self.llm.invoke(prompt)
        
        # Handle different response types
        if isinstance(response, str):
            return response
        elif hasattr(response, 'content'):
            return response.content
        else:
            return str(response)
    
    def clear_cache(self, video_id: Optional[str] = None):
        """Clear cache for specific video or all videos"""
        if video_id:
            if video_id in self.cache:
                del self.cache[video_id]
                print(f"✓ Cache cleared for video {video_id}")
        else:
            self.cache.clear()
            print("✓ All cache cleared")
