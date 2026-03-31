import os
import unittest
from unittest.mock import patch

from rag_pipeline_cloud import RAGPipeline


class RagPipelineCloudTests(unittest.TestCase):
    @patch.dict(
        os.environ,
        {
            "LLM_PROVIDER": "openrouter",
            "OPENROUTER_API_KEY": "test-key",
            "HTTP_PROXY": "http://127.0.0.1:9",
            "HTTPS_PROXY": "http://127.0.0.1:9",
        },
        clear=False,
    )
    def test_ambient_proxy_env_is_ignored_by_default(self):
        pipeline = RAGPipeline()
        self.assertFalse(pipeline.http.trust_env)
        self.assertIsNone(pipeline._configured_proxies())

    @patch.dict(
        os.environ,
        {
            "LLM_PROVIDER": "openrouter",
            "OPENROUTER_API_KEY": "test-key",
            "YT_TRANSCRIPT_PROXY_HTTP": "http://proxy.example:8080",
            "YT_TRANSCRIPT_PROXY_HTTPS": "http://proxy.example:8080",
        },
        clear=False,
    )
    def test_explicit_transcript_proxy_env_is_used(self):
        pipeline = RAGPipeline()
        proxies = pipeline._configured_proxies()
        self.assertEqual(
            proxies,
            {
                "http": "http://proxy.example:8080",
                "https": "http://proxy.example:8080",
            },
        )


if __name__ == "__main__":
    unittest.main()
