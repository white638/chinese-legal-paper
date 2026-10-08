"""Official-gateway Streamable HTTP MCP client with explicit call reservations."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from .common import LegalError, atomic_json, digest, read_json, schema_errors
from .providers import checked, http, json_body

ENDPOINTS = {"law-keyword": "/mcp-law", "law-semantic": "/mcp-law-search-service",
             "case-keyword": "/mcp-case", "case-semantic": "/mcp-case-search-service",
             "article-keyword": "/mcp-fatiao", "law-recognition": "/law_recognition",
             "case-recognition": "/case_number_recognition", "citation-validator": "/pku_citation_validator",
             "document-link": "/add-doc-link"}
PROTOCOLS = {"2025-06-18", "2025-03-26"}


def rpc_body(response, request_id):
    checked(response)
    if "text/event-stream" in response.headers.get("content-type", ""):
        messages, data = [], []
        for line in response.body.decode("utf-8").replace("\r\n", "\n").split("\n") + [""]:
            if line.startswith("data:"):
                data.append(line[5:].lstrip())
            elif not line and data:
                try:
                    messages.append(json.loads("\n".join(data)))
                except ValueError:
                    raise LegalError("MCP.INVALID_SSE", "SSE event contains invalid JSON") from None
                data = []
        matches = [m for m in messages if isinstance(m, dict) and m.get("id") == request_id and ("result" in m or "error" in m)]
        if len(matches) != 1:
            raise LegalError("MCP.RESPONSE_ID", "Expected exactly one matching JSON-RPC response")
        result = matches[0]
    else:
        result = json_body(response)
    if result.get("jsonrpc") != "2.0" or type(result.get("id")) is not int or result.get("id") != request_id:
        raise LegalError("MCP.RESPONSE_ID", "Mismatched JSON-RPC response")
    if "error" in result:
        raise LegalError("MCP.RPC_ERROR", "MCP returned an error; inspect the provider account, not a zero-result search")
    if not isinstance(result.get("result"), dict):
        raise LegalError("MCP.RESULT", "MCP result must be an object")
    return result["result"]


class Client:
    def __init__(self, endpoint, *, env=None, transport=http):
        if endpoint not in ENDPOINTS:
            raise LegalError("MCP.ENDPOINT", "Choose a documented official PKULaw endpoint alias")
        env = os.environ if env is None else env
        token = env.get("PKULAW_MCP_TOKEN", "").strip()
        if not token or "\n" in token or "\r" in token:
            raise LegalError("AUTH.PKULAW", "Set PKULAW_MCP_TOKEN to the bare account token")
        self.endpoint = endpoint
        self.url = "https://apim-gateway.pkulaw.com" + ENDPOINTS[endpoint]
        self.transport, self.request_id = transport, 0
        self.headers = {"Authorization": "Bearer " + token, "Accept": "application/json, text/event-stream"}
        self.tools, self.initialized = {}, False

    def rpc(self, method, params=None):
        self.request_id += 1
        response = self.transport("POST", self.url, self.headers, {
            "jsonrpc": "2.0", "id": self.request_id, "method": method, "params": params or {}})
        if response.status == 404 and self.initialized:
            # No automatic replay of a possibly billed call. A fresh client must discover again.
            self.tools, self.initialized = {}, False
            self.headers.pop("Mcp-Session-Id", None)
            raise LegalError("MCP.SESSION_EXPIRED", "Session expired; initialize/discover a fresh session before a new explicit call")
        result = rpc_body(response, self.request_id)
        if method == "initialize":
            protocol = result.get("protocolVersion")
            if protocol not in PROTOCOLS:
                raise LegalError("MCP.PROTOCOL", "Server selected an unsupported MCP protocol version")
            self.headers["MCP-Protocol-Version"] = protocol
            session = response.headers.get("mcp-session-id")
            if session:
                if not all(0x21 <= ord(c) <= 0x7E for c in session):
                    raise LegalError("MCP.SESSION", "Invalid session header")
                self.headers["Mcp-Session-Id"] = session
        return result

    def discover(self):
        self.rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                               "clientInfo": {"name": "chinese-legal-paper", "version": "1.0.0"}})
        response = self.transport("POST", self.url, self.headers,
                                  {"jsonrpc": "2.0", "method": "notifications/initialized"})
        checked(response)
        if response.status != 202:
            raise LegalError("MCP.NOTIFICATION", "Expected HTTP 202 for initialization notification")
        self.initialized = True
        cursor, cursors, self.tools = None, set(), {}
        for _ in range(50):
            result = self.rpc("tools/list", {"cursor": cursor} if cursor else {})
            if not isinstance(result.get("tools"), list):
                raise LegalError("MCP.TOOLS", "Invalid tool discovery response")
            for tool in result["tools"]:
                if not isinstance(tool, dict) or not isinstance(tool.get("name"), str) or not isinstance(tool.get("inputSchema"), dict):
                    raise LegalError("MCP.TOOL_SCHEMA", "Tool needs an observed name and inputSchema")
                if tool["name"] in self.tools:
                    raise LegalError("MCP.DUPLICATE_TOOL", "Duplicate tool names in discovery")
                self.tools[tool["name"]] = tool
            cursor = result.get("nextCursor")
            if not cursor:
                return {"endpoint": self.endpoint, "protocol": self.headers["MCP-Protocol-Version"],
                        "tools": list(self.tools.values()), "schema_digest": digest(self.tools)}
            if not isinstance(cursor, str) or cursor in cursors:
                raise LegalError("MCP.CURSOR", "Invalid or repeating tool pagination cursor")
            cursors.add(cursor)
        raise LegalError("MCP.TOOL_LIMIT", "Tool pagination exceeded its safety bound")

    def call(self, name, arguments, *, schema_digest, allow_tools, ledger, unit_cost, budget, max_calls):
        if not self.initialized or name not in self.tools:
            raise LegalError("MCP.NOT_DISCOVERED", "Discover the tool in this session before calling it")
        if schema_digest != digest(self.tools):
            raise LegalError("MCP.SCHEMA_CHANGED", "Discovery schema changed; review the current tool contract")
        if name not in allow_tools:
            raise LegalError("MCP.TOOL_NOT_ALLOWED", "Explicitly authorize this discovered read-only tool")
        annotations = self.tools[name].get("annotations") or {}
        if annotations.get("destructiveHint") is True or annotations.get("readOnlyHint") is False:
            raise LegalError("MCP.MUTATION", "This academic client does not call tools marked as mutating")
        errors = schema_errors(arguments, self.tools[name]["inputSchema"])
        if errors:
            raise LegalError("MCP.ARGUMENT_SCHEMA", "; ".join(errors))
        with reservation(ledger, self.endpoint, name, arguments, unit_cost, budget, max_calls):
            result = self.rpc("tools/call", {"name": name, "arguments": arguments})
            if result.get("isError"):
                raise LegalError("MCP.TOOL_ERROR", "The tool reported an error; the reserved attempt remains counted")
            return {"status": "candidate", "endpoint": self.endpoint, "tool": name, "result": result,
                    "warning": "Retrieved material still needs identity, version, text-access and claim-support checks"}


def money(value):
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number <= 0:
            raise ValueError()
        return number
    except (InvalidOperation, ValueError):
        raise LegalError("BUDGET.INVALID", "Cost and budget must be finite positive decimal amounts") from None


@contextmanager
def reservation(path, endpoint, tool, arguments, unit_cost, budget, max_calls):
    unit, ceiling = money(unit_cost), money(budget)
    if type(max_calls) is not int or max_calls < 1:
        raise LegalError("BUDGET.INVALID", "max_calls must be a positive integer")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_suffix(path.suffix + ".lock")
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise LegalError("BUDGET.LOCKED", "Budget ledger is in use; inspect interrupted runs before manual recovery") from None
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(json.dumps({"pid": os.getpid(), "at": datetime.now(timezone.utc).isoformat()}))
        ledger = read_json(path) if path.exists() else {"schema_version": "legal-call-budget/v1", "attempts": []}
        if ledger.get("schema_version") != "legal-call-budget/v1" or not isinstance(ledger.get("attempts"), list):
            raise LegalError("BUDGET.CORRUPT", "Invalid budget ledger; do not reset it automatically")
        attempts = ledger["attempts"]
        reserved = sum((money(a["reserved_cost"]) for a in attempts), Decimal("0"))
        if len(attempts) >= max_calls or reserved + unit > ceiling:
            raise LegalError("BUDGET.EXHAUSTED", "Configured call or estimated cost ceiling reached")
        attempt = {"endpoint": endpoint, "tool": tool, "arguments_digest": digest(arguments),
                   "at": datetime.now(timezone.utc).isoformat(), "reserved_cost": str(unit), "status": "reserved"}
        attempts.append(attempt)
        atomic_json(path, ledger)
        try:
            yield
        except BaseException:
            attempt["status"] = "failed_or_unknown"
            atomic_json(path, ledger)
            raise
        else:
            attempt["status"] = "returned"
            atomic_json(path, ledger)
    finally:
        lock.unlink(missing_ok=True)
