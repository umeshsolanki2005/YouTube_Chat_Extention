# Integration Guide: Merging Your Existing RAG Code

If you already have a working RAG chatbot in Colab or VS Code, this guide shows you exactly where and how to integrate it.

## 📍 Architecture Overview

Your existing code likely has three parts:
1. **Transcript Loading** - Fetching YouTube transcripts
2. **RAG Pipeline** - Chunking, embeddings, retrieval
3. **Answer Generation** - Gemini prompt and chain

The project already has all three! You have options:
- ✓ Use the existing implementations as-is
- ✓ Replace specific components with your code
- ✓ Mix and match the best parts

## 🔄 Common Integration Scenarios

### Scenario 1: Your RAG Code is Better Than Mine

If your chunking/splitting strategy or embeddings approach is superior:

**In `backend/rag_pipeline.py`, replace these methods:**

```python
# REPLACE THIS METHOD with your chunking code:
def _split_text(self, text: str) -> list[str]:
    """Original implementation here"""
    splitter = RecursiveCharacterTextSplitter(...)
    chunks = splitter.split_text(text)
    return chunks

# WITH YOUR CODE that still returns list[str]:
def _split_text(self, text: str) -> list[str]:
    """Your superior chunking strategy"""
    # Your text splitting logic here
    # Just make sure it returns: list of strings (chunks)
    
    # Example: If you have a custom chunker
    from my_custom_chunker import MyChunker
    chunker = MyChunker(
        max_chunk_size=1500,
        overlap=300,
        strategy="sentence_aware"
    )
    chunks = chunker.chunk(text)
    return chunks
```

**Just ensure:**
- Input: `text: str` (the full transcript)
- Output: `list[str]` (list of chunks)

### Scenario 2: You Want Your Embeddings Model

Replace Google's embeddings with OpenAI, local models, or custom embeddings:

```python
def _initialize_models(self):
    """Initialize with your embeddings model"""
    try:
        # EXAMPLE: Using OpenAI embeddings
        from langchain_openai import OpenAIEmbeddings
        
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            api_key=os.getenv('OPENAI_API_KEY')
        )
        
        # Keep Gemini for LLM generation
        self.llm = ChatGoogleGenerativeAI(...)
        self.is_gemini_configured = True
        
    except Exception as e:
        print(f"Error: {str(e)}")
        self.is_gemini_configured = False

# Update requirements.txt:
# langchain-openai>=0.0.1
```

**Other embedding options:**
```python
# HuggingFace (local, free)
from langchain_community.embeddings import HuggingFaceEmbeddings
self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

# Cohere
from langchain_community.embeddings import CohereEmbeddings
self.embeddings = CohereEmbeddings(cohere_api_key=api_key)

# Self-hosted with sentence-transformers
embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-mpnet-base-v2"
)
```

### Scenario 3: Your Prompt Template is Better

Replace the answer generation prompt:

```python
async def _generate_answer(self, question: str, docs: list) -> str:
    """Generate with your custom prompt"""
    
    # YOUR CUSTOM PROMPT TEMPLATE
    SYSTEM_PROMPT = """You are an expert video analyst. 
    Using ONLY the provided transcript excerpts, answer the user's question.
    If information is unclear or missing, explicitly state that.
    Cite specific timing if relevant.
    Keep answers concise but comprehensive."""
    
    PROMPT_TEMPLATE = """{system_prompt}

Transcript Excerpts:
{context}

User Question: {question}

Answer:"""
    
    # Build context
    context = "\n---\n".join([doc.page_content for doc in docs])
    
    # Format prompt your way
    formatted_prompt = PROMPT_TEMPLATE.format(
        system_prompt=SYSTEM_PROMPT,
        context=context,
        question=question
    )
    
    # Call LLM
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        self._call_llm,
        formatted_prompt
    )
    
    return response
```

### Scenario 4: Use Different LLM Instead of Gemini

Use OpenAI GPT, Claude, Llama, etc.:

