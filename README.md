# GEN_AI Workspace

This repository is a local workspace for GenAI projects..

## Projects

- `youtube-rag-extension/`: Chrome extension + FastAPI backend for asking questions about YouTube transcripts with a RAG pipeline.

## Quick Start (YouTube RAG Extension)

1. Open a terminal in `youtube-rag-extension/backend`.
2. Create and activate a virtual environment.
3. Install dependencies:
   - `pip install -r requirements.txt`
4. Configure environment variables in `backend/.env`.
5. Start backend:
   - `python app.py`
6. In Chrome, load unpacked extension from:
   - `youtube-rag-extension/extension`

## Useful Docs

- `youtube-rag-extension/README.md`
- `youtube-rag-extension/SETUP_GUIDE.md`
- `youtube-rag-extension/DEPLOYMENT_GUIDE.md`

## Notes

- Keep API keys only in backend env files; never in extension code.
- Runtime logs in `youtube-rag-extension/backend/*.log` are generated locally.
