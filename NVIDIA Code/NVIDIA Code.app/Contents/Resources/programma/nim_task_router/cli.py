import argparse
import getpass
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import tempfile
from contextlib import contextmanager
import httpx
from .engine import API_BASE
from .policy import TIERS, GatewayError, classify, default_config, validate
from .server import make_server


def read_config(path):
    if not path.exists():
        raise ValueError("Configurazione assente. Esegui nim-router init")
    return validate(json.loads(path.read_text(encoding="utf-8")))


KEY_FILE = "nvidia-api-key.txt"
KEY_PLACEHOLDER = "INCOLLA_QUI_LA_TUA_CHIAVE_NVIDIA"


def create_key_file(config_path):
    path = config_path.resolve().parent / KEY_FILE
    try:
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return path
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(KEY_PLACEHOLDER+"\n")
    return path


def key_input(config_path=None):
    config_path = (config_path or Path("nim-router.json")).resolve()
    config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    path = Path(config.get("api_key_file", KEY_FILE)).expanduser()
    if not path.is_absolute():
        path = config_path.parent / path
    if path.exists():
        key = path.read_text(encoding="utf-8-sig").strip()
        if not key or key == KEY_PLACEHOLDER:
            raise ValueError("Inserisci la chiave nel file "+str(path)+" (testo semplice, una sola riga)")
        if any(c.isspace() for c in key) or key.startswith("{\\rtf"):
            raise ValueError("Il file della chiave deve contenere solo la chiave, in testo semplice su una riga")
        print("Chiave NVIDIA caricata dal file locale.")
        return key
    key = os.environ.get("NVIDIA_API_KEY") or getpass.getpass("Chiave NVIDIA (non verrà salvata): ")
    if not key.strip():
        raise ValueError("Chiave NVIDIA vuota")
    return key.strip()


def claude_env(port, token, env=None, context_tokens=65536):
    child = dict(os.environ if env is None else env)
    for name in ("NVIDIA_API_KEY", "ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN",
                 "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL", "CLAUDE_CODE_USE_BEDROCK",
                 "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY", "CLAUDE_CODE_USE_ANTHROPIC_AWS",
                 "CLAUDE_CODE_RETRY_WATCHDOG"):
        child.pop(name, None)
    child.update({"ANTHROPIC_BASE_URL": "http://127.0.0.1:"+str(port),
        "ANTHROPIC_AUTH_TOKEN": token, "ANTHROPIC_MODEL": "route-auto",
        "ANTHROPIC_CUSTOM_MODEL_OPTION": "route-auto",
        "ANTHROPIC_CUSTOM_MODEL_OPTION_NAME": "NVIDIA Code",
        "ANTHROPIC_CUSTOM_MODEL_OPTION_DESCRIPTION": "Routing locale ai modelli NVIDIA configurati",
        "ANTHROPIC_DEFAULT_SONNET_MODEL": "route-auto", "ANTHROPIC_DEFAULT_HAIKU_MODEL": "route-fast",
        "ANTHROPIC_DEFAULT_OPUS_MODEL": "route-deep", "CLAUDE_CODE_SUBAGENT_MODEL": "route-balanced",
        "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "8192", "MAX_THINKING_TOKENS": "0",
        "CLAUDE_CODE_MAX_CONTEXT_TOKENS": str(context_tokens),
        "CLAUDE_CODE_MAX_RETRIES": "0",
        "CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS": "1", "CLAUDE_CODE_GATEWAY_HINT_HEADERS": "1"})
    return child


