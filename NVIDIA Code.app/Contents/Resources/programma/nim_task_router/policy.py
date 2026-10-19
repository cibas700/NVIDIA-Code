"""Offline routing: no classifier model and no speculative parallel calls."""
import json
import hashlib
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path

TIERS = ("fast", "balanced", "deep")
ALIASES = ("route-auto", "route-fast", "route-balanced", "route-deep")


@dataclass
class GatewayError(Exception):
    message: str
    status: int = 400
    retryable: bool = False
    retry_after: int = 0

    def __str__(self):
        return self.message


def default_config():
    catalog = json.loads(Path(__file__).with_name("catalog.json").read_text())
    return {
        "api_key_file": "nvidia-api-key.txt",
        "client_context_tokens": 65536,
        "models": [dict(m, enabled=True, max_input_bytes=180000,
                        max_output_tokens=8192, extra_body={}) for m in catalog["models"]],
        "first_token_seconds": {"fast": 45, "balanced": 75, "deep": 120},
        "idle_seconds": 60,
        "total_seconds": 240,
        "max_attempts": 2,
        "max_calls_per_run": 100,
        "rpm": 10,
        "cooldown_seconds": 90,
        "max_request_bytes": 2097152,
        "max_response_bytes": 8388608,
    }


def validate(config):
    if not isinstance(config.get("api_key_file", "nvidia-api-key.txt"), str) or not config.get("api_key_file", "nvidia-api-key.txt").strip():
        raise ValueError("api_key_file deve essere un percorso non vuoto")
    def positive(value, name):
        if isinstance(value, bool) or not isinstance(value, (float, int)) or value <= 0:
            raise ValueError(name + " deve essere positivo")
    for field in ("idle_seconds", "total_seconds", "rpm", "max_calls_per_run",
                  "cooldown_seconds", "max_request_bytes", "max_response_bytes"):
        positive(config[field], field)
    positive(config.get("client_context_tokens", 65536), "client_context_tokens")
    if config["max_attempts"] not in (1, 2):
        raise ValueError("max_attempts deve essere 1 o 2")
    for tier in TIERS:
        positive(config["first_token_seconds"][tier], "first_token_seconds." + tier)
    ids = set()
    reserved = {"model", "messages", "stream", "max_tokens", "tools", "tool_choice",
                "stream_options", "n", "stop", "temperature", "top_p"}
    for model in config["models"]:
        if model["id"] in ids or model["tier"] not in TIERS:
            raise ValueError("ID duplicato o tier non valido")
        ids.add(model["id"])
        if not isinstance(model["extra_body"], dict) or reserved.intersection(model["extra_body"]):
            raise ValueError("extra_body non può sovrascrivere campi del gateway")
        for name in ("max_input_bytes", "max_output_tokens"):
            positive(model[name], name)
    if not any(m["enabled"] and m["free_endpoint"] and m["tools"] for m in config["models"]):
        raise ValueError("Nessun modello gratuito con strumenti abilitato")
    return config


def latest_task(body):
    # Do not classify system prompts, tool output, or earlier tasks as user intent.
    for msg in reversed(body.get("messages", [])):
        if msg.get("role") != "user":
            continue
        content = msg.get("content", "")
        if isinstance(content, str):
            if content.strip():
                return content
        else:
            text = " ".join(b.get("text", "") for b in content if b.get("type") == "text")
            if text.strip():
                return text
    return ""


def classify(body, request_class=""):
    alias = body.get("model", "route-auto")
    if alias not in ALIASES:
        raise GatewayError("Modello locale sconosciuto; usa route-auto/fast/balanced/deep")
    if alias != "route-auto":
        return alias[6:], "profilo esplicito"
    if request_class in ("auxiliary", "compaction"):
        return "fast", "richiesta ausiliaria"
    task = latest_task(body).lower()
    if re.search(r"\b(architettura|architecture|sicurezza|security|race condition|deadlock|"
                 r"concorrenza|concurrency|migrazione|migration|refactor|distributed|distribuito)\b", task):
        return "deep", "task complessa secondo regole locali"
    if len(task) < 700 and re.search(r"\b(riassumi|summari[sz]e|traduci|translate|rinomina|rename|"
                                    r"typo|commento|comment|spiega|explain)\b", task):
        return "fast", "task breve secondo regole locali"
    return "balanced", "profilo predefinito per coding"


class Policy:
    def __init__(self, config):
        self.config = validate(config)
        self.lock = threading.Lock()
        self.cooldown = {}
        self.starts = []
        self.calls = 0
        self.blocked_until = 0
        self.bindings = {}

    def candidates(self, body, request_class="", binding=""):
        tier, reason = classify(body, request_class)
        # This is a byte safety limit, NOT a tokenizer/context-window guarantee.
        size = len(json.dumps(body, ensure_ascii=False).encode("utf-8"))
        max_tokens = body.get("max_tokens", 8192)
        rank = TIERS.index(tier)
        now = time.monotonic()
        with self.lock:
            result = [m for m in self.config["models"]
                      if m["enabled"] and m["free_endpoint"] and m["tools"]
                      and TIERS.index(m["tier"]) >= rank
                      and m["max_input_bytes"] >= size and m["max_output_tokens"] >= max_tokens
                      and self.cooldown.get(m["id"], 0) <= now]
        result.sort(key=lambda m: TIERS.index(m["tier"]))
        with self.lock:
            preferred = self.bindings.get(binding, (None, 0))
        if binding and preferred[1] > now:
            result.sort(key=lambda m: m["id"] != preferred[0])
        if not result:
            raise GatewayError("Nessun modello idoneo: controlla limiti input/output, profili e cooldown", 400)
        return result[:self.config["max_attempts"]], reason

    def bind(self, key, model_id):
        if key:
            with self.lock:
                now = time.monotonic()
                self.bindings = {k: v for k, v in self.bindings.items() if v[1] > now}
                if len(self.bindings) >= 1024:
                    self.bindings.pop(next(iter(self.bindings)))
                self.bindings[key] = (model_id, now + 1800)

    def reserve(self):
        now = time.monotonic()
        with self.lock:
            if now < self.blocked_until:
                raise GatewayError("NVIDIA in cooldown dopo 429", 429, retry_after=max(1, int(self.blocked_until-now)+1))
            self.starts = [t for t in self.starts if now-t < 60]
            if self.calls >= self.config["max_calls_per_run"]:
                raise GatewayError("Budget richieste del processo esaurito", 429, retry_after=3600)
            if len(self.starts) >= self.config["rpm"]:
                raise GatewayError("Limite RPM locale raggiunto", 429, retry_after=max(1, int(60-(now-self.starts[0]))+1))
            self.calls += 1
            self.starts.append(now)

    def failed(self, model_id, error):
        with self.lock:
            if error.status == 429:
                self.blocked_until = time.monotonic() + max(error.retry_after, self.config["cooldown_seconds"])
            elif error.retryable:
                self.cooldown[model_id] = time.monotonic() + self.config["cooldown_seconds"]


def binding_key(body, headers):
    session = headers.get("x-claude-code-session-id", "")
    if not session:
        return ""
    prompt = headers.get("x-claude-code-prompt-id") or latest_task(body)
    parts = [session, headers.get("x-claude-code-agent-id", "main"), body.get("model", ""), prompt]
    return hashlib.sha256(json.dumps(parts).encode()).hexdigest()