```python
def _initialize_models(self):
    """Use GPT-4 instead of Gemini"""
    try:
        from langchain_openai import ChatOpenAI
        
        self.embeddings = GoogleGenerativeAIEmbeddings(...)  # Keep this
        
        # Replace LLM with ChatGPT
        self.llm = ChatOpenAI(
            model="gpt-4-turbo",
            temperature=0.3,
            api_key=os.getenv('OPENAI_API_KEY')
        )
        
        self.is_gemini_configured = True
        
    except Exception as e:
        print(f"Error: {str(e)}")
        self.is_gemini_configured = False
```

**Update .env:**
```
OPENAI_API_KEY=sk-...
```

**Update requirements.txt:**
```
langchain-openai>=0.0.1
```

### Scenario 5: Use Different Vector Store

Replace FAISS with Chroma, Pinecone, Weaviate, etc.:

```python
def _create_vectorstore(self, chunks: list[str]):
    """Use Chroma instead of FAISS"""
    from langchain_community.vectorstores import Chroma
    
    vectorstore = Chroma.from_texts(
        texts=chunks,
        embedding=self.embeddings,
        persist_directory="/tmp/chroma_db"
    )
    return vectorstore
```

Vector stores that work with LangChain:
- FAISS (current, local)
- Chroma (local, persistent)
- Pinecone (cloud, scales)
- Weaviate (cloud/local)
- Milvus (open-source)

### Scenario 6: Bring Your Entire RAG Chain

If you have a complete Langchain QA chain already built:

```python
async def _generate_answer(self, question: str, docs: list) -> str:
    """Use your existing LangChain chain"""
    
    # Your existing chain from Colab
    from my_rag_module import my_qa_chain, retriever
    
    # Prepare context
    context = "\n".join([doc.page_content for doc in docs])
    
    # Run your chain
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: my_qa_chain.invoke({
            "context": context,
            "question": question
        })
    )
    
    # Return answer
    if isinstance(result, dict):
        return result.get("output_text", result.get("answer", str(result)))
    return str(result)
```

## 📋 Step-by-Step Example: Full Integration

**Let's say you have this existing Colab code:**

```python
# Your existing code structure:

# 1. TRANSCRIPT LOADING
def get_youtube_transcript(video_id):
    """Your custom transcript fetching"""
    from my_custom_lib import get_vtt_format_transcript
    return get_vtt_format_transcript(video_id)

# 2. CHUNKING
def chunk_transcript(text, chunk_size=800, overlap=100):
    """Your specific chunking strategy"""
    my_chunks = []
    for i in range(0, len(text), chunk_size - overlap):
        my_chunks.append(text[i:i + chunk_size])
    return my_chunks

# 3. EMBEDDINGS
def create_embeddings(chunks):
    """Using sentence-transformers locally"""
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer('all-MiniLM-L6-v2')
    embeddings = model.encode(chunks)
    return embeddings

# 4. ANSWER GENERATION
def generate_answer(question, context, llm):
    """Your Gemini prompt"""
    prompt = f"""Answer based only on this transcript:
    {context}
    Question: {question}"""
    return llm.generate_content(prompt).text
```

**Integration into the project:**

1. **Copy your functions to a new file** `backend/my_custom_rag.py`

2. **Update `rag_pipeline.py` to use them:**

