import asyncio
import contextlib
import json
import sys
import time
import httpx
from .policy import GatewayError
from .protocol import MessageBuilder, event

API_BASE = "https://integrate.api.nvidia.com/v1"


def log_record(**fields):
    # Only metadata; never exception bodies, prompts, tool arguments, or keys.
    print(json.dumps(fields, ensure_ascii=False), file=sys.stderr, flush=True)


class Engine:
    def __init__(self, policy, api_key, transport=None, log=log_record):
        self.policy, self.api_key = policy, api_key
        self.transport, self.log = transport, log

    async def generate(self, body, translated, request_class="", binding=""):
        candidates, reason = self.policy.candidates(body, request_class, binding)
        total_start = time.monotonic()
        total_limit = self.policy.config["total_seconds"]
        for attempt, model in enumerate(candidates, 1):
            builder = MessageBuilder(body.get("model", "route-auto"),
                                     {t["function"]["name"] for t in translated.get("tools", [])})
            started_at = time.monotonic()
            response = None
            pending = None
            try:
                self.policy.reserve()
                self.log(event="attempt", model=model["id"], attempt=attempt, reason=reason,
                         calls=self.policy.calls)
                yield event("ping")
                first_limit = self.policy.config["first_token_seconds"][model["tier"]]
                timeout = httpx.Timeout(connect=10, read=None, write=30, pool=10)
                async with httpx.AsyncClient(timeout=timeout, trust_env=False,
                                             transport=self.transport) as client:
                    request = client.build_request("POST", API_BASE+"/chat/completions",
                        headers={"Authorization": "Bearer "+self.api_key, "Accept": "text/event-stream"},
                        json={**translated, **model["extra_body"], "model": model["id"]})
                    # Connection/headers and first semantic output share a deadline.
                    pending = asyncio.create_task(client.send(request, stream=True))
                    while not pending.done():
                        remaining = min(first_limit-(time.monotonic()-started_at),
                                        total_limit-(time.monotonic()-total_start))
                        if remaining <= 0:
                            raise GatewayError("Timeout prima del primo token", 504, retryable=True)
                        await asyncio.wait({pending}, timeout=min(5, remaining))
                        if not pending.done():
                            yield event("ping")
                    response = pending.result()
                    pending = None
                    if response.status_code >= 400:
                        status = response.status_code
                        delay = response.headers.get("retry-after", "90")
                        try:
                            delay = max(1, int(delay))
                        except ValueError:
                            delay = 90
                        raise GatewayError("NVIDIA ha restituito HTTP "+str(status), status,
                                           retryable=(status in (408, 500, 502, 503, 504)),
                                           retry_after=delay if status == 429 else 0)
                    if "text/event-stream" not in response.headers.get("content-type", ""):
                        raise GatewayError("NVIDIA non ha restituito uno stream SSE", 502, retryable=True)
                    lines = response.aiter_lines().__aiter__()
                    last_semantic = time.monotonic()
                    size = 0
                    while True:
                        if pending is None:
                            pending = asyncio.create_task(lines.__anext__())
                        now = time.monotonic()
                        remaining = min(total_limit-(now-total_start),
                            (self.policy.config["idle_seconds"]-(now-last_semantic)) if builder.started
                            else first_limit-(now-started_at))
                        if remaining <= 0:
                            raise GatewayError("Timeout del flusso NVIDIA", 504, retryable=True)
                        await asyncio.wait({pending}, timeout=min(5, remaining))
                        if not pending.done():
                            yield event("ping")
                            continue
                        try:
                            line = pending.result()
                        except StopAsyncIteration:
                            pending = None
                            break
                        pending = None
                        size += len(line.encode())
                        if size > self.policy.config["max_response_bytes"]:
                            raise GatewayError("Risposta oltre il limite locale", 502)
                        if not line.startswith("data:"):
                            continue
                        raw = line[5:].strip()
                        if raw == "[DONE]":
                            break
                        try:
                            chunk = json.loads(raw)
                        except ValueError:
                            raise GatewayError("JSON SSE NVIDIA non valido", 502, retryable=True)
                        choices = chunk.get("choices") or []
                        delta = choices[0].get("delta", {}) if choices else {}
                        if any(delta.get(k) for k in ("content", "reasoning_content", "reasoning", "tool_calls")):
                            last_semantic = time.monotonic()
                        for item in builder.feed(chunk):
                            yield item
                    for item in builder.finish():
                        yield item
                    self.policy.bind(binding, model["id"])
                    self.log(event="success", model=model["id"], attempt=attempt,
                             seconds=round(time.monotonic()-started_at, 3),
                             usage=builder.message["usage"] if builder.usage_known else None)
                    return
            except (httpx.HTTPError, asyncio.TimeoutError):
                error = GatewayError("Connessione NVIDIA interrotta", 504, retryable=True)
            except GatewayError as caught:
                error = caught
            finally:
                if pending is not None:
                    if not pending.done():
                        pending.cancel()
                    with contextlib.suppress(asyncio.CancelledError, Exception):
                        result = await pending
                        if isinstance(result, httpx.Response):
                            await result.aclose()
                if response is not None:
                    await response.aclose()
            self.policy.failed(model["id"], error)
            self.log(event="failure", model=model["id"], attempt=attempt, status=error.status,
                     output_started=builder.started, usage_unknown=True)
            if builder.started or not error.retryable or attempt == len(candidates) or time.monotonic()-total_start >= total_limit:
                raise error
            # The failed HTTP stream is closed before the next candidate starts.
            # Closing it cannot guarantee cancellation/accounting at NVIDIA.
