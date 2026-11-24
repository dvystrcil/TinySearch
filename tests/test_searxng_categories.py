"""search_categories: name SearXNG categories alongside engines.

SearXNG treats `engines=` as the whole engine list, so a caller that wants one
extra engine (e.g. a paid, opt-in one) on top of the instance's defaults has
to restate every default. Sending `categories=general` with `engines=` adds
the category's enabled engines instead (searx/webadapter.py), so the instance
stays the one place that picks the free engines.
"""
from __future__ import annotations

import json
import unittest
from typing import Any
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from tinysearch.config import DEFAULT_CONFIG, normalize_config
from tinysearch.services import web_search_service
from tinysearch.services.web_search_service import (
    _backend_attempt_plan,
    _dispatch_search,
    _searxng_search,
)
from tests.test_web_search_service import _FakeUrlopenResponse


def _capture_urlopen(seen: list[dict[str, list[str]]]):
    body = json.dumps({"results": [{"title": "t", "url": "https://example.com/", "content": "c"}]}).encode()

    def fake(req: Any, timeout: Any = None) -> _FakeUrlopenResponse:
        seen.append(parse_qs(urlsplit(req.full_url).query))
        return _FakeUrlopenResponse(body)

    return fake


class SearxngCategoriesParamTests(unittest.TestCase):
    def _params(self, **kwargs: Any) -> dict[str, list[str]]:
        seen: list[dict[str, list[str]]] = []
        with patch.object(web_search_service, "urlopen", new=_capture_urlopen(seen)):
            _searxng_search("q", 5, url="http://searxng:8080/search", **kwargs)
        return seen[0]

    def test_categories_sent_with_engines(self) -> None:
        params = self._params(engines=["braveapi"], categories=["general"])
        self.assertEqual(params["engines"], ["braveapi"])
        self.assertEqual(params["categories"], ["general"])

    def test_several_categories_are_comma_joined(self) -> None:
        params = self._params(categories="general, it")
        self.assertEqual(params["categories"], ["general,it"])

    def test_no_categories_param_by_default(self) -> None:
        self.assertNotIn("categories", self._params(engines=["yahoo"]))


class SearchCategoriesConfigTests(unittest.TestCase):
    def test_default_is_empty_list(self) -> None:
        self.assertEqual(DEFAULT_CONFIG["search_categories"], [])
        self.assertEqual(normalize_config({})["search_categories"], [])

    def test_comma_string_is_normalized_to_list(self) -> None:
        config = normalize_config({"search_categories": "general , it"})
        self.assertEqual(config["search_categories"], ["general", "it"])

    def test_list_is_trimmed(self) -> None:
        config = normalize_config({"search_categories": [" general ", ""]})
        self.assertEqual(config["search_categories"], ["general"])

    def test_other_types_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            normalize_config({"search_categories": 3})


class SearchCategoriesReachSearxngTests(unittest.TestCase):
    CONFIG = {
        "search_backend": "searxng",
        "search_backend_url": "http://searxng:8080/search",
        "search_engines": ["braveapi"],
        "search_categories": ["general"],
        "search_region": "",
        "search_backend_fallback": False,
    }

    def test_batch_search_plan_sends_categories(self) -> None:
        """The MCP `search` tool path (search_batch_with_metadata)."""
        seen: list[dict[str, list[str]]] = []
        with patch.object(web_search_service, "urlopen", new=_capture_urlopen(seen)):
            name, attempt = _backend_attempt_plan(dict(self.CONFIG), "q", 5)[0]
            attempt()
        self.assertEqual(name, "searxng")
        self.assertEqual(seen[0]["categories"], ["general"])
        self.assertEqual(seen[0]["engines"], ["braveapi"])

    def test_dispatcher_sends_categories(self) -> None:
        seen: list[dict[str, list[str]]] = []
        with patch.object(web_search_service, "urlopen", new=_capture_urlopen(seen)):
            _dispatch_search("q", 5, config=dict(self.CONFIG))
        self.assertEqual(seen[0]["categories"], ["general"])


if __name__ == "__main__":
    unittest.main()