```python
# At the top of rag_pipeline.py, add:
from my_custom_rag import (
    get_youtube_transcript,
    chunk_transcript,
    create_embeddings,
    generate_answer
)

# Then in RAGPipeline class:
class RAGPipeline:
    def __init__(self, ...):
        # Your parameters
        self.chunk_size = 800
        self.chunk_overlap = 100
        self.cache = {}
        self._initialize_models()
    
    def _initialize_models(self):
        """Your embeddings model"""
        try:
            from sentence_transformers import SentenceTransformer
            self.embeddings_model = SentenceTransformer('all-MiniLM-L6-v2')
            self.llm = ChatGoogleGenerativeAI(...)
            self.is_gemini_configured = True
        except Exception as e:
            print(f"Error: {str(e)}")
    
    def _fetch_transcript(self, video_id: str) -> str:
        # Use YOUR function
        return get_youtube_transcript(video_id)
    
    def _split_text(self, text: str) -> list[str]:
        # Use YOUR function
        return chunk_transcript(text, self.chunk_size, self.chunk_overlap)
    
    def _create_vectorstore(self, chunks: list[str]):
        # IMPORTANT: `_create_vectorstore` must still return
        # a vectorstore with .similarity_search() method
        # If you just have embeddings, wrap them:
        from langchain_community.vectorstores import FAISS
        from langchain.schema import Document
        
        embeddings = create_embeddings(chunks)
        
        # Convert to FAISS vectorstore that works with the rest of the code
        docs = [Document(page_content=chunk) for chunk in chunks]
        vectorstore = FAISS.from_documents(
            docs,
            self.embeddings
        )
        return vectorstore
    
    async def _generate_answer(self, question: str, docs: list) -> str:
        # Use YOUR function
        context = "\n".join([doc.page_content for doc in docs])
        loop = asyncio.get_event_loop()
        answer = await loop.run_in_executor(
            None,
            lambda: generate_answer(question, context, self.llm)
        )
        return answer
```

3. **Update `requirements.txt`:**
```
# Keep existing:
fastapi==0.104.1
uvicorn[standard]==0.24.0
python-dotenv==1.0.0
youtube-transcript-api==0.6.1
langchain==0.1.0
langchain-google-genai==0.0.11
google-generativeai==0.3.0
faiss-cpu==1.7.4

# Add your dependencies:
sentence-transformers==2.2.2
my_custom_lib==1.0.0  # If you have a package
```

4. **Install and test:**
```bash
pip install -r requirements.txt
python app.py
```

## ✅ Checklist for Integration

- [ ] Decide which components to replace (transcript, chunking, embeddings, LLM, prompt)
- [ ] Copy your code to `backend/` folder
- [ ] Update the corresponding methods in `rag_pipeline.py`
- [ ] Update `requirements.txt` with any new dependencies
- [ ] Update `.env.example` with new API key requirements (if any)
- [ ] Test with `python app.py`
- [ ] Test with Chrome extension
- [ ] Ask a test question to verify end-to-end

## 🔍 Testing Your Integration

**1. Check backend starts OK:**
```bash
python app.py
# Should see: ✓ Gemini models initialized successfully
# Or: ✓ Custom models initialized successfully
```

**2. Test health endpoint:**
```bash
curl http://localhost:8000/health
# Should return: {"status": "healthy", ...}
```

**3. Test through API:**
```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "video_id": "dQw4w9WgXcQ",
    "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "question": "What is this video?"
  }'
```

**4. Test through Chrome extension:**
- Go to a YouTube video
- Open side panel
- Ask a question
- Verify answer appears and matches your RAG logic

## 🚀 Performance Tips

**For faster processing:**
- Use smaller `chunk_size` (500-800 chars)
- Use smaller embedding model (e.g., `gte-small` or `MiniLM`)
- Cache stays in memory between requests

**For better answers:**
- Use larger `retrieval_k` (5-10 chunks)
- Use better embedding model (e.g., `bge-large-en`)
- Fine-tune your prompt based on actual Q&A

## 📱 Debugging Integration

**Backend logs:** Check terminal where `python app.py` is running

**Browser console:** F12 → Console tab → Check for errors

**API docs:** Visit `http://localhost:8000/docs`

**Enable verbose logging:**

```python
# In app.py, before uvicorn.run():
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 🎓 Important Notes

1. **Interface compatibility:** Your functions must follow the same input/output types
2. **Asyncio:** Backend uses async, so wrap blocking operations in executors
3. **Caching:** Cache is per video_id, clears on backend restart
4. **Error handling:** Wrap everything in try/except, return helpful messages
5. **Testing:** Always test end-to-end with the extension, not just API

---

**Common gotcha:** Make sure your code returns the right types:
- `_fetch_transcript()` returns `str`
- `_split_text()` returns `list[str]`
- `_create_vectorstore()` returns obj with `.similarity_search()`
- `_generate_answer()` returns `str` (via async)

**Questions?** Check README.md or modify the methods incrementally, testing after each change.
