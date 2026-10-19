"""Core Anthropic Messages <-> chat completions translation.

Intentionally limited to text and client-side tools. Reject unsupported payloads
before inference instead of losing images, documents or tool references.
"""
import json
import uuid
from .policy import GatewayError


def text_content(content):
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        raise GatewayError("Contenuto deve essere testo o lista di blocchi")
    parts = []
    for block in content:
        if block.get("type") != "text" or not isinstance(block.get("text"), str):
            raise GatewayError("Questo prototipo accetta solo testo nei risultati degli strumenti")
        parts.append(block["text"])
    return "\n".join(parts)


def translate(body):
    if not isinstance(body, dict) or not isinstance(body.get("messages"), list) or not body["messages"]:
        raise GatewayError("messages deve essere una lista non vuota")
    if type(body.get("max_tokens")) is not int or body["max_tokens"] <= 0:
        raise GatewayError("max_tokens deve essere un intero positivo")
    if "stream" in body and type(body["stream"]) is not bool:
        raise GatewayError("stream deve essere booleano")
    if body.get("output_config", {}).get("format"):
        raise GatewayError("Structured output Anthropic non supportato dal prototipo")
    messages = []
    if body.get("system"):
        messages.append({"role": "system", "content": text_content(body["system"])})
    for msg in body["messages"]:
        role = msg.get("role")
        if role in ("system", "developer"):
            messages.append({"role": "system", "content": text_content(msg.get("content", ""))})
            continue
        if role not in ("user", "assistant"):
            raise GatewayError("Ruolo messaggio non valido")
        content = msg.get("content", "")
        if isinstance(content, str):
            messages.append({"role": role, "content": content})
            continue
        if not isinstance(content, list):
            raise GatewayError("content non valido")
        texts, calls = [], []
        for b in content:
            kind = b.get("type")
            if kind == "text":
                texts.append(b["text"])
            elif kind in ("thinking", "redacted_thinking") and role == "assistant":
                continue  # No portable reasoning-signature format on this upstream.
            elif kind == "tool_use" and role == "assistant":
                if not isinstance(b.get("input"), dict):
                    raise GatewayError("Input tool_use deve essere un oggetto")
                calls.append({"id": b["id"], "type": "function", "function": {
                    "name": b["name"], "arguments": json.dumps(b["input"], ensure_ascii=False)}})
            elif kind == "tool_result" and role == "user":
                # Preserve tool-result ordering ahead of the following user text.
                messages.append({"role": "tool", "tool_call_id": b["tool_use_id"],
                                 "content": text_content(b.get("content", ""))})
            else:
                raise GatewayError("Blocco non supportato: " + str(kind))
        if texts or calls:
            out = {"role": role, "content": "\n".join(texts) if texts else None}
            if calls:
                out["tool_calls"] = calls
            messages.append(out)
    data = {"messages": messages, "max_tokens": body["max_tokens"], "stream": True}
    for src, dest in (("temperature", "temperature"), ("top_p", "top_p"), ("stop_sequences", "stop")):
        if src in body:
            data[dest] = body[src]
    if body.get("tools"):
        tools = []
        for tool in body["tools"]:
            if tool.get("type", "custom") != "custom" or "input_schema" not in tool:
                raise GatewayError("Supportati solo strumenti client con input_schema")
            tools.append({"type": "function", "function": {
                "name": tool["name"], "description": tool.get("description", ""),
                "parameters": tool["input_schema"]}})
        data["tools"] = tools
        choice = body.get("tool_choice", {"type": "auto"})
        kind = choice.get("type")
        if kind == "tool":
            data["tool_choice"] = {"type": "function", "function": {"name": choice["name"]}}
        elif kind in ("auto", "any", "none"):
            data["tool_choice"] = {"auto": "auto", "any": "required", "none": "none"}[kind]
        else:
            raise GatewayError("tool_choice non valido")
        if choice.get("disable_parallel_tool_use"):
            data["parallel_tool_calls"] = False
    return data


def event(kind, **data):
    return {"type": kind, **data}


