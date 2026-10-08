"""Read-only metadata clients; results are discovery candidates, never evidence."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
import time
from urllib import error, parse, request

from .common import LegalError

HOSTS = {"api.crossref.org", "api.openalex.org", "api.semanticscholar.org", "api.unpaywall.org",
         "apim-gateway.pkulaw.com"}
MAX_BYTES = 8 * 1024 * 1024


@dataclass
class Response:
    status: int
    headers: dict
    body: bytes


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def http(method, url, headers=None, payload=None):
    target = parse.urlsplit(url)
    if (target.scheme != "https" or target.hostname not in HOSTS or target.username or
            target.password or target.port not in {None, 443} or target.fragment):
        raise LegalError("HTTP.ENDPOINT", "Only documented HTTPS provider hosts are allowed")
    data = None if payload is None else json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
    header = {"User-Agent": "ChineseLegalPaper/1.0 (research metadata client)", **(headers or {})}
    if data is not None:
        header["Content-Type"] = "application/json"
    req = request.Request(url, data=data, headers=header, method=method)
    try:
        with request.build_opener(NoRedirect()).open(req, timeout=20) as res:
            hs = {k.lower(): v for k, v in res.headers.items()}
            if "text/event-stream" in hs.get("content-type", ""):
                # Stop at the matching RPC response; an SSE server may keep its stream open.
                chunks, event, size = [], [], 0
                for line in res:
                    size += len(line)
                    if size > MAX_BYTES:
                        raise LegalError("HTTP.TOO_LARGE", "Provider response exceeded the bounded payload size")
                    chunks.append(line)
                    if line.strip().startswith(b"data:"):
                        event.append(line.strip()[5:].lstrip())
                    if not line.strip() and event:
                        try:
                            msg = json.loads(b"\n".join(event))
                        except ValueError:
                            msg = {}
                        if payload and msg.get("id") == payload.get("id") and ("result" in msg or "error" in msg):
                            break
                        event = []
                body = b"".join(chunks)
            else:
                body = res.read(MAX_BYTES + 1)
                if len(body) > MAX_BYTES:
                    raise LegalError("HTTP.TOO_LARGE", "Provider response exceeded the bounded payload size")
            return Response(res.status, hs, body)
    except error.HTTPError as exc:
        return Response(exc.code, {k.lower(): v for k, v in exc.headers.items()}, b"")
    except (error.URLError, TimeoutError, OSError) as exc:
        # URLs, response bodies and exception strings can contain credentials.
        raise LegalError("HTTP.NETWORK", f"Provider connection failed ({type(exc).__name__})") from None


def checked(response):
    code = response.status
    if 200 <= code < 300:
        return response
    category = {401: "AUTH_REQUIRED", 403: "FORBIDDEN", 404: "NOT_FOUND", 429: "RATE_LIMIT"}.get(code,
               "SERVER_ERROR" if code >= 500 else "HTTP_ERROR")
    raise LegalError(f"HTTP.{category}", f"Provider returned HTTP {code}; this is not a zero-result search")


def json_body(response):
    checked(response)
    try:
        data = json.loads(response.body)
        if not isinstance(data, dict):
            raise ValueError("expected object")
        return data
    except (ValueError, UnicodeError):
        raise LegalError("HTTP.INVALID_JSON", "Provider returned an invalid JSON object") from None


def get_json(url, headers=None, *, transport=http, retries=1):
    for attempt in range(retries + 1):
        res = transport("GET", url, headers or {})
        if res.status not in {429, 500, 502, 503, 504} or attempt == retries:
            return json_body(res)
        delay = res.headers.get("retry-after", "1")
        if not delay.isdigit() or int(delay) > 5:
            checked(res)
        time.sleep(int(delay))
    raise AssertionError("unreachable")


def _doi(value):
    value = str(value or "").strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if value.lower().startswith(prefix):
            value = value[len(prefix):]
    if not value.startswith("10.") or "/" not in value or any(c.isspace() for c in value):
        raise LegalError("DOI.INVALID", "Supply an actual DOI, not a title or guessed identifier")
    return value


def search(provider, query, *, limit=10, cursor=None, env=None, transport=http):
    if not query.strip() or not 1 <= limit <= 100:
        raise LegalError("SEARCH.ARGUMENT", "Query is required and limit must be between 1 and 100")
    env = os.environ if env is None else env
    headers, candidates, next_cursor = {}, [], None
    if provider == "crossref":
        if cursor is not None and (not str(cursor).isdigit() or int(cursor) + limit > 1000):
            raise LegalError("SEARCH.CURSOR", "Crossref search uses offsets within the first 1000 results; narrow the query")
        offset = int(cursor or 0)
        # Deep cursors currently change relevance ordering on the public API.
        # Bounded offsets preserve useful search ranking instead of bulk-harvest order.
        params = {"query.bibliographic": query, "rows": limit}
        if offset:
            params["offset"] = offset
        if env.get("CROSSREF_MAILTO"):
            params["mailto"] = env["CROSSREF_MAILTO"]
        data = get_json("https://api.crossref.org/works?" + parse.urlencode(params), transport=transport)
        message = data.get("message", {})
        if not isinstance(message.get("items"), list):
            raise LegalError("PROVIDER.SHAPE", "Crossref response has no items list")
        consumed = offset + len(message["items"])
        total = message.get("total-results", consumed)
        if len(message["items"]) == limit and consumed < min(total, 1000):
            next_cursor = str(consumed)
        for item in message["items"]:
            candidates.append({"provider_id": item.get("DOI"), "title": (item.get("title") or [None])[0],
                "authors": [" ".join(str(a.get(k) or "") for k in ("given", "family")).strip() for a in item.get("author", [])],
                "year": ((item.get("issued") or {}).get("date-parts") or [[None]])[0][0],
                "doi": item.get("DOI"), "url": item.get("URL"), "abstract": item.get("abstract"),
                "oa_url": None})
    elif provider == "openalex":
        if not env.get("OPENALEX_API_KEY"):
            raise LegalError("AUTH.OPENALEX", "Set OPENALEX_API_KEY; account quota and pricing apply")
        params = {"search": query, "per-page": limit, "cursor": cursor or "*", "api_key": env["OPENALEX_API_KEY"]}
        data = get_json("https://api.openalex.org/works?" + parse.urlencode(params), transport=transport)
        if not isinstance(data.get("results"), list):
            raise LegalError("PROVIDER.SHAPE", "OpenAlex response has no results list")
        next_cursor = (data.get("meta") or {}).get("next_cursor")
        for item in data["results"]:
            doi = item.get("doi")
            candidates.append({"provider_id": item.get("id"), "title": item.get("title"),
                "authors": [(a.get("author") or {}).get("display_name") for a in item.get("authorships", [])],
                "year": item.get("publication_year"), "doi": doi.removeprefix("https://doi.org/") if doi else None,
                "url": (item.get("primary_location") or {}).get("landing_page_url"),
                "abstract": None, "oa_url": (item.get("open_access") or {}).get("oa_url")})
    elif provider == "semantic-scholar":
        if env.get("SEMANTIC_SCHOLAR_API_KEY"):
            headers["x-api-key"] = env["SEMANTIC_SCHOLAR_API_KEY"]
        if cursor is not None and (not str(cursor).isdigit() or int(cursor) < 0):
            raise LegalError("SEARCH.CURSOR", "Semantic Scholar cursor must be a nonnegative offset")
        params = {"query": query, "limit": limit, "offset": cursor or 0,
                  "fields": "paperId,title,authors,year,externalIds,url,abstract,openAccessPdf"}
        data = get_json("https://api.semanticscholar.org/graph/v1/paper/search?" + parse.urlencode(params), headers, transport=transport)
        if not isinstance(data.get("data"), list):
            raise LegalError("PROVIDER.SHAPE", "Semantic Scholar response has no data list")
        next_cursor = data.get("next")
        for item in data["data"]:
            candidates.append({"provider_id": item.get("paperId"), "title": item.get("title"),
                "authors": [a.get("name") for a in item.get("authors", [])], "year": item.get("year"),
                "doi": (item.get("externalIds") or {}).get("DOI"), "url": item.get("url"),
                "abstract": item.get("abstract"), "oa_url": (item.get("openAccessPdf") or {}).get("url")})
    elif provider == "unpaywall":
        email = env.get("UNPAYWALL_EMAIL", "")
        if "@" not in email:
            raise LegalError("AUTH.UNPAYWALL", "Set a valid contact UNPAYWALL_EMAIL")
        doi = _doi(query)
        data = get_json("https://api.unpaywall.org/v2/" + parse.quote(doi, safe="") + "?" + parse.urlencode({"email": email}), transport=transport)
        if data.get("doi", "").lower() != doi.lower():
            raise LegalError("PROVIDER.IDENTITY", "Unpaywall DOI did not match the requested work")
        oa = data.get("best_oa_location") or {}
        candidates = [{"provider_id": data.get("doi"), "title": data.get("title"), "year": data.get("year"),
                       "doi": data.get("doi"), "url": data.get("doi_url"), "authors": [], "abstract": None,
                       "oa_url": oa.get("url_for_pdf") or oa.get("url"), "oa_license": oa.get("license")}]
    else:
        raise LegalError("PROVIDER.UNKNOWN", "Use crossref, openalex, semantic-scholar or unpaywall")
    for candidate in candidates:
        candidate.update(status="candidate", access_level="metadata", fulltext_verified=False)
    return {"schema_version": "legal-discovery/v1", "provider": provider, "query": query,
            "retrieved_at": datetime.now(timezone.utc).isoformat(), "next_cursor": next_cursor,
            "candidates": candidates, "warning": "Metadata and OA links do not establish full-text access or claim support"}
