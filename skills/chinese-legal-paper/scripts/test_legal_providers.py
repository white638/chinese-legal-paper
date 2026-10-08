import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from legal_core.common import LegalError, digest, read_json
from legal_core.pkulaw import Client, rpc_body, reservation
from legal_core.providers import Response, checked, get_json, http, search


def response(value, status=200, headers=None):
    return Response(status, headers or {"content-type":"application/json"}, json.dumps(value).encode())


class FakeMCP:
    def __init__(self, *, sse=False, pages=False, fail_call=None):
        self.requests = []
        self.sse, self.pages, self.fail_call = sse, pages, fail_call
        self.tool = {"name":"observed_read_tool", "description":"Synthetic read-only search",
                     "inputSchema":{"type":"object","properties":{"query":{"type":"string","minLength":1}},"required":["query"],"additionalProperties":False},
                     "annotations":{"readOnlyHint":True,"destructiveHint":False}}

    def __call__(self, method, url, headers, payload=None):
        self.requests.append((method, url, dict(headers), payload))
        operation = payload["method"]
        if operation == "notifications/initialized":
            return Response(202, {}, b"")
        if operation == "initialize":
            return response({"jsonrpc":"2.0","id":payload["id"],"result":{"protocolVersion":"2025-06-18","capabilities":{"tools":{}}}},
                            headers={"content-type":"application/json","mcp-session-id":"test-session"})
        if operation == "tools/list":
            result = {"tools":[]} if payload.get("params",{}).get("cursor") else {"tools":[self.tool]}
            if self.pages and not payload.get("params",{}).get("cursor"):
                result["nextCursor"] = "page2"
        elif operation == "tools/call":
            if self.fail_call:
                return Response(self.fail_call, {}, b"")
            result = {"content":[{"type":"text","text":"Synthetic legal result, not a real law"}]}
        else:
            raise AssertionError(operation)
        body = {"jsonrpc":"2.0","id":payload["id"],"result":result}
        if self.sse:
            raw = ': heartbeat\n\ndata: {"jsonrpc":"2.0","method":"notifications/message"}\n\ndata: ' + json.dumps(body) + '\n\n'
            return Response(200, {"content-type":"text/event-stream"}, raw.encode())
        return response(body)