def encode_sse(item):
    return ("event: " + item["type"] + "\ndata: " + json.dumps(item, ensure_ascii=False) + "\n\n").encode()


class MessageBuilder:
    def __init__(self, alias, tool_names):
        self.message = {"id": "msg_"+uuid.uuid4().hex, "type": "message", "role": "assistant",
                        "model": alias, "content": [], "stop_reason": None, "stop_sequence": None,
                        "usage": {"input_tokens": 0, "output_tokens": 0}}
        self.started = False
        self.text_open = False
        self.text = ""
        self.calls = {}
        self.tool_names = tool_names
        self.usage_known = False
        self.finish_reason = None

    def feed(self, chunk):
        events = []
        if "error" in chunk:
            raise GatewayError("Errore nel flusso NVIDIA", 502, retryable=True)
        if chunk.get("usage"):
            u = chunk["usage"]
            self.message["usage"] = {"input_tokens": u.get("prompt_tokens", 0),
                                     "output_tokens": u.get("completion_tokens", 0)}
            self.usage_known = True
        choices = chunk.get("choices") or []
        if not choices:
            return events
        delta = choices[0].get("delta", {})
        semantic = any(delta.get(k) for k in ("content", "reasoning_content", "reasoning", "tool_calls"))
        if semantic and not self.started:
            self.started = True
            events.append(event("message_start", message=dict(self.message)))
        text = delta.get("content")
        if text:
            if not isinstance(text, str):
                raise GatewayError("Delta testo non valido", 502, retryable=True)
            if not self.text_open:
                self.text_open = True
                events.append(event("content_block_start", index=0, content_block={"type": "text", "text": ""}))
            self.text += text
            events.append(event("content_block_delta", index=0, delta={"type": "text_delta", "text": text}))
        for call in delta.get("tool_calls", []):
            index = call["index"]
            target = self.calls.setdefault(index, {"id": "", "name": "", "arguments": ""})
            if call.get("id"):
                target["id"] = call["id"]
            fn = call.get("function", {})
            if fn.get("name"):
                target["name"] = fn["name"]
            target["arguments"] += fn.get("arguments") or ""
        if choices[0].get("finish_reason"):
            self.finish_reason = choices[0]["finish_reason"]
        return events

    def finish(self):
        if not self.started or not self.finish_reason:
            raise GatewayError("Risposta NVIDIA vuota o interrotta", 502, retryable=True)
        if self.finish_reason not in ("stop", "length", "tool_calls", "function_call"):
            raise GatewayError("Risposta bloccata o finish_reason non supportato", 502)
        events = []
        if self.text_open:
            self.message["content"].append({"type": "text", "text": self.text})
            events.append(event("content_block_stop", index=0))
        for i in sorted(self.calls):
            call = self.calls[i]
            if not call["id"] or call["name"] not in self.tool_names:
                raise GatewayError("Strumento NVIDIA sconosciuto o ID mancante", 502)
            try:
                args = json.loads(call["arguments"] or "{}")
            except ValueError:
                raise GatewayError("Argomenti strumento incompleti: nessuna riesecuzione automatica", 502)
            if not isinstance(args, dict):
                raise GatewayError("Argomenti strumento non validi", 502)
            index = len(self.message["content"])
            block = {"type": "tool_use", "id": call["id"], "name": call["name"], "input": args}
            self.message["content"].append(block)
            events.extend([
                event("content_block_start", index=index, content_block={**block, "input": {}}),
                event("content_block_delta", index=index, delta={"type": "input_json_delta", "partial_json": json.dumps(args)}),
                event("content_block_stop", index=index)])
        if self.finish_reason in ("tool_calls", "function_call") and not self.calls:
            raise GatewayError("finish_reason tool_calls senza strumenti", 502)
        if not self.message["content"]:
            raise GatewayError("Il modello ha prodotto solo ragionamento senza risposta", 502)
        reason = "max_tokens" if self.finish_reason == "length" else ("tool_use" if self.calls else "end_turn")
        self.message["stop_reason"] = reason
        events.extend([event("message_delta", delta={"stop_reason": reason, "stop_sequence": None},
                             usage=self.message["usage"]), event("message_stop")])
        return events
