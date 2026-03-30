"""
Lightweight cloud RAG pipeline for Render free tier.

Design goals:
- No local embeddings / FAISS / torch downloads.
- Use external LLM APIs only (OpenRouter or HuggingFace Inference API).
- Fast startup and fail-fast behavior for /ask.
- Background transcript pre-processing to keep request latency low.
"""

import asyncio
import html
import os
import re
import json
import xml.etree.ElementTree as ET
from collections import Counter
from typing import Dict, List, Optional

import requests
from googleapiclient.discovery import build
from huggingface_hub import InferenceClient
from openai import OpenAI
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    RequestBlocked,
    TranscriptsDisabled,
    VideoUnavailable,
)
from youtube_transcript_api.proxies import GenericProxyConfig


STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "of", "in", "on", "at", "for", "is",
    "are", "was", "were", "be", "this", "that", "it", "with", "as", "by", "from",
    "what", "who", "when", "where", "why", "how", "about", "does", "do", "did",
}


class RAGPipeline:
    def __init__(self, chunk_size: int = 1200, retrieval_k: int = 4):
        self.chunk_size = chunk_size
        self.retrieval_k = retrieval_k

        # video_id -> {"transcript": str, "chunks": List[str], "ready": bool, "error": Optional[str]}
        self.cache: Dict[str, Dict] = {}
        self.processing_tasks: Dict[str, asyncio.Task] = {}

        self.youtube_api = None
        self.is_youtube_api_configured = False
        self.llm_provider = os.getenv("LLM_PROVIDER", "openrouter").lower()
        self.is_llm_configured = False

        self.openrouter_client: Optional[OpenAI] = None
        self.hf_client: Optional[InferenceClient] = None

        self.request_timeout_seconds = int(os.getenv("CLOUD_REQUEST_TIMEOUT_SECONDS", "55"))
        self.transcript_timeout_seconds = int(os.getenv("TRANSCRIPT_TIMEOUT_SECONDS", "35"))
        self._initialize_clients()

    def _initialize_clients(self) -> None:
        youtube_api_key = os.getenv("YOUTUBE_DATA_API_KEY")
        if youtube_api_key:
            self.youtube_api = build("youtube", "v3", developerKey=youtube_api_key)
            self.is_youtube_api_configured = True
            print("[OK] YouTube Data API initialized")

        if self.llm_provider == "openrouter":
            api_key = os.getenv("OPENROUTER_API_KEY")
            if not api_key:
                raise ValueError("OPENROUTER_API_KEY is required when LLM_PROVIDER=openrouter")
            self.openrouter_client = OpenAI(
                api_key=api_key,
                base_url="https://openrouter.ai/api/v1",
            )
            self.is_llm_configured = True
            print("[OK] OpenRouter client initialized")
            return

        if self.llm_provider == "huggingface":
            token = os.getenv("HUGGINGFACEHUB_API_TOKEN")
            if not token:
                raise ValueError("HUGGINGFACEHUB_API_TOKEN is required when LLM_PROVIDER=huggingface")
            self.hf_client = InferenceClient(token=token)
            self.is_llm_configured = True
            print("[OK] HuggingFace Inference client initialized")
            return

        raise ValueError("LLM_PROVIDER must be 'openrouter' or 'huggingface' in cloud mode")

    def _build_youtube_transcript_api(self) -> YouTubeTranscriptApi:
        http_proxy = os.getenv("YT_TRANSCRIPT_PROXY_HTTP") or os.getenv("HTTP_PROXY") or os.getenv("http_proxy")
        https_proxy = os.getenv("YT_TRANSCRIPT_PROXY_HTTPS") or os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
        if http_proxy or https_proxy:
            return YouTubeTranscriptApi(proxy_config=GenericProxyConfig(http_url=http_proxy, https_url=https_proxy))
        return YouTubeTranscriptApi()

    async def ensure_video_processed(self, video_id: str, video_url: str) -> bool:
        current = self.cache.get(video_id)
        if current and current.get("ready"):
            return True
        if current and current.get("error"):
            # Keep the error state stable; don't re-queue forever on each request.
            return False

        running = self.processing_tasks.get(video_id)
        if running and not running.done():
            return False

        self.cache[video_id] = {"transcript": "", "chunks": [], "ready": False, "error": None}
        self.processing_tasks[video_id] = asyncio.create_task(self._process_video(video_id, video_url))
        return False

    async def _process_video(self, video_id: str, video_url: str) -> None:
        try:
            transcript = await asyncio.wait_for(
                asyncio.to_thread(self._fetch_transcript, video_id),
                timeout=self.transcript_timeout_seconds,
            )
            chunks = self._split_text(transcript)
            self.cache[video_id] = {
                "transcript": transcript,
                "chunks": chunks,
                "ready": True,
                "error": None,
            }
            print(f"[OK] Cached transcript for {video_id} ({len(chunks)} chunks)")
        except asyncio.TimeoutError:
            self.cache[video_id] = {
                "transcript": "",
                "chunks": [],
                "ready": False,
                "error": f"Transcript fetch timed out after {self.transcript_timeout_seconds}s",
            }
            print(f"[ERR] Transcript processing timed out for {video_id}")
        except Exception as exc:
            self.cache[video_id] = {
                "transcript": "",
                "chunks": [],
                "ready": False,
                "error": str(exc),
            }
            print(f"[ERR] Transcript processing failed for {video_id}: {exc}")
        finally:
            self.processing_tasks.pop(video_id, None)

    async def answer_question(self, video_id: str, video_url: str, question: str) -> str:
        if not self.is_llm_configured:
            raise ValueError("LLM client is not configured")

        entry = self.cache.get(video_id)
        if entry and entry.get("error"):
            return await self._answer_from_video_metadata(video_id, question, entry.get("error"))

        if not entry or not entry.get("ready"):
            is_ready = await self.ensure_video_processed(video_id, video_url)
            if not is_ready:
                task = self.processing_tasks.get(video_id)
                if task and not task.done():
                    try:
                        wait_budget = max(8, min(20, self.request_timeout_seconds - 10))
                        await asyncio.wait_for(task, timeout=wait_budget)
                    except asyncio.TimeoutError:
                        pass

                entry = self.cache.get(video_id)
                if entry and entry.get("error"):
                    return await self._answer_from_video_metadata(video_id, question, entry.get("error"))
                if entry and entry.get("ready"):
                    pass
                else:
                    raise ValueError("Video transcript is being prepared in background. Please retry in 10-20 seconds.")

        entry = self.cache.get(video_id) or {}
        if entry.get("error"):
            return await self._answer_from_video_metadata(video_id, question, entry.get("error"))

        chunks = entry.get("chunks") or []
        context_chunks = self._retrieve_relevant_chunks(question, chunks)
        if not context_chunks:
            return "I could not find enough transcript context to answer this question."

        prompt = self._build_prompt(question, context_chunks)
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._call_llm, prompt),
                timeout=self.request_timeout_seconds,
            )
        except Exception as exc:
            # Cloud free-tier providers can rate limit; provide a useful fallback answer.
            return self._extractive_fallback_answer(question, context_chunks, exc)

    def _fetch_transcript(self, video_id: str) -> str:
        # Primary path: youtube-transcript-api
        ytt = self._build_youtube_transcript_api()
        language_combinations = [
            ("en", "en-US", "en-GB"),
            ("en",),
            ("es", "en"),
            ("hi", "en"),
            ("fr", "en"),
        ]
        for languages in language_combinations:
            try:
                fetched = ytt.fetch(video_id, languages=languages)
                text = " ".join(s.text for s in fetched).strip()
                if text:
                    return text
            except (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable, RequestBlocked):
                continue
            except Exception:
                continue

        # Fallback path: parse caption tracks from watch page HTML
        try:
            return self._fetch_transcript_web_scraping(video_id)
        except Exception as exc:
            print(f"[WARN] Web fallback failed: {exc}")

        # Fallback path: direct timedtext endpoints
        try:
            return self._fetch_transcript_timedtext(video_id)
        except Exception as exc:
            print(f"[WARN] Timedtext fallback failed: {exc}")

        # Optional diagnostic using YouTube Data API (doesn't attempt caption download)
        if self.is_youtube_api_configured:
            try:
                self._fetch_transcript_youtube_data_api(video_id)
            except Exception as exc:
                print(f"[WARN] YouTube Data API info check failed: {exc}")

        raise ValueError(
            f"Unable to fetch transcript for video {video_id}. "
            "Captions may be unavailable/blocked for this request."
        )

    def _fetch_transcript_youtube_data_api(self, video_id: str) -> str:
        """
        Diagnostic-only check.
        NOTE: `captions().list(part='snippet')` does not provide `downloadUrl` in most cases.
        """
        captions_response = self.youtube_api.captions().list(part="snippet", videoId=video_id).execute()
        items = captions_response.get("items") or []
        if not items:
            raise ValueError("No caption tracks found via YouTube Data API")
        langs = [((x.get("snippet") or {}).get("language") or "?") for x in items]
        raise ValueError(f"Caption tracks exist ({', '.join(langs)}), but direct download URL is not exposed")

    def _fetch_transcript_web_scraping(self, video_id: str) -> str:
        """
        Parse caption track URLs from watch page HTML and fetch timedtext XML.
        This is lightweight and works without local models.
        """
        watch_url = f"https://www.youtube.com/watch?v={video_id}"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
        }

        page = requests.get(watch_url, headers=headers, timeout=20)
        page.raise_for_status()
        html_text = page.text

        tracks = self._extract_caption_tracks_from_html(html_text)
        if not tracks:
            raise ValueError("captionTracks list is empty")

        # prefer English, else first available
        track = None
        for t in tracks:
            if "en" in (t.get("languageCode", "").lower()):
                track = t
                break
        if track is None:
            track = tracks[0]

        base_url = track.get("baseUrl")
        if not base_url:
            raise ValueError("No baseUrl in selected caption track")

        xml_resp = requests.get(base_url, headers=headers, timeout=20)
        xml_resp.raise_for_status()
        xml_text = xml_resp.text

        text_elements = re.findall(r"<text[^>]*>(.*?)</text>", xml_text, flags=re.DOTALL)
        cleaned = []
        for t in text_elements:
            val = re.sub(r"\s+", " ", html.unescape(t)).strip()
            if val:
                cleaned.append(val)

        transcript = " ".join(cleaned).strip()
        if not transcript:
            raise ValueError("Timedtext XML was empty")
        return transcript

    def _extract_caption_tracks_from_html(self, html_text: str) -> List[dict]:
        """
        Extract caption tracks from ytInitialPlayerResponse.
        More reliable than naive regex on 'captionTracks' array text.
        """
        patterns = [
            r"ytInitialPlayerResponse\s*=\s*(\{.*?\});",
            r'window\["ytInitialPlayerResponse"\]\s*=\s*(\{.*?\});',
        ]

        for pattern in patterns:
            match = re.search(pattern, html_text, flags=re.DOTALL)
            if not match:
                continue
            try:
                payload = json.loads(match.group(1))
                captions = payload.get("captions", {}).get("playerCaptionsTracklistRenderer", {})
                tracks = captions.get("captionTracks") or []
                if tracks:
                    return tracks
            except Exception:
                continue
        return []

    def _fetch_transcript_timedtext(self, video_id: str) -> str:
        """
        Direct timedtext fallback:
        1) get available tracks
        2) request transcript XML by lang (and kind when present)
        """
        list_url = "https://www.youtube.com/api/timedtext"
        list_resp = requests.get(
            list_url,
            params={"type": "list", "v": video_id},
            timeout=20,
        )
        list_resp.raise_for_status()

        xml_text = list_resp.text.strip()
        if not xml_text:
            raise ValueError("No timedtext track list returned")

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            raise ValueError(f"Timedtext list parse error: {exc}")

        tracks = []
        for track in root.findall("track"):
            lang_code = track.attrib.get("lang_code")
            kind = track.attrib.get("kind", "")
            if lang_code:
                tracks.append((lang_code, kind))

        if not tracks:
            raise ValueError("No track entries in timedtext list")

        preferred = []
        # Prefer English tracks first
        for lang, kind in tracks:
            if lang.lower().startswith("en"):
                preferred.append((lang, kind))
        for pair in tracks:
            if pair not in preferred:
                preferred.append(pair)

        for lang, kind in preferred:
            params = {"v": video_id, "lang": lang}
            if kind:
                params["kind"] = kind
            resp = requests.get(list_url, params=params, timeout=20)
            if resp.status_code != 200:
                continue

            body = resp.text
            text_elements = re.findall(r"<text[^>]*>(.*?)</text>", body, flags=re.DOTALL)
            cleaned = []
            for t in text_elements:
                val = re.sub(r"\s+", " ", html.unescape(t)).strip()
                if val:
                    cleaned.append(val)

            transcript = " ".join(cleaned).strip()
            if transcript:
                return transcript

        raise ValueError("Timedtext tracks exist but transcript fetch returned empty content")

    def _split_text(self, text: str) -> List[str]:
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            return []
        chunks: List[str] = []
        start = 0
        n = len(text)
        while start < n:
            end = min(start + self.chunk_size, n)
            if end < n:
                ws = text.rfind(" ", start, end)
                if ws > start + int(self.chunk_size * 0.6):
                    end = ws
            chunks.append(text[start:end].strip())
            start = end
        return [c for c in chunks if c]

    def _retrieve_relevant_chunks(self, question: str, chunks: List[str]) -> List[str]:
        if not chunks:
            return []
        tokens = [
            t for t in re.findall(r"[a-zA-Z0-9']+", question.lower())
            if t not in STOPWORDS and len(t) > 2
        ]
        if not tokens:
            return chunks[: self.retrieval_k]

        scored = []
        for idx, chunk in enumerate(chunks):
            low = chunk.lower()
            score = 0
            counts = Counter(re.findall(r"[a-zA-Z0-9']+", low))
            for token in tokens:
                score += counts.get(token, 0)
            if score > 0:
                scored.append((score, idx, chunk))

        if not scored:
            return chunks[: self.retrieval_k]

        scored.sort(key=lambda x: (-x[0], x[1]))
        return [c for _, _, c in scored[: self.retrieval_k]]

    def _build_prompt(self, question: str, context_chunks: List[str]) -> str:
        context = "\n\n---\n\n".join(context_chunks)
        return (
            "You are an assistant answering questions about a YouTube video's transcript.\n"
            "Answer ONLY from the provided transcript context.\n"
            "If the answer is not in context, say you cannot find it in the transcript.\n"
            "Keep response concise.\n\n"
            f"Transcript Context:\n{context}\n\n"
            f"Question: {question}\n\n"
            "Answer:"
        )

    def _call_llm(self, prompt: str) -> str:
        if self.llm_provider == "openrouter":
            model = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.2-3b-instruct:free")
            completion = self.openrouter_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=500,
            )
            return completion.choices[0].message.content.strip()

        model = os.getenv("HUGGINGFACE_MODEL", "HuggingFaceH4/zephyr-7b-beta")
        result = self.hf_client.text_generation(
            prompt,
            model=model,
            max_new_tokens=400,
            temperature=0.2,
            do_sample=False,
        )
        return str(result).strip()

    def _extractive_fallback_answer(self, question: str, context_chunks: List[str], err: Exception) -> str:
        """
        Deterministic fallback when LLM provider fails/rate-limits.
        Returns best-effort answer from transcript context so user isn't blocked.
        """
        best = context_chunks[0] if context_chunks else ""
        # Keep output concise for extension UI.
        snippet = best[:700].strip()
        if not snippet:
            return "Transcript is available, but AI generation is temporarily unavailable. Please retry in a moment."
        return (
            "AI provider is temporarily unavailable (rate-limited). "
            "Best transcript snippet:\n\n"
            f"{snippet}"
        )

    async def _answer_from_video_metadata(self, video_id: str, question: str, transcript_error: Optional[str]) -> str:
        """
        Fallback path when transcript cannot be fetched.
        Uses YouTube metadata so user still receives a useful answer.
        """
        if not self.is_youtube_api_configured:
            raise ValueError(
                "Transcript unavailable and metadata fallback is not configured (YOUTUBE_DATA_API_KEY missing)."
            )

        def _get_meta():
            response = self.youtube_api.videos().list(part="snippet", id=video_id).execute()
            items = response.get("items") or []
            if not items:
                return None
            snippet = items[0].get("snippet", {})
            return {
                "title": snippet.get("title", ""),
                "description": snippet.get("description", ""),
                "channel": snippet.get("channelTitle", ""),
            }

        meta = await asyncio.to_thread(_get_meta)
        if not meta:
            raise ValueError(f"Transcript unavailable and video metadata not found for {video_id}.")

        prompt = (
            "Transcript is unavailable. Use ONLY this video metadata to answer the user's question.\n"
            "Be explicit that this answer is metadata-based, not transcript-based.\n\n"
            f"Video title: {meta['title']}\n"
            f"Channel: {meta['channel']}\n"
            f"Description: {meta['description'][:3000]}\n\n"
            f"Question: {question}\n"
            "Answer:"
        )
        try:
            ans = await asyncio.wait_for(
                asyncio.to_thread(self._call_llm, prompt),
                timeout=self.request_timeout_seconds,
            )
            return (
                "Transcript could not be fetched for this video, so this is a metadata-based answer:\n\n"
                f"{ans}"
            )
        except Exception:
            # deterministic fallback when provider is rate-limited
            return (
                "Transcript could not be fetched for this video. "
                "Based on title/description, this video appears to be about:\n\n"
                f"- {meta['title']}\n"
                f"- Channel: {meta['channel']}\n"
                f"- Description summary: {meta['description'][:400]}"
            )

    def clear_cache(self, video_id: Optional[str] = None):
        if video_id:
            self.cache.pop(video_id, None)
            task = self.processing_tasks.pop(video_id, None)
            if task and not task.done():
                task.cancel()
            return
        for _, task in list(self.processing_tasks.items()):
            if not task.done():
                task.cancel()
        self.processing_tasks.clear()
        self.cache.clear()