def gateway_settings(env):
    # CLI settings outrank user/project settings, unlike inherited environment.
    names = ("ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_MODEL",
             "ANTHROPIC_CUSTOM_MODEL_OPTION", "ANTHROPIC_CUSTOM_MODEL_OPTION_NAME",
             "ANTHROPIC_CUSTOM_MODEL_OPTION_DESCRIPTION", "ANTHROPIC_DEFAULT_SONNET_MODEL",
             "ANTHROPIC_DEFAULT_HAIKU_MODEL", "ANTHROPIC_DEFAULT_OPUS_MODEL",
             "CLAUDE_CODE_SUBAGENT_MODEL", "CLAUDE_CODE_MAX_OUTPUT_TOKENS",
             "MAX_THINKING_TOKENS", "CLAUDE_CODE_MAX_CONTEXT_TOKENS", "CLAUDE_CODE_MAX_RETRIES",
             "CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS", "CLAUDE_CODE_GATEWAY_HINT_HEADERS")
    settings = {name: env[name] for name in names}
    for name in ("ANTHROPIC_API_KEY", "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX",
                 "CLAUDE_CODE_USE_FOUNDRY", "CLAUDE_CODE_USE_ANTHROPIC_AWS", "CLAUDE_CODE_RETRY_WATCHDOG"):
        settings[name] = ""
    return {"env": settings}


@contextmanager
def session_settings(env):
    # Contains only the short-lived local gateway token, never the NVIDIA key.
    with tempfile.TemporaryDirectory(prefix="nvidia-code-session-") as folder:
        path = Path(folder)/"settings.json"
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(gateway_settings(env), file)
        yield path


def check_model(config, model_id, key):
    if not any(m["id"] == model_id and m["enabled"] and m["free_endpoint"] and m["tools"] for m in config["models"]):
        raise ValueError("Modello non abilitato come Free Endpoint con strumenti")
    print("Verifica esplicita: due richieste di inferenza, senza retry.")
    tool = {"type": "function", "function": {"name": "echo", "description": "Echo a value",
            "parameters": {"type": "object", "properties": {"value": {"type": "string"}}, "required": ["value"]}}}
    messages = [{"role": "user", "content": "Call the echo tool with value pong. After its result, reply exactly pong."}]
    extra = next(m["extra_body"] for m in config["models"] if m["id"] == model_id)
    with httpx.Client(timeout=120, trust_env=False) as client:
        def call(data):
            r = client.post(API_BASE+"/chat/completions", headers={"Authorization": "Bearer "+key}, json=data)
            if r.status_code != 200:
                raise ValueError("Verifica NVIDIA fallita: HTTP "+str(r.status_code))
            return r.json()["choices"][0]["message"]
        response = call({**extra, "model": model_id, "messages": messages, "tools": [tool],
            "tool_choice": {"type": "function", "function": {"name": "echo"}}, "max_tokens": 4096, "stream": False})
        calls = response.get("tool_calls") or []
        if len(calls) != 1 or calls[0]["function"]["name"] != "echo" or json.loads(calls[0]["function"]["arguments"]) != {"value": "pong"}:
            raise ValueError("Tool calling non conforme; modello da verificare manualmente")
        messages.append({k: response[k] for k in ("role", "content", "tool_calls") if k in response})
        messages.append({"role": "tool", "tool_call_id": calls[0]["id"], "content": "pong"})
        final = call({**extra, "model": model_id, "messages": messages, "tools": [tool],
                      "tool_choice": "none", "max_tokens": 4096, "stream": False})
        if (final.get("content") or "").strip().lower().strip(".\"'") != "pong":
            raise ValueError("Risultato del secondo turno non conforme")
    print("Tool calling e secondo turno verificati. Non è un benchmark di coding né un test completo di Claude Code.")