class ProviderTests(unittest.TestCase):
    def test_crossref_candidates_and_cursor(self):
        data = {"message":{"items":[{"DOI":"10.1234/test","title":["A real returned title"],"author":[{"given":"A","family":"B"}],"issued":{"date-parts":[[2020]]},"URL":"https://doi.org/10.1234/test"}],"total-results":20}}
        calls = []
        def transport(*args):
            calls.append(args)
            return response(data)
        result = search("crossref", "law", limit=1, transport=transport, env={})
        self.assertEqual("candidate", result["candidates"][0]["status"])
        self.assertFalse(result["candidates"][0]["fulltext_verified"])
        self.assertEqual("1", result["next_cursor"])
        self.assertIn("query.bibliographic=law", calls[0][1])
        self.assertNotIn("cursor=", calls[0][1])
        self.assertNotIn("offset=", calls[0][1])

    def test_zero_results_distinct_from_error(self):
        result = search("crossref", "no matches", transport=lambda *a: response({"message":{"items":[]}}), env={})
        self.assertEqual([], result["candidates"])
        for status, code in ((401,"AUTH_REQUIRED"),(403,"FORBIDDEN"),(429,"RATE_LIMIT"),(503,"SERVER_ERROR")):
            with self.subTest(status=status), self.assertRaises(LegalError) as raised:
                checked(Response(status, {}, b""))
            self.assertEqual("HTTP."+code, raised.exception.code)

    def test_html_login_is_not_empty_results(self):
        with self.assertRaises(LegalError) as raised:
            search("crossref", "law", transport=lambda *a: Response(200,{},b"<html>login</html>"), env={})
        self.assertEqual("HTTP.INVALID_JSON", raised.exception.code)

    def test_invalid_response_shape_is_not_empty_results(self):
        with self.assertRaises(LegalError):
            search("semantic-scholar", "law", transport=lambda *a: response({"error":"unexpected"}), env={})

    def test_openalex_requires_key_and_does_not_echo_it(self):
        with self.assertRaises(LegalError):
            search("openalex", "law", env={})
        def transport(method, url, headers):
            self.assertIn("api_key=secret-key", url)
            return response({"results":[{"id":"https://openalex.org/W1","title":"Law","doi":"https://doi.org/10.1234/test","authorships":[],"publication_year":2024,"open_access":{"oa_url":"https://example.org/paper"}}],"meta":{"next_cursor":None}})
        result = search("openalex", "law", env={"OPENALEX_API_KEY":"secret-key"}, transport=transport)
        self.assertNotIn("secret-key", json.dumps(result))
        self.assertEqual("metadata", result["candidates"][0]["access_level"])

    def test_semantic_scholar_headers_offset_and_oa(self):
        def transport(method,url,headers):
            self.assertEqual(headers["x-api-key"], "secret")
            self.assertIn("offset=10",url)
            return response({"data":[{"paperId":"id","title":"Law","authors":[{"name":"Author"}],"externalIds":{"DOI":"10.1234/test"},"openAccessPdf":{"url":"https://example.org/paper.pdf"}}],"next":20})
        result=search("semantic-scholar","law",cursor="10",env={"SEMANTIC_SCHOLAR_API_KEY":"secret"},transport=transport)
        self.assertEqual(20,result["next_cursor"])
        self.assertFalse(result["candidates"][0]["fulltext_verified"])

    def test_unpaywall_needs_real_doi_contact_and_matching_identity(self):
        with self.assertRaises(LegalError):
            search("unpaywall","article title",env={"UNPAYWALL_EMAIL":"test@example.org"})
        with self.assertRaises(LegalError):
            search("unpaywall","10.1234/test",env={})
        result=search("unpaywall","10.1234/test",env={"UNPAYWALL_EMAIL":"test@example.org"},
                      transport=lambda *a:response({"doi":"10.1234/test","best_oa_location":{"url_for_pdf":"https://example.org/file","license":"cc-by"}}))
        self.assertEqual("cc-by",result["candidates"][0]["oa_license"])
        with self.assertRaises(LegalError):
            search("unpaywall","10.1234/test",env={"UNPAYWALL_EMAIL":"test@example.org"},transport=lambda *a:response({"doi":"10.9999/wrong"}))

    def test_bounded_metadata_retry(self):
        responses=iter([Response(429,{"retry-after":"0"},b""),response({"ok":True})])
        self.assertEqual({"ok":True},get_json("https://api.crossref.org/works",transport=lambda *a:next(responses)))
        with self.assertRaises(LegalError):
            get_json("https://api.crossref.org/works",transport=lambda *a:Response(429,{"retry-after":"100"},b""))

    def test_endpoint_allowlist_prevents_credential_redirection(self):
        for url in ("http://api.crossref.org/works","https://evil.example/","https://api.crossref.org.evil.example/","https://user:pass@api.crossref.org/","https://api.crossref.org:444/works"):
            with self.subTest(url=url), self.assertRaises(LegalError):
                http("GET",url,{"Authorization":"Bearer secret"})


class MCPTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.ledger=Path(self.tmp.name)/"budget.json"

    def client(self, **kwargs):
        fake=FakeMCP(**kwargs)
        client=Client("law-keyword",env={"PKULAW_MCP_TOKEN":"secret"},transport=fake)
        discovered=client.discover()
        return client,fake,discovered

    def call(self,client,discovered,**kwargs):
        args={"schema_digest":discovered["schema_digest"],"allow_tools":["observed_read_tool"],"ledger":self.ledger,"unit_cost":"0.10","budget":"1.00","max_calls":3}
        args.update(kwargs)
        return client.call("observed_read_tool",{"query":"law"},**args)

    def test_initialize_session_headers_json_and_pagination(self):
        client,fake,discovered=self.client(pages=True)
        self.assertEqual(4,len(fake.requests))
        for req in fake.requests[1:]:
            self.assertEqual("test-session",req[2]["Mcp-Session-Id"])
            self.assertEqual("2025-06-18",req[2]["MCP-Protocol-Version"])
        self.assertEqual("candidate",self.call(client,discovered)["status"])
        self.assertNotIn("secret",self.ledger.read_text())

    def test_sse_protocol_response(self):
        client,fake,discovered=self.client(sse=True)
        self.assertEqual("observed_read_tool",discovered["tools"][0]["name"])
        self.call(client,discovered)

    def test_authentication_missing_does_not_attempt_connection(self):
        fake=mock.Mock()
        with self.assertRaises(LegalError):
            Client("law-keyword",env={},transport=fake)
        fake.assert_not_called()

    def test_unknown_tool_not_guessed(self):
        client,fake,discovered=self.client()
        with self.assertRaises(LegalError):
            client.call("guessed_tool",{},schema_digest=discovered["schema_digest"],allow_tools=["guessed_tool"],ledger=self.ledger,unit_cost="1",budget="1",max_calls=1)
        self.assertFalse(self.ledger.exists())

    def test_changed_schema_requires_review(self):
        client,fake,discovered=self.client()
        client.tools["observed_read_tool"]["inputSchema"]["required"].append("extra")
        with self.assertRaises(LegalError) as raised:
            self.call(client,discovered)
        self.assertEqual("MCP.SCHEMA_CHANGED",raised.exception.code)

    def test_parameters_validated_before_billing(self):
        client,fake,discovered=self.client()
        with self.assertRaises(LegalError):
            client.call("observed_read_tool",{"query":12},schema_digest=discovered["schema_digest"],allow_tools=["observed_read_tool"],ledger=self.ledger,unit_cost="1",budget="1",max_calls=1)
        self.assertFalse(self.ledger.exists())

    def test_explicit_allowlist_and_mutation_guard(self):
        client,fake,discovered=self.client()
        with self.assertRaises(LegalError):
            self.call(client,discovered,allow_tools=[])
        client.tools["observed_read_tool"]["annotations"]["destructiveHint"]=True
        discovered["schema_digest"]=digest(client.tools)
        with self.assertRaises(LegalError) as raised:
            self.call(client,discovered)
        self.assertEqual("MCP.MUTATION",raised.exception.code)

    def test_error_reserves_attempt_and_does_not_retry(self):
        client,fake,discovered=self.client(fail_call=503)
        with self.assertRaises(LegalError):
            self.call(client,discovered)
        calls=[r for r in fake.requests if r[3]["method"]=="tools/call"]
        self.assertEqual(1,len(calls))
        self.assertEqual("failed_or_unknown",read_json(self.ledger)["attempts"][0]["status"])
        with self.assertRaises(LegalError) as raised:
            self.call(client,discovered,max_calls=1)
        self.assertEqual("BUDGET.EXHAUSTED",raised.exception.code)

    def test_expired_session_does_not_replay_paid_call(self):
        client,fake,discovered=self.client(fail_call=404)
        with self.assertRaises(LegalError) as raised:
            self.call(client,discovered)
        self.assertEqual("MCP.SESSION_EXPIRED",raised.exception.code)
        self.assertFalse(client.initialized)

    def test_decimal_budget_and_concurrent_lock(self):
        for _ in range(3):
            with reservation(self.ledger,"law-keyword","t",{},"0.1","0.3",5):
                with self.assertRaises(LegalError):
                    with reservation(self.ledger,"law-keyword","t",{},"0.1","0.3",5):
                        pass
        with self.assertRaises(LegalError):
            with reservation(self.ledger,"law-keyword","t",{},"0.1","0.3",5):
                pass

    def test_nonfinite_and_zero_cost_rejected(self):
        for amount in ("NaN","Infinity","-1","0"):
            with self.subTest(amount=amount),self.assertRaises(LegalError):
                with reservation(self.ledger,"law-keyword","t",{},amount,"1",3):
                    pass

    def test_mismatched_rpc_response_rejected(self):
        with self.assertRaises(LegalError):
            rpc_body(response({"jsonrpc":"2.0","id":99,"result":{}}),1)


if __name__=="__main__":
    unittest.main()
