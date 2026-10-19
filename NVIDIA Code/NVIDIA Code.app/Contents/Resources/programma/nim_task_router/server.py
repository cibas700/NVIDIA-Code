import asyncio
import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from .engine import Engine, log_record
from .policy import ALIASES, GatewayError, Policy, binding_key
from .protocol import encode_sse, event, translate


def error_body(error):
    kind = {400: "invalid_request_error", 401: "authentication_error", 403: "permission_error",
            404: "not_found_error", 413: "request_too_large", 429: "rate_limit_error"}.get(error.status, "api_error")
    return {"type": "error", "error": {"type": kind, "message": error.message}}


def make_handler(config, api_key, token=None, transport=None, log=log_record):
    policy = Policy(config)
    engine = Engine(policy, api_key, transport, log)
    local_token = token or secrets.token_urlsafe(32)
    slots = threading.BoundedSemaphore(4)

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = "NimTaskRouter/0.1"

        def setup(self):
            super().setup()
            self.connection.settimeout(10)

        def log_message(self, *args):
            pass

        def auth(self):
            # The service is local-only; reject browser origins and DNS rebinding.
            if self.headers.get("Origin"):
                raise GatewayError("Accesso browser non supportato", 403)
            if self.headers.get("Host") not in ("127.0.0.1:"+str(self.server.server_port), "localhost:"+str(self.server.server_port)):
                raise GatewayError("Host non valido", 403)
            bearer = self.headers.get("Authorization", "")
            presented = bearer[7:] if bearer.startswith("Bearer ") else self.headers.get("x-api-key", "")
            if not secrets.compare_digest(presented.encode(), local_token.encode()):
                raise GatewayError("Token gateway non valido", 401)

        def json_response(self, status, value, retry_after=0):
            payload = json.dumps(value, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            if retry_after:
                self.send_header("Retry-After", str(retry_after))
            self.end_headers()
            self.wfile.write(payload)
            self.close_connection = True

        def do_HEAD(self):
            self.send_response(200 if urlsplit(self.path).path == "/api/hello" else 404)
            self.send_header("Content-Length", "0")
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True

        def do_GET(self):
            try:
                self.auth()
                path = urlsplit(self.path).path
                if path == "/health":
                    self.json_response(200, {"status": "ok", "upstream_calls": policy.calls,
                                             "max_calls_per_run": config["max_calls_per_run"]})
                elif path == "/v1/models":
                    self.json_response(200, {"data": [{"id": m, "type": "model", "display_name": m,
                        "created_at": "2026-10-18T00:00:00Z"} for m in ALIASES], "has_more": False,
                        "first_id": ALIASES[0], "last_id": ALIASES[-1]})
                else:
                    raise GatewayError("Endpoint non disponibile", 404)
            except GatewayError as e:
                self.json_response(e.status, error_body(e), e.retry_after)

        def do_POST(self):
            acquired = False
            streaming = False
            try:
                self.auth()
                if urlsplit(self.path).path != "/v1/messages":
                    # No fabricated token counts: Claude Code can estimate itself.
                    raise GatewayError("Endpoint non disponibile", 404)
                if self.headers.get("Transfer-Encoding"):
                    raise GatewayError("Invia Content-Length", 411)
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= config["max_request_bytes"]:
                    raise GatewayError("Dimensione richiesta non valida", 413)
                body = json.loads(self.rfile.read(length))
                translated = translate(body)
                hints = {k.lower(): v for k, v in self.headers.items()}
                hint = hints.get("x-claude-code-request-class", "")
                binding = binding_key(body, hints)
                policy.candidates(body, hint, binding)
                acquired = slots.acquire(blocking=False)
                if not acquired:
                    raise GatewayError("Gateway occupato", 429, retry_after=5)
                if body.get("stream"):
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("Connection", "close")
                    self.send_header("X-Accel-Buffering", "no")
                    self.end_headers()
                    self.close_connection = True
                    streaming = True
                    async def relay():
                        stream = engine.generate(body, translated, hint, binding)
                        try:
                            async for item in stream:
                                self.wfile.write(encode_sse(item))
                                self.wfile.flush()
                        finally:
                            await stream.aclose()
                    asyncio.run(relay())
                else:
                    async def collect():
                        message = None
                        blocks = {}
                        async for item in engine.generate(body, translated, hint, binding):
                            kind = item["type"]
                            if kind == "message_start":
                                message = item["message"]
                            elif kind == "content_block_start":
                                blocks[item["index"]] = dict(item["content_block"])
                            elif kind == "content_block_delta":
                                block = blocks[item["index"]]
                                delta = item["delta"]
                                if delta["type"] == "text_delta":
                                    block["text"] += delta["text"]
                                else:
                                    block["input"] = json.loads(delta["partial_json"])
                            elif kind == "message_delta":
                                message.update(item["delta"])
                                message["usage"] = item["usage"]
                        message["content"] = [blocks[i] for i in sorted(blocks)]
                        return message
                    self.json_response(200, asyncio.run(collect()))
            except GatewayError as e:
                log(event="gateway_rejected", status=e.status, message=e.message[:200])
                if streaming:
                    self.wfile.write(encode_sse({"type": "error", "error": error_body(e)["error"]}))
                    self.wfile.flush()
                else:
                    self.json_response(e.status, error_body(e), e.retry_after)
            except (ValueError, KeyError, TypeError, AttributeError):
                error = GatewayError("Payload non valido o formato non supportato", 400)
                if streaming:
                    self.wfile.write(encode_sse({"type": "error", "error": error_body(error)["error"]}))
                else:
                    self.json_response(400, error_body(error))
            except (BrokenPipeError, ConnectionResetError, TimeoutError, OSError):
                # A disconnected client ends generation; never start a fallback.
                pass
            except Exception:
                log(event="internal_error")
                if not streaming:
                    self.json_response(500, error_body(GatewayError("Errore interno gateway", 500)))
            finally:
                if acquired:
                    slots.release()

    Handler.local_token = local_token
    Handler.policy = policy
    return Handler


def make_server(config, api_key, token=None, port=0, transport=None, log=log_record):
    handler = make_handler(config, api_key, token, transport, log)
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    server.daemon_threads = True
    server.local_token = handler.local_token
    server.policy = handler.policy
    return server