def main():
    parser = argparse.ArgumentParser(description="Gateway locale sperimentale NVIDIA per Claude Code")
    parser.add_argument("--config", type=Path, default=Path("nim-router.json"))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="Crea configurazione senza chiavi")
    catalog = sub.add_parser("catalog", help="Mostra catalogo; --remote legge /models senza inferenze")
    catalog.add_argument("--remote", action="store_true")
    add = sub.add_parser("add-model", help="Aggiungi un Free Endpoint chat/tool verificato da te")
    add.add_argument("model")
    add.add_argument("--tier", choices=TIERS, required=True)
    add.add_argument("--source", required=True, help="Pagina https://build.nvidia.com/ del Free Endpoint")
    route = sub.add_parser("route", help="Spiega una scelta senza chiamare NVIDIA")
    route.add_argument("task")
    check = sub.add_parser("check", help="Verifica esplicita con due inferenze")
    check.add_argument("model")
    run = sub.add_parser("run", help="Avvia gateway e Claude Code nel progetto corrente")
    run.add_argument("claude_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    try:
        if args.command == "init":
            with args.config.open("x", encoding="utf-8") as f:
                json.dump(default_config(), f, indent=2, ensure_ascii=False)
                f.write("\n")
            print("Creato "+str(args.config)+". Nessuna chiave salvata; nessuna inferenza eseguita.")
            print("Inserisci la chiave in "+str(create_key_file(args.config)))
            return
        if args.command == "route":
            body = {"model": "route-auto", "messages": [{"role": "user", "content": args.task}]}
            tier, reason = classify(body)
            print(json.dumps({"tier": tier, "reason": reason, "api_calls": 0}, ensure_ascii=False))
            return
        config = read_config(args.config)
        if args.command == "catalog":
            known = {m["id"]: m for m in config["models"]}
            if not args.remote:
                for model in config["models"]:
                    print(json.dumps(model, ensure_ascii=False))
                return
            # Model-list membership does not prove free access or tool support.
            with httpx.Client(timeout=30, trust_env=False) as client:
                r = client.get(API_BASE+"/models", headers={"Authorization": "Bearer "+key_input(args.config)})
                if r.status_code != 200:
                    raise ValueError("Catalogo NVIDIA: HTTP "+str(r.status_code))
                for item in r.json()["data"]:
                    model = known.get(item["id"])
                    print(json.dumps({"id": item["id"], "registered_free_endpoint": bool(model and model["free_endpoint"]),
                        "note": "Metadati locali; /models non certifica gratuità o compatibilità"}, ensure_ascii=False))
            return
        if args.command == "add-model":
            if not args.source.startswith("https://build.nvidia.com/"):
                raise ValueError("Indica la pagina ufficiale del modello")
            config["models"].append({"id": args.model, "tier": args.tier, "source": args.source,
                "enabled": True, "free_endpoint": True, "tools": True, "max_input_bytes": 180000,
                "max_output_tokens": 8192, "extra_body": {}})
            validate(config)
            args.config.write_text(json.dumps(config, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
            print("Aggiunto con la tua attestazione Free Endpoint/tool calling. Nessuna inferenza.")
            return
        if args.command == "check":
            check_model(config, args.model, key_input(args.config))
            return
        claude = shutil.which("claude")
        if not claude:
            raise ValueError("Claude Code non trovato nel PATH. Installalo separatamente seguendo la documentazione Anthropic.")
        key = key_input(args.config)
        server = make_server(config, key)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        print("Gateway su 127.0.0.1:"+str(server.server_port)+". Log con soli metadati su stderr.")
        try:
            cli_args = args.claude_args
            if cli_args[:1] == ["--"]:
                cli_args = cli_args[1:]
            child_env = claude_env(server.server_port, server.local_token,
                context_tokens=config.get("client_context_tokens", 65536))
            with session_settings(child_env) as settings_file:
                code = subprocess.call([claude, *cli_args, "--settings", str(settings_file)], env=child_env)
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=2)
        raise SystemExit(code)
    except (ValueError, OSError, GatewayError, httpx.HTTPError, KeyError) as e:
        # Never print raw HTTP errors/response bodies containing provider data.
        message = str(e) if isinstance(e, (ValueError, GatewayError)) else "Operazione non riuscita (rete, file o formato risposta)"
        print("Errore: "+message, file=sys.stderr)
        raise SystemExit(1)
    except KeyboardInterrupt:
        raise SystemExit(130)
