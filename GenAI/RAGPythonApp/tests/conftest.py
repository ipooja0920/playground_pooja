"""
Shared pytest configuration.

- Adds the RAGPythonApp root to sys.path so tests can import app modules directly.
- Sets a dummy OPENAI_API_KEY so llm_client.py can be imported without a real key
  (all actual API calls are mocked in the tests themselves).
"""
import os
import sys

# Ensure the parent directory (RAGPythonApp/) is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Provide a dummy key so llm_client._client can be instantiated at import time.
# Tests mock _client directly, so no real API calls are made.
os.environ.setdefault("OPENAI_API_KEY", "sk-test-dummy-key-for-unit-tests")
