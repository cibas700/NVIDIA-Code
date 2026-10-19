# NVIDIA Code

[English](#english) | [Italiano](#italiano)

<a id="english"></a>

## English

**NVIDIA Code** is an experimental macOS launcher and local API gateway for using the **Claude Code CLI** with selected models hosted by NVIDIA.

Double-clicking the application opens Terminal, starts a local Python gateway, and launches the separately installed Claude Code CLI. The gateway translates the supported subset of Anthropic Messages requests into NVIDIA chat-completion requests.

**NVIDIA Code does not run Claude models on NVIDIA, install Claude Code, or run inference on your Mac.** The responding model is an eligible NVIDIA-hosted model from the local configuration. Requests are sent over the Internet.

> [!IMPORTANT]
> Use your own NVIDIA API key. Personal copies of this package can already contain a real key in `Dati/nvidia-api-key.txt`. A key stored separately from the JSON configuration is still included if you share the whole folder or ZIP. Public packages must contain an empty key file or a placeholder, never a real credential.

### Contents

- [Requirements](#en-requirements)
- [Installation and first launch](#en-installation)
- [Projects and daily use](#en-projects)
- [Routing and model configuration](#en-routing)
- [Fallback and limits](#en-fallback)
- [Advanced CLI and diagnostics](#en-cli)
- [Credentials, privacy and distribution](#en-security)
- [Troubleshooting](#en-troubleshooting)
- [Updates, verification and limitations](#en-limitations)
- [Independence and licensing](#en-license)

<a id="en-requirements"></a>

### Requirements

| Component | Requirement for the inspected package |
| --- | --- |
| Operating system | macOS **13.0 or later**, as declared in `Info.plist`. |
| Architecture | The launcher is intended for Intel and Apple Silicon Macs; check the binary included in your release. |
| Terminal | Apple's Terminal application, used by the graphical launcher. |
| Python | Python **3.9 or later at `/usr/bin/python3`** for the included launch scripts. |
| Claude Code | A separately installed `claude` executable discoverable by the launcher. |
| NVIDIA access | A personal API key and access to the configured hosted models. |
| Network | HTTPS access to `integrate.api.nvidia.com`. |

Check the interpreter actually used by the launcher:

```bash
/usr/bin/python3 --version
claude --version
```

**A working `python3` command alone is insufficient.** A Homebrew or python.org installation can resolve to another path. The supplied launcher explicitly invokes `/usr/bin/python3`; it does not automatically select another interpreter.

If that interpreter is missing, check your Apple Command Line Tools installation. To use a different Python, a maintainer must adapt the launcher and verify the bundled dependencies with that interpreter. Editing files inside the app can invalidate its signature.

The app includes the router and its Python libraries in `Contents/Resources/programma/`. Normal use of this bundle does not require creating a virtual environment or installing the router again with `pip`.

No local NVIDIA GPU, Docker installation, downloaded model weights, or local NIM server is required for this hosted API workflow.

#### Install Claude Code separately

The native macOS installation method documented by Anthropic is:

```bash
curl -fsSL https://claude.ai/install.sh | bash
```

Then open a new Terminal window and check:

```bash
claude --version
claude doctor
```

See the [official Claude Code setup documentation](https://code.claude.com/docs/en/setup) for current installation methods, platform requirements, authentication and updates. The native installation does not require Node.js solely to run this launcher; individual development tools or MCP servers can have their own dependencies.

The included launcher adds `~/.local/bin`, `/opt/homebrew/bin`, `/usr/local/bin` and standard system directories to `PATH`. Installations managed through a shell-specific version manager may need additional PATH configuration.

#### Obtain an NVIDIA key

Use the [NVIDIA API Catalog](https://build.nvidia.com/) and the instructions for the chosen model to obtain API access. NVIDIA's [API Catalog quickstart](https://docs.api.nvidia.com/nim/re/docs/api-quickstart) explains the hosted API workflow.

Account access, usage conditions and model availability must be checked with NVIDIA. Local configuration flags do not establish that an endpoint is free or accessible.

<a id="en-installation"></a>

### Installation and first launch

1. Obtain a complete application package from the project's trusted distribution source and extract it. A repository clone is usable directly only if it contains the complete runnable bundle; source code alone may require a build.
2. Keep the complete folder together:

   ```text
   NVIDIA Code/
   ├── NVIDIA Code.app/
   │   └── Contents/
   │       └── Resources/
   │           ├── Avvia.command
   │           ├── programma/
   │           └── Sorgenti/
   ├── Terminal.command
   ├── Dati/
   │   ├── nim-router.json
   │   └── nvidia-api-key.txt
   ├── Progetti/
   └── LEGGIMI.txt
   ```

3. Open `Dati/nvidia-api-key.txt` in a plain-text editor. In TextEdit, choose **Format → Make Plain Text** if necessary. Replace its contents with your own key on one line. Do not add quotes, `NVIDIA_API_KEY=`, Markdown fences or explanatory text. Preserve the `.txt` extension; do not save as RTF.
4. Check `/usr/bin/python3 --version` and `claude --version`.
5. Double-click `NVIDIA Code.app`. Terminal should open and display the project directory and gateway startup message.
6. Review any project trust or tool-permission prompts shown by Claude Code. Start with a small text request. This sends an actual inference request to NVIDIA.

Alternative launch: double-click `Terminal.command`.

To launch from an existing Terminal, change into the extracted `NVIDIA Code` directory and run:

```bash
/bin/zsh './Terminal.command'
```

Move the entire `NVIDIA Code` folder when relocating the installation. The app expects `Dati` next to the `.app`, and uses `Progetti` as its default working directory. A Dock shortcut may point to the app while the app stays inside the complete folder.

<a id="en-projects"></a>

### Projects and daily use

- Double-clicking opens Claude Code inside the included `Progetti/` directory.
- To open an existing project, drag **one project folder** onto `NVIDIA Code.app`. The project remains at its original location.
- If several items are supplied, the native launcher uses only the first.
- To select a project from Terminal:

  ```bash
  /bin/zsh './Terminal.command' '/absolute/path/to/MyProject'
  ```

- Enter `/exit` in Claude Code to end the session normally. The gateway shuts down after the CLI exits; Terminal may remain open.

Claude Code tools can read or change files and execute commands according to their permissions. Review the selected directory and requested actions before approving them.

The graphical application hands the session over to Terminal and then exits. Closing the graphical launcher is therefore not a control for an already running Terminal session.

<a id="en-routing"></a>

### Routing and model configuration

The configuration file is `Dati/nim-router.json`.

```text
Claude Code CLI
    → local gateway at http://127.0.0.1:<temporary-port>
    → local routing rules and protocol translation
    → https://integrate.api.nvidia.com/v1/chat/completions
    → eligible NVIDIA-hosted model
```

**The upstream URL is fixed in `nim_task_router/engine.py`.** This version does not expose a configurable endpoint URL in `nim-router.json`. A model's `source` URL is descriptive metadata, not its inference endpoint.

#### Local model aliases

| Alias | Routing behavior |
| --- | --- |
| `route-auto` | Uses local rules to select a tier. |
| `route-fast` | Starts with eligible `fast` models, then higher tiers if needed. |
| `route-balanced` | Considers eligible `balanced` and `deep` models. |
| `route-deep` | Considers only eligible `deep` models. |

These are gateway aliases, not NVIDIA model IDs. The launcher's default is `route-auto`. For example, the advanced `run` command can pass `--model route-deep` to Claude Code, as shown below.

Automatic classification uses the latest non-empty user text and selected request hints. It does not call an extra classifier model:

- Auxiliary or compaction requests marked by the supported hint use `fast`.
- Recognized terms such as `architecture`, `security`, `migration` or `refactor`, and their implemented Italian equivalents, select `deep`.
- A request shorter than 700 characters containing supported terms such as `translate`, `rename`, `summarize` or `explain` selects `fast`.
- Other requests select `balanced`.

This is a keyword heuristic, not a measured assessment of task difficulty. Higher-tier eligibility does not guarantee better output.

#### Candidate selection

A candidate must be enabled and have both `free_endpoint` and `tools` set to `true`. It must also satisfy the tier, input-size, output-token and cooldown checks.

Candidates are ordered by tier, preserving configuration order within a tier. A successful model may be preferred for related requests for up to 30 minutes when session/prompt identifiers allow binding. The list is then limited by `max_attempts`.

With the inspected configuration, a request normally has at most **two candidate attempts**. The router does not benchmark or automatically discover the best model.

#### Model entries in the inspected package

| NVIDIA model ID as stored in the JSON | Tier |
| --- | --- |
| `poolside/laguna-xs-2.1` | `balanced` |
| `nvidia/nemotron-3.5-lightning-30b-a3b` | `fast` |
| `nvidia/nemotron-3-ultra-550b-a55b` | `deep` |
| `stepfun-ai/step-5-preview` | `deep` |
| `z-ai/glm-5.3-flash` | `balanced` |
| `meta/muse-glimmer-30b` | `fast` |
| `nvidia/nemotron-3.5-super-vl-120b-a12b` | `balanced` |

This table records the package contents. It does **not** confirm that these IDs currently exist, are available to your account, are free, or support compliant tool calling. Verify each model before relying on it. This package does not include every NVIDIA endpoint.

#### Model fields

| Field | Meaning |
| --- | --- |
| `id` | Upstream model ID sent to NVIDIA. |
| `tier` | `fast`, `balanced` or `deep`. |
| `enabled` | Whether the router may select the entry. |
| `free_endpoint` | Local eligibility declaration; not a billing check. |
| `tools` | Local declaration of tool support; not an automatic compatibility test. |
| `source` | Reference page for the model. |
| `max_input_bytes` | Local limit on the serialized incoming request size; not a token-context guarantee. |
| `max_output_tokens` | Maximum requested output accepted for this candidate. |
| `extra_body` | Additional provider parameters; reserved gateway fields cannot be overridden here. |

All seven supplied entries use `max_input_bytes: 180000` and `max_output_tokens: 8192`. Disabling an entry uses `"enabled": false`. Keep at least one eligible entry and avoid duplicate IDs.

Back up the JSON before editing and restart the session after changes. Syntax validation alone does not establish model availability or complete configuration correctness.

<a id="en-fallback"></a>

### Fallback and limits

Fallback is sequential and limited. It requires an eligible second candidate, remaining time and budget, and an error marked retryable **before semantic model output has started**.

Retryable cases include connection failures, supported timeouts, HTTP `408`, `500`, `502`, `503`, `504`, and certain invalid upstream streams.

- HTTP `400`, `401`, `403` and `404` do not trigger model fallback.
- HTTP `429` triggers a gateway-wide cooldown rather than an immediate attempt with another model.
- Once the model has produced text, reasoning or tool-call output, the gateway does not replay the request on another model. This also applies when reasoning has started but no visible answer is shown yet.
- A disconnected Claude Code client does not trigger fallback.
- Closing a failed upstream stream does not guarantee that NVIDIA cancels all processing or accounting.

| Setting | Supplied value | Meaning |
| --- | --- | --- |
| `first_token_seconds` | `fast: 45`, `balanced: 75`, `deep: 120` | Deadline for connection/headers and first semantic output for each attempt. |
| `idle_seconds` | `60` | Allowed interval without semantic output after a response starts. |
| `total_seconds` | `240` | Shared time budget for processing a request across attempts. |
| `max_attempts` | `2` | At most two eligible candidates; supported values are 1 or 2. |
| `max_calls_per_run` | `100` | Local upstream-attempt budget for one gateway process, including fallback attempts. |
| `rpm` | `10` | Local rolling 60-second attempt limit; not NVIDIA's quota. |
| `cooldown_seconds` | `90` | Model cooldown after retryable failures; minimum global cooldown after `429`. |
| `max_request_bytes` | `2097152` | Maximum incoming HTTP request body: 2 MiB. |
| `max_response_bytes` | `8388608` | Limit on the upstream stream size counted by the implementation: 8 MiB. |
| `api_key_file` | `nvidia-api-key.txt` | Key path, resolved relative to the configuration directory if not absolute. |
| `client_context_tokens` | Omitted; code defaults to `65536` | Context setting passed to Claude Code; not proof of upstream context capacity. |

The server admits at most four concurrent message requests. Local limits do not replace provider quotas, prevent all costs, or coordinate separate application instances. A fresh gateway process has fresh local counters.

<a id="en-cli"></a>

### Advanced CLI and diagnostics

From the extracted `NVIDIA Code` directory, define this shell helper to use the bundled router and libraries:

```bash
claude_nvidia_router() {
  PYTHONPATH="$PWD/NVIDIA Code.app/Contents/Resources/programma" \
  PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
  /usr/bin/python3 -m nim_task_router \
    --config "$PWD/Dati/nim-router.json" "$@"
}
```

Run it from that directory. The function exists only in the current shell. It does not install a global command. The `--config` option belongs before the subcommand.

| Command | Effect | NVIDIA traffic |
| --- | --- | --- |
| `claude_nvidia_router --help` | Show CLI help. | None. |
| `claude_nvidia_router route 'Explain this project'` | Show the tier selected by the local classifier. | None; does not validate the configured models or credentials. |
| `claude_nvidia_router catalog` | List configured model entries. | None. |
| `claude_nvidia_router catalog --remote` | Request NVIDIA's `/v1/models` list. | Authenticated network request; no inference. |
| `claude_nvidia_router check 'MODEL_ID'` | Test a tool call and a follow-up response. | Up to two real inference requests if the first succeeds; no retry. |
| `claude_nvidia_router run` | Start the gateway and Claude Code in the current directory. | Actual use sends inference requests. |
| `claude_nvidia_router run -- --model route-deep` | Start Claude Code with the deep routing alias. | Actual use sends inference requests. |

Replace `MODEL_ID` with an exact configured model ID. `check` is a small tool-calling test, not a coding benchmark or full Claude Code compatibility test. It does not establish streaming compatibility. The remote model list does not certify free access or tool support.

The CLI also includes `init` and `add-model`; inspect their `--help` before use. `init` creates a new configuration and refuses to overwrite an existing one. `add-model` changes the JSON and records your declaration that a model is an appropriate free/tool-capable endpoint; it does not verify that declaration with inference.

The application bundle and launch script also contain `--verifica` checks. They check bundle structure or offline classification, respectively; they do not verify API credentials, NVIDIA inference or the full Finder-to-Terminal launch flow.

<a id="en-security"></a>

### Credentials, privacy and distribution

#### Key loading

The router first resolves `api_key_file` from the configuration. With the supplied setting, the file is `Dati/nvidia-api-key.txt`.

- If the file exists, its contents take precedence over `NVIDIA_API_KEY`.
- An empty file or the exact placeholder `INCOLLA_QUI_LA_TUA_CHIAVE_NVIDIA` stops startup and asks you to edit the file.
- Only when the file is absent does the router try `NVIDIA_API_KEY`, then an interactive hidden prompt. That prompt does not save the key.

The key file is **plain text**, not encrypted storage or macOS Keychain. To restrict its permissions, from the package directory run:

```bash
chmod 600 'Dati/nvidia-api-key.txt'
```

The gateway holds the NVIDIA key in its Python process and uses it for upstream authorization. It removes `NVIDIA_API_KEY` from the environment passed to Claude Code. The inspected package contains one recognizable NVIDIA API key, located only in the text file; the JSON contains its filename rather than its value.

#### Local gateway and data flow

The gateway listens on `127.0.0.1` with a temporary port and session token. The launcher supplies Claude Code with temporary gateway settings; the temporary settings file contains the local token, not the NVIDIA key, and is removed during normal cleanup.

The gateway sends supported conversation content—including project text and tool results included in requests—to NVIDIA. Running the gateway locally does **not** keep inference data on the Mac. Claude Code and other tools may also have their own network activity and local records.

Router logs are designed to emit metadata such as selected model, attempts, errors, duration and reported usage. That does not guarantee that Terminal scrollback, Claude Code transcripts, hooks or other tools are free of sensitive information. Review material before sharing it.

#### Preparing a public copy

1. Work on a separate copy of the package.
2. Replace the real key with the exact placeholder above, or remove the key file and document the first-use setup.
3. Exclude private projects, transcripts, logs and other credentials.
4. Verify the actual release ZIP as well as the repository. `.gitignore` does not sanitize archives or remove previously committed secrets.
5. Ensure project licensing and third-party notices are included.

A suggested repository exclusion is:

```gitignore
# Personal credentials
**/Dati/nvidia-api-key.txt
```

Track a separate example file if needed. Review the rule against your repository layout. If a real key has been published or sent to an unintended recipient, revoke it through NVIDIA; deleting the latest file does not invalidate previously shared copies.

<a id="en-troubleshooting"></a>

### Troubleshooting

| Symptom | What to check |
| --- | --- |
| `claude` not found | Install the CLI; run `claude --version` and `claude doctor`. Compare its installation path with the launcher's PATH, especially when using version managers. |
| Python missing or too old | Test `/usr/bin/python3 --version`, not only `python3 --version`. Another installed Python does not automatically satisfy this launcher. |
| Missing `Dati/nim-router.json` | Restore the complete folder structure. Moving only the `.app` breaks its relative paths. |
| Key not loaded | Check the configured path, plain-text format, filename and contents. An existing empty/placeholder file blocks environment-variable fallback. |
| NVIDIA `401` or `403` | Check key validity and account permissions. These errors do not trigger automatic model fallback. |
| NVIDIA `404` | Verify the configured model ID and API availability. The router does not automatically replace an unavailable ID. |
| NVIDIA `429` | Wait for the indicated cooldown and review provider quotas and local RPM limits. Repeated relaunching does not change NVIDIA's quota. |
| `Nessun modello idoneo` | Check enabled entries, tier, `free_endpoint`, `tools`, input/output limits and cooldowns. |
| Request budget exhausted | The current gateway reached `max_calls_per_run`. End the session and review usage before starting another one. |
| Unsupported block or payload | Use text and supported client tools. Images, documents and unsupported Anthropic features cannot be forwarded by this adapter. |
| Incomplete response or timeout | Check the model and timeouts. An interrupted response is not replayed after semantic output starts. |
| Works in Terminal but not Finder | Check `/usr/bin/python3`, launch-script PATH, macOS security controls and Terminal availability. The graphical path needs its own verification. |
| Corporate proxy required | The router's HTTP clients use `trust_env=False`; standard proxy environment variables are not automatically honored. Network adaptation may require code changes. |

For a script-launch diagnostic, run `/bin/zsh './Terminal.command'` from the package directory and inspect the displayed error.

If macOS blocks the app, establish the source's trustworthiness before using the system's security controls to allow it. The supplied notes describe an **ad hoc signature**, which is not Apple Developer ID signing or notarization. Permission changes to scripts do not resolve signing or quarantine issues.

If Claude Code opens but routing fails, inspect the first gateway error. The launcher supplies temporary `--settings` configuration to direct this session to the local gateway and clears selected inherited provider variables. Managed settings, hooks, plugins or changes in Claude Code can still affect compatibility; do not assume the app validates every external setting.

<a id="en-limitations"></a>

### Updates, verification and limitations

- This is an experimental adapter, not a complete Anthropic API implementation.
- The adapter supports text, custom client-side tool definitions, tool calls and text tool results. Claude Code executes permitted client tools; the gateway translates their messages.
- Image/document blocks, server-side tool formats and Anthropic structured output are unsupported. Assistant thinking blocks are not preserved as portable reasoning content.
- A model name containing `VL` does not add image support to this adapter.
- Context and byte limits are different. Increasing `client_context_tokens` does not enlarge the NVIDIA model's context window.
- Token usage may be unavailable; zeros in a response are not proof of zero use or cost.
- Model availability, pricing, quota and behavior are governed by NVIDIA and can change. Local `free_endpoint` flags are not a promise of free service.
- No specific Claude Code version is pinned or certified by the inspected bundle. CLI updates can introduce incompatible requests or settings behavior.
- Keep a backup before updating the bundle or JSON, and recheck a small text request and tool round trip after an update. These checks can make actual API calls.
- Preserve your personal key and projects privately when replacing a package; never copy them into a public release.

This README was checked against the supplied package's code and configuration. The documentation review did not launch the application, use the API key, perform NVIDIA inference, verify the live model catalog, or establish successful installation on a clean Mac. Statements in `LEGGIMI.txt` about earlier tests are historical notes, not new verification performed by this review.

<a id="en-license"></a>

### Independence and licensing

NVIDIA Code is an independent project and is not affiliated with or officially supported by Anthropic or NVIDIA. Product names and trademarks belong to their respective owners.

**No project-level `LICENSE` file was found in the inspected archive.** Do not assume a particular open-source license or permission to redistribute the project. Before publishing a release, the maintainer should add an appropriate project license and retain the notices and license terms of bundled third-party libraries. Claude Code and NVIDIA services remain subject to their respective terms.

---

<a id="italiano"></a>

## Italiano

**NVIDIA Code** è un launcher sperimentale per macOS con un gateway API locale che permette di utilizzare la **CLI di Claude Code** con alcuni modelli ospitati da NVIDIA.

Il doppio clic sull'applicazione apre il Terminale, avvia un gateway Python locale e lancia la CLI di Claude Code, da installare separatamente. Il gateway traduce il sottoinsieme supportato delle richieste Anthropic Messages in richieste chat completion per NVIDIA.

**NVIDIA Code non esegue i modelli Claude su NVIDIA, non installa Claude Code e non esegue l'inferenza sul Mac.** A rispondere è un modello NVIDIA idoneo presente nella configurazione locale. Le richieste vengono inviate tramite Internet.

> [!IMPORTANT]
> Utilizza la tua chiave API NVIDIA. Le copie personali del pacchetto possono già contenere una chiave reale in `Dati/nvidia-api-key.txt`. Separare la chiave dal JSON non la esclude dalla condivisione dell'intera cartella o dello ZIP. I pacchetti pubblici devono contenere un file vuoto o un segnaposto, mai una credenziale reale.

### Indice

- [Requisiti](#it-requisiti)
- [Installazione e primo avvio](#it-installazione)
- [Progetti e utilizzo](#it-progetti)
- [Routing e configurazione dei modelli](#it-routing)
- [Fallback e limiti](#it-fallback)
- [CLI avanzata e diagnostica](#it-cli)
- [Credenziali, privacy e distribuzione](#it-sicurezza)
- [Risoluzione dei problemi](#it-problemi)
- [Aggiornamenti, verifiche e limiti](#it-limiti)
- [Indipendenza e licenza](#it-licenza)

<a id="it-requisiti"></a>

### Requisiti

| Componente | Requisito per il pacchetto esaminato |
| --- | --- |
| Sistema operativo | macOS **13.0 o successivo**, come dichiarato in `Info.plist`. |
| Architettura | Launcher previsto per Mac Intel e Apple Silicon; verifica il binario incluso nella versione distribuita. |
| Terminale | Applicazione Terminale di Apple, utilizzata dal launcher grafico. |
| Python | Python **3.9 o successivo nel percorso `/usr/bin/python3`** per gli script inclusi. |
| Claude Code | Eseguibile `claude` installato separatamente e individuabile dal launcher. |
| Accesso NVIDIA | Chiave API personale e accesso ai modelli ospitati configurati. |
| Rete | Accesso HTTPS a `integrate.api.nvidia.com`. |

Controlla l'interprete effettivamente utilizzato dal launcher:

```bash
/usr/bin/python3 --version
claude --version
```

**Il solo funzionamento del comando `python3` non è sufficiente.** Un'installazione tramite Homebrew o python.org può trovarsi altrove. Il launcher incluso richiama esplicitamente `/usr/bin/python3` e non seleziona automaticamente un altro interprete.

Se l'interprete manca, controlla l'installazione degli strumenti da riga di comando Apple. Per utilizzare un altro Python, chi mantiene il progetto deve adattare il launcher e verificare le librerie incluse con quell'interprete. Modificare i file interni dell'app può invalidarne la firma.

L'app include il router e le librerie Python in `Contents/Resources/programma/`. Per il normale utilizzo del bundle non serve creare un ambiente virtuale né reinstallare il router con `pip`.

Questo utilizzo delle API ospitate non richiede una GPU NVIDIA locale, Docker, il download dei pesi dei modelli o un server NIM locale.

#### Installare Claude Code separatamente

Il metodo di installazione nativa per macOS documentato da Anthropic è:

```bash
curl -fsSL https://claude.ai/install.sh | bash
```

Apri quindi una nuova finestra del Terminale e controlla:

```bash
claude --version
claude doctor
```

Consulta la [documentazione ufficiale di installazione di Claude Code](https://code.claude.com/docs/en/setup) per metodi, requisiti, autenticazione e aggiornamenti correnti. L'installazione nativa non richiede Node.js per il solo funzionamento di questo launcher; singoli strumenti di sviluppo o server MCP possono avere dipendenze proprie.

Il launcher aggiunge al `PATH` `~/.local/bin`, `/opt/homebrew/bin`, `/usr/local/bin` e le directory standard di sistema. Le installazioni gestite da un version manager specifico della shell possono richiedere una configurazione aggiuntiva del PATH.

#### Ottenere una chiave NVIDIA

Utilizza [NVIDIA API Catalog](https://build.nvidia.com/) e le istruzioni del modello scelto per ottenere l'accesso alle API. La [guida introduttiva di NVIDIA API Catalog](https://docs.api.nvidia.com/nim/re/docs/api-quickstart) descrive l'utilizzo delle API ospitate.

Accesso dell'account, condizioni di utilizzo e disponibilità dei modelli vanno verificati con NVIDIA. I flag della configurazione locale non dimostrano che un endpoint sia gratuito o accessibile.

<a id="it-installazione"></a>

### Installazione e primo avvio

1. Ottieni un pacchetto applicativo completo da una fonte di distribuzione affidabile del progetto ed estrailo. Un clone del repository è direttamente utilizzabile soltanto se contiene il bundle completo ed eseguibile; i soli sorgenti possono richiedere una compilazione.
2. Mantieni unita l'intera cartella:

   ```text
   NVIDIA Code/
   ├── NVIDIA Code.app/
   │   └── Contents/
   │       └── Resources/
   │           ├── Avvia.command
   │           ├── programma/
   │           └── Sorgenti/
   ├── Terminal.command
   ├── Dati/
   │   ├── nim-router.json
   │   └── nvidia-api-key.txt
   ├── Progetti/
   └── LEGGIMI.txt
   ```

3. Apri `Dati/nvidia-api-key.txt` con un editor di testo semplice. In TextEdit, se necessario, seleziona **Formato → Converti in formato solo testo**. Sostituisci il contenuto con la tua chiave, su una sola riga. Non aggiungere virgolette, `NVIDIA_API_KEY=`, delimitatori Markdown o spiegazioni. Mantieni l'estensione `.txt`; non salvare in RTF.
4. Verifica `/usr/bin/python3 --version` e `claude --version`.
5. Fai doppio clic su `NVIDIA Code.app`. Il Terminale dovrebbe aprirsi e mostrare la directory del progetto e il messaggio di avvio del gateway.
6. Leggi le eventuali richieste di fiducia nel progetto e di autorizzazione agli strumenti mostrate da Claude Code. Prova una breve richiesta testuale: questa operazione invia una vera richiesta di inferenza a NVIDIA.

Avvio alternativo: doppio clic su `Terminal.command`.

Per avviare da un Terminale già aperto, entra nella cartella `NVIDIA Code` estratta ed esegui:

```bash
/bin/zsh './Terminal.command'
```

Per trasferire l'installazione, sposta l'intera cartella `NVIDIA Code`. L'app cerca `Dati` accanto al file `.app` e usa `Progetti` come directory predefinita. Puoi creare un collegamento nel Dock mantenendo l'app dentro la cartella completa.

<a id="it-progetti"></a>

### Progetti e utilizzo

- Il doppio clic avvia Claude Code nella directory `Progetti/` inclusa.
- Per aprire un progetto esistente, trascina **una cartella di progetto** su `NVIDIA Code.app`. Il progetto rimane nella sua posizione originale.
- Se vengono forniti più elementi, il launcher nativo utilizza soltanto il primo.
- Per scegliere il progetto dal Terminale:

  ```bash
  /bin/zsh './Terminal.command' '/percorso/assoluto/MioProgetto'
  ```

- Digita `/exit` in Claude Code per terminare normalmente la sessione. Il gateway si arresta dopo l'uscita della CLI; il Terminale può rimanere aperto.

Gli strumenti di Claude Code possono leggere o modificare file ed eseguire comandi secondo i permessi concessi. Controlla la directory selezionata e le azioni richieste prima di autorizzarle.

L'applicazione grafica passa la sessione al Terminale e poi termina. Chiudere il launcher grafico non controlla quindi una sessione già avviata nel Terminale.

<a id="it-routing"></a>

### Routing e configurazione dei modelli

La configurazione si trova in `Dati/nim-router.json`.

```text
CLI di Claude Code
    → gateway locale su http://127.0.0.1:<porta-temporanea>
    → regole locali di routing e traduzione del protocollo
    → https://integrate.api.nvidia.com/v1/chat/completions
    → modello NVIDIA ospitato idoneo
```

**L'URL del servizio remoto è fisso in `nim_task_router/engine.py`.** Questa versione non espone un URL di endpoint configurabile in `nim-router.json`. Il campo `source` di un modello è un riferimento descrittivo, non l'endpoint di inferenza.

#### Alias locali dei modelli

| Alias | Comportamento |
| --- | --- |
| `route-auto` | Sceglie un livello tramite regole locali. |
| `route-fast` | Considera prima i modelli `fast` idonei, poi quelli di livello superiore se necessario. |
| `route-balanced` | Considera i modelli `balanced` e `deep` idonei. |
| `route-deep` | Considera soltanto i modelli `deep` idonei. |

Sono alias del gateway, non ID di modelli NVIDIA. Il launcher usa normalmente `route-auto`. Per esempio, il comando avanzato `run` può passare `--model route-deep` a Claude Code, come indicato più avanti.

La classificazione automatica considera l'ultimo testo utente non vuoto e alcuni indicatori della richiesta. Non chiama un ulteriore modello classificatore:

- Le richieste ausiliarie o di compattazione contrassegnate dall'indicatore supportato usano `fast`.
- Termini riconosciuti come `architettura`, `sicurezza`, `migrazione` o `refactor`, e i corrispondenti inglesi implementati, selezionano `deep`.
- Una richiesta più breve di 700 caratteri contenente termini supportati come `traduci`, `rinomina`, `riassumi` o `spiega` seleziona `fast`.
- Le altre richieste selezionano `balanced`.

Si tratta di un'euristica basata su parole chiave, non di una valutazione misurata della difficoltà. L'appartenenza a un livello superiore non garantisce una risposta migliore.

#### Selezione dei candidati

Un candidato deve essere abilitato e avere `free_endpoint` e `tools` impostati a `true`. Deve inoltre rispettare i controlli su livello, dimensione dell'input, token di output e cooldown.

I candidati vengono ordinati per livello, mantenendo l'ordine della configurazione all'interno dello stesso livello. Un modello usato con successo può essere preferito per richieste correlate fino a 30 minuti, quando gli identificatori di sessione e prompt permettono questa associazione. La lista viene poi limitata da `max_attempts`.

Con la configurazione esaminata, ogni richiesta dispone normalmente di **al massimo due tentativi su candidati**. Il router non effettua benchmark e non scopre automaticamente il modello migliore.

#### Modelli presenti nel pacchetto esaminato

| ID NVIDIA memorizzato nel JSON | Livello |
| --- | --- |
| `poolside/laguna-xs-2.1` | `balanced` |
| `nvidia/nemotron-3.5-lightning-30b-a3b` | `fast` |
| `nvidia/nemotron-3-ultra-550b-a55b` | `deep` |
| `stepfun-ai/step-5-preview` | `deep` |
| `z-ai/glm-5.3-flash` | `balanced` |
| `meta/muse-glimmer-30b` | `fast` |
| `nvidia/nemotron-3.5-super-vl-120b-a12b` | `balanced` |

La tabella riporta il contenuto del pacchetto. **Non** certifica che questi ID esistano attualmente, siano accessibili dal tuo account, siano gratuiti o supportino correttamente le chiamate agli strumenti. Verifica ogni modello prima di farvi affidamento. Il pacchetto non include tutti gli endpoint NVIDIA.

#### Campi di ogni modello

| Campo | Significato |
| --- | --- |
| `id` | ID del modello inviato a NVIDIA. |
| `tier` | `fast`, `balanced` o `deep`. |
| `enabled` | Stabilisce se il router può selezionare la voce. |
| `free_endpoint` | Dichiarazione locale di idoneità; non verifica la fatturazione. |
| `tools` | Dichiarazione locale di supporto agli strumenti; non è un test automatico di compatibilità. |
| `source` | Pagina di riferimento del modello. |
| `max_input_bytes` | Limite locale della richiesta in ingresso serializzata; non garantisce la capienza del contesto in token. |
| `max_output_tokens` | Massimo output richiesto accettato per quel candidato. |
| `extra_body` | Parametri aggiuntivi del fornitore; non può sovrascrivere i campi riservati del gateway. |

Tutte le sette voci incluse usano `max_input_bytes: 180000` e `max_output_tokens: 8192`. Per disabilitare una voce usa `"enabled": false`. Mantieni almeno una voce idonea ed evita ID duplicati.

Prima di modificare il JSON, creane una copia di sicurezza; riavvia la sessione dopo le modifiche. La sola verifica della sintassi non dimostra la disponibilità dei modelli o la correttezza completa della configurazione.

<a id="it-fallback"></a>

### Fallback e limiti

Il fallback è sequenziale e limitato. Richiede un secondo candidato idoneo, tempo e budget residui e un errore classificato come ritentabile **prima dell'inizio dell'output semantico del modello**.

Sono ritentabili gli errori di connessione, i timeout supportati, gli HTTP `408`, `500`, `502`, `503`, `504` e alcuni errori del flusso remoto.

- Gli HTTP `400`, `401`, `403` e `404` non attivano il fallback.
- L'HTTP `429` attiva un cooldown dell'intero gateway, senza provare immediatamente un altro modello.
- Dopo l'inizio di testo, ragionamento o chiamate agli strumenti, il gateway non ripete la richiesta su un altro modello. Questo vale anche se è iniziato il ragionamento ma non compare ancora una risposta visibile.
- La disconnessione del client Claude Code non attiva il fallback.
- Chiudere un flusso remoto fallito non garantisce che NVIDIA interrompa ogni elaborazione o conteggio dell'utilizzo.

| Impostazione | Valore incluso | Significato |
| --- | --- | --- |
| `first_token_seconds` | `fast: 45`, `balanced: 75`, `deep: 120` | Scadenza per connessione/header e primo output semantico di ogni tentativo. |
| `idle_seconds` | `60` | Intervallo consentito senza output semantico dopo l'inizio della risposta. |
| `total_seconds` | `240` | Budget temporale condiviso dai tentativi di elaborazione di una richiesta. |
| `max_attempts` | `2` | Massimo due candidati; i valori supportati sono 1 o 2. |
| `max_calls_per_run` | `100` | Budget locale di tentativi remoti per un processo gateway, inclusi i fallback. |
| `rpm` | `10` | Limite locale di tentativi in una finestra mobile di 60 secondi; non è la quota NVIDIA. |
| `cooldown_seconds` | `90` | Cooldown del modello dopo errori ritentabili; cooldown globale minimo dopo un `429`. |
| `max_request_bytes` | `2097152` | Dimensione massima del corpo HTTP in ingresso: 2 MiB. |
| `max_response_bytes` | `8388608` | Limite della dimensione del flusso remoto conteggiata dall'implementazione: 8 MiB. |
| `api_key_file` | `nvidia-api-key.txt` | Percorso della chiave, relativo alla directory della configurazione se non assoluto. |
| `client_context_tokens` | Assente; il codice usa `65536` | Impostazione del contesto passata a Claude Code; non certifica la capacità del modello remoto. |

Il server ammette al massimo quattro richieste di messaggi contemporanee. I limiti locali non sostituiscono le quote del fornitore, non impediscono ogni costo e non coordinano istanze separate dell'applicazione. Ogni nuovo processo gateway ha contatori locali nuovi.

<a id="it-cli"></a>

### CLI avanzata e diagnostica

Dalla cartella `NVIDIA Code` estratta, definisci questa funzione di shell per usare il router e le librerie incluse:

```bash
claude_nvidia_router() {
  PYTHONPATH="$PWD/NVIDIA Code.app/Contents/Resources/programma" \
  PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
  /usr/bin/python3 -m nim_task_router \
    --config "$PWD/Dati/nim-router.json" "$@"
}
```

Eseguila da quella directory. La funzione esiste soltanto nella shell corrente e non installa un comando globale. L'opzione `--config` precede il sottocomando.

| Comando | Effetto | Traffico NVIDIA |
| --- | --- | --- |
| `claude_nvidia_router --help` | Mostra l'aiuto della CLI. | Nessuno. |
| `claude_nvidia_router route 'Spiega questo progetto'` | Mostra il livello scelto dal classificatore locale. | Nessuno; non valida i modelli configurati o le credenziali. |
| `claude_nvidia_router catalog` | Elenca le voci della configurazione. | Nessuno. |
| `claude_nvidia_router catalog --remote` | Richiede l'elenco NVIDIA `/v1/models`. | Richiesta autenticata di rete; nessuna inferenza. |
| `claude_nvidia_router check 'ID_MODELLO'` | Verifica una chiamata a uno strumento e la risposta successiva. | Fino a due vere richieste di inferenza se la prima riesce; nessun retry. |
| `claude_nvidia_router run` | Avvia gateway e Claude Code nella directory corrente. | L'utilizzo effettivo invia richieste di inferenza. |
| `claude_nvidia_router run -- --model route-deep` | Avvia Claude Code con l'alias deep. | L'utilizzo effettivo invia richieste di inferenza. |

Sostituisci `ID_MODELLO` con un ID esatto presente nella configurazione. `check` è un piccolo test delle chiamate agli strumenti, non un benchmark di coding o una verifica completa di Claude Code. Non verifica la compatibilità dello streaming. Il catalogo remoto non certifica gratuità o supporto agli strumenti.

La CLI include anche `init` e `add-model`: consulta il relativo `--help` prima dell'uso. `init` crea una nuova configurazione e rifiuta di sovrascriverne una esistente. `add-model` modifica il JSON e registra la tua dichiarazione che un modello sia un endpoint gratuito adatto e capace di usare strumenti; non la verifica tramite inferenza.

Il bundle applicativo e lo script di avvio contengono anche controlli `--verifica`. Controllano rispettivamente la struttura del bundle e la classificazione offline; non verificano credenziali, inferenza NVIDIA o l'intero avvio da Finder a Terminale.

<a id="it-sicurezza"></a>

### Credenziali, privacy e distribuzione

#### Caricamento della chiave

Il router risolve prima il percorso `api_key_file` della configurazione. Con il valore incluso, il file è `Dati/nvidia-api-key.txt`.

- Se il file esiste, il suo contenuto ha precedenza su `NVIDIA_API_KEY`.
- Un file vuoto o contenente il segnaposto esatto `INCOLLA_QUI_LA_TUA_CHIAVE_NVIDIA` interrompe l'avvio e richiede di modificarlo.
- Soltanto se il file manca, il router prova `NVIDIA_API_KEY` e poi una richiesta interattiva con input nascosto. Quest'ultima non salva la chiave.

La chiave è conservata **in testo semplice**, senza cifratura e senza utilizzare il Portachiavi di macOS. Per limitarne i permessi, dalla directory del pacchetto esegui:

```bash
chmod 600 'Dati/nvidia-api-key.txt'
```

Il gateway mantiene la chiave NVIDIA nel processo Python e la usa per autenticarsi al servizio remoto. Rimuove `NVIDIA_API_KEY` dall'ambiente passato a Claude Code. Nel pacchetto esaminato è presente una chiave NVIDIA riconoscibile, soltanto nel file di testo; il JSON contiene il nome del file, non il valore della chiave.

#### Gateway locale e flusso dei dati

Il gateway ascolta su `127.0.0.1`, con una porta temporanea e un token di sessione. Il launcher fornisce a Claude Code impostazioni temporanee del gateway; il relativo file contiene il token locale, non la chiave NVIDIA, e viene rimosso durante la normale pulizia.

Il gateway invia a NVIDIA il contenuto supportato della conversazione, inclusi il testo dei progetti e i risultati degli strumenti presenti nelle richieste. Il gateway locale **non** mantiene sul Mac i dati dell'inferenza. Claude Code e gli altri strumenti possono inoltre avere una propria attività di rete e propri archivi locali.

I log del router sono progettati per emettere metadati: modello scelto, tentativi, errori, durata e utilizzo comunicato dal fornitore. Questo non garantisce che cronologia del Terminale, trascrizioni di Claude Code, hook o altri strumenti siano privi di dati sensibili. Controlla il materiale prima di condividerlo.

#### Preparare una copia pubblica

1. Lavora su una copia separata del pacchetto.
2. Sostituisci la chiave reale con il segnaposto esatto indicato sopra, oppure elimina il file documentando la configurazione al primo utilizzo.
3. Escludi progetti privati, trascrizioni, log e altre credenziali.
4. Controlla lo ZIP effettivo della release oltre al repository. `.gitignore` non ripulisce gli archivi e non rimuove segreti già registrati nei commit.
5. Includi la licenza del progetto e gli avvisi delle dipendenze.

Una possibile esclusione per il repository è:

```gitignore
# Credenziali personali
**/Dati/nvidia-api-key.txt
```

Se serve, versiona un file di esempio separato. Adatta la regola alla struttura del repository. Se una chiave reale è stata pubblicata o inviata a un destinatario non previsto, revocala tramite NVIDIA: cancellare l'ultimo file non invalida le copie già condivise.

<a id="it-problemi"></a>

### Risoluzione dei problemi

| Problema | Controlli |
| --- | --- |
| `claude` non trovato | Installa la CLI; esegui `claude --version` e `claude doctor`. Confronta il percorso d'installazione con il PATH del launcher, soprattutto con i version manager. |
| Python assente o troppo vecchio | Verifica `/usr/bin/python3 --version`, non soltanto `python3 --version`. Un altro Python installato non soddisfa automaticamente il launcher. |
| `Dati/nim-router.json` mancante | Ripristina la struttura completa. Spostare soltanto la `.app` interrompe i percorsi relativi. |
| Chiave non caricata | Controlla percorso configurato, formato di testo semplice, nome e contenuto. Un file esistente vuoto o con il segnaposto impedisce il ricorso alla variabile d'ambiente. |
| NVIDIA `401` o `403` | Controlla validità della chiave e permessi dell'account. Questi errori non attivano il fallback. |
| NVIDIA `404` | Verifica ID del modello e disponibilità API. Il router non sostituisce automaticamente un ID non disponibile. |
| NVIDIA `429` | Attendi il cooldown indicato e controlla quote del fornitore e limiti RPM locali. Riavviare ripetutamente non cambia la quota NVIDIA. |
| `Nessun modello idoneo` | Controlla voci abilitate, livello, `free_endpoint`, `tools`, limiti di input/output e cooldown. |
| Budget delle richieste esaurito | Il gateway corrente ha raggiunto `max_calls_per_run`. Termina la sessione e controlla l'utilizzo prima di aprirne un'altra. |
| Blocco o payload non supportato | Usa testo e strumenti client supportati. Immagini, documenti e funzionalità Anthropic non implementate non possono essere inoltrati. |
| Risposta incompleta o timeout | Controlla modello e timeout. La richiesta interrotta non viene ripetuta dopo l'inizio dell'output semantico. |
| Funziona dal Terminale ma non da Finder | Controlla `/usr/bin/python3`, PATH dello script, controlli di sicurezza macOS e disponibilità del Terminale. Il percorso grafico richiede una verifica propria. |
| Serve un proxy aziendale | I client HTTP del router usano `trust_env=False`: le variabili d'ambiente standard dei proxy non vengono applicate automaticamente. Potrebbero servire modifiche al codice di rete. |

Per diagnosticare l'avvio tramite script, esegui `/bin/zsh './Terminal.command'` dalla directory del pacchetto e leggi l'errore mostrato.

Se macOS blocca l'app, verifica l'affidabilità della fonte prima di consentirla tramite i controlli di sicurezza del sistema. Le note incluse descrivono una **firma ad hoc**, che non equivale a una firma Apple Developer ID o alla notarizzazione. Modificare i permessi degli script non risolve problemi di firma o quarantena.

Se Claude Code si apre ma il routing fallisce, leggi il primo errore del gateway. Il launcher fornisce una configurazione temporanea tramite `--settings` per indirizzare la sessione al gateway e ripulisce alcune variabili ereditate dei fornitori. Impostazioni gestite, hook, plugin o modifiche di Claude Code possono comunque influire sulla compatibilità: l'app non verifica ogni configurazione esterna.

<a id="it-limiti"></a>

### Aggiornamenti, verifiche e limiti

- È un adattatore sperimentale, non un'implementazione completa delle API Anthropic.
- Supporta testo, definizioni di strumenti client personalizzati, chiamate agli strumenti e risultati testuali. Claude Code esegue gli strumenti client autorizzati; il gateway ne traduce i messaggi.
- Blocchi immagine/documento, formati di strumenti server e output strutturato Anthropic non sono supportati. I blocchi di ragionamento dell'assistente non vengono conservati come ragionamento portabile.
- La presenza di `VL` nel nome di un modello non aggiunge il supporto alle immagini all'adattatore.
- Limiti in byte e contesto in token sono diversi. Aumentare `client_context_tokens` non amplia la finestra di contesto del modello NVIDIA.
- I dati di utilizzo dei token possono mancare: gli zeri nella risposta non dimostrano assenza di utilizzo o costi.
- Disponibilità, prezzi, quote e comportamento dei modelli dipendono da NVIDIA e possono cambiare. I flag locali `free_endpoint` non promettono un servizio gratuito.
- Il bundle esaminato non vincola né certifica una specifica versione di Claude Code. Gli aggiornamenti della CLI possono introdurre richieste o comportamenti delle impostazioni incompatibili.
- Prima di aggiornare bundle o JSON, conserva una copia di sicurezza. Dopo un aggiornamento ricontrolla una breve richiesta testuale e un ciclo di chiamata/risultato di uno strumento: queste prove possono effettuare vere chiamate API.
- Quando sostituisci il pacchetto, conserva privatamente chiave e progetti; non copiarli in una release pubblica.

Questo README è stato confrontato con codice e configurazione del pacchetto fornito. La revisione della documentazione non ha avviato l'applicazione, utilizzato la chiave, effettuato inferenze NVIDIA, verificato il catalogo live dei modelli o accertato l'installazione su un Mac pulito. Le affermazioni di `LEGGIMI.txt` sui test precedenti sono note storiche, non nuove verifiche eseguite durante questa revisione.

<a id="it-licenza"></a>

### Indipendenza e licenza

NVIDIA Code è un progetto indipendente, non affiliato né ufficialmente supportato da Anthropic o NVIDIA. Nomi dei prodotti e marchi appartengono ai rispettivi proprietari.

**Nell'archivio esaminato non è stato trovato un file `LICENSE` a livello di progetto.** Non presumere una specifica licenza open source o un'autorizzazione alla ridistribuzione. Prima di pubblicare una release, chi mantiene il progetto deve aggiungere una licenza appropriata e conservare avvisi e condizioni delle librerie di terze parti incluse. Claude Code e i servizi NVIDIA restano soggetti alle rispettive condizioni.
