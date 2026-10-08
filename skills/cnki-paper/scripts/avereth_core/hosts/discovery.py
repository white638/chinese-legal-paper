"""Public-search capability broker for optional Scout discovery.

The primary host registers read-only search callables here. It must not expose
its general tool set to a Scout. Isolated generation adapters are not involved.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import threading
from typing import Any, Callable, Iterator

from ..application.delegation import (REQUEST_SCHEMA, RESULT_SCHEMA, PUBLIC_TOOLS, digest,
                                      normalize_hit, validate_candidate_result)
from .profile import active_host_profile

SearchAdapter = Callable[[str], list[dict[str, str]]]


class PublicDiscoveryBroker:
    """One primary coordinator's finite, non-recursive public search channel."""

    def __init__(self, adapters: dict[str, SearchAdapter]) -> None:
        self._adapters = dict(adapters)
        self._active = 0
        self._lock = threading.Lock()

    @classmethod
    def from_host(cls, adapters: dict[str, SearchAdapter]) -> PublicDiscoveryBroker:
        """Bind the installed host's explicit discovery capability before use."""
        channel = active_host_profile().get("discovery_channel")
        expected = {"mode": "primary_search_broker", "allowed_tools": ["exa.search", "web.search"],
                    "direct_agent_tools": False, "context": "fresh_no_parent_history"}
        if channel != expected:
            raise ValueError("host discovery channel is unavailable or incompatible; return to primary")
        if set(adapters) - PUBLIC_TOOLS or any(not callable(adapter) for adapter in adapters.values()):
            raise ValueError("only approved callable public search adapters may be registered")
        return cls(adapters)

    @contextmanager
    def _slot(self, maximum: int) -> Iterator[None]:
        with self._lock:
            if self._active >= maximum:
                raise ValueError("Scout concurrency budget exhausted; serialize or return to primary")
            self._active += 1
        try:
            yield
        finally:
            with self._lock:
                self._active -= 1

    def discover(self, request: dict[str, Any], *, parent_depth: int = 0) -> dict[str, Any]:
        if parent_depth != 0:
            raise ValueError("recursive delegation is forbidden")
        request = deepcopy(request)
        identifier = request.pop("request_id", None)
        if request.get("schema_version") != REQUEST_SCHEMA or identifier != "scout-" + digest(request):
            raise ValueError("discovery request identity is invalid")
        request["request_id"] = identifier
        task, budget = request["public_task"], request["budget"]
        tool = task["tool"]
        if tool not in PUBLIC_TOOLS or request.get("role") != "avereth_scout" or request["allowed_tools"] != [tool]:
            raise ValueError("invalid Scout tool scope")
        if (type(budget["max_active"]) is not int or not 1 <= budget["max_active"] <= 3
                or type(budget["max_tool_retries"]) is not int or not 0 <= budget["max_tool_retries"] <= 1
                or type(budget["max_candidates"]) is not int or not 1 <= budget["max_candidates"] <= 30
                or not isinstance(task["queries"], list) or not 1 <= len(task["queries"]) <= 8
                or any(not isinstance(query, str) or not query.strip() or len(query) > 500
                       for query in task["queries"])
                or len(set(task["queries"])) != len(task["queries"])
                or type(budget["max_tool_calls"]) is not int
                or budget["max_tool_calls"] != len(task["queries"]) * (1 + budget["max_tool_retries"])):
            raise ValueError("invalid Scout resource budget")
        adapter = self._adapters.get(tool)
        if adapter is None:
            raise ValueError("approved public search adapter unavailable; return to primary")
        result: dict[str, Any] = {"schema_version": RESULT_SCHEMA, "request_id": identifier,
                                 "candidates": [], "search_log": [], "gaps": []}
        seen: set[str] = set()
        with self._slot(budget["max_active"]):
            for query in task["queries"]:
                succeeded = False
                for attempt in range(1, budget["max_tool_retries"] + 2):
                    entry = {"tool": tool, "query": query, "attempt": attempt,
                             "status": "success", "hits": [], "error": ""}
                    try:
                        hits = adapter(query)
                        if not isinstance(hits, list):
                            raise ValueError("search adapter returned non-list data")
                        # Truncate only the candidate capture, never manufacture hits.
                        normalized = [normalize_hit(hit, query) for hit in hits[:budget["max_candidates"]]]
                        for candidate in normalized:
                            entry["hits"].append({key: candidate[key] for key in ("url", "title", "snippet")})
                            if candidate["url"] not in seen and len(result["candidates"]) < budget["max_candidates"]:
                                seen.add(candidate["url"])
                                result["candidates"].append(candidate)
                        succeeded = True
                    except (TimeoutError, ConnectionError) as exc:
                        entry.update(status="temporary_error", hits=[], error=type(exc).__name__)
                    except Exception as exc:
                        entry.update(status="blocked", hits=[], error=type(exc).__name__)
                    result["search_log"].append(entry)
                    if entry["status"] != "temporary_error":
                        break
                if not succeeded:
                    result["gaps"].append(f"Public search not completed for: {query}; primary action required")
        validate_candidate_result(request, result)
        return result
