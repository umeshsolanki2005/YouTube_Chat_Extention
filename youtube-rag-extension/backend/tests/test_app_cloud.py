import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

import app_cloud


class DummyPipeline:
    def __init__(self):
        self.cache = {"abc123": {"ready": True}}
        self.processing_tasks = {}
        self.is_llm_configured = True
        self.is_youtube_api_configured = False
        self.answer_question = AsyncMock(return_value="test answer")

    def clear_cache(self, video_id=None):
        if video_id:
            self.cache.pop(video_id, None)
        else:
            self.cache.clear()


class AppCloudTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app_cloud.app)
        self.pipeline = DummyPipeline()
        self.rag_patch = patch.object(app_cloud, "rag_pipeline", self.pipeline)
        self.ensure_patch = patch.object(app_cloud, "ensure_pipeline_initialized", AsyncMock())
        self.rag_patch.start()
        self.ensure_patch.start()

    def tearDown(self):
        self.ensure_patch.stop()
        self.rag_patch.stop()

    def test_health_ready(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["ready"], True)

    def test_config_reports_runtime_flags(self):
        resp = self.client.get("/config")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["llm_configured"], True)
        self.assertEqual(data["cached_videos"], 1)

    def test_status_reports_cache_and_processing(self):
        resp = self.client.get("/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["cached_videos"], 1)
        self.assertEqual(data["processing_videos"], 0)

    def test_ask_returns_answer(self):
        payload = {
            "video_id": "abc123",
            "video_url": "https://www.youtube.com/watch?v=abc123",
            "question": "What is this about?",
        }
        resp = self.client.post("/ask", json=payload)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"answer": "test answer"})
        self.pipeline.answer_question.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
