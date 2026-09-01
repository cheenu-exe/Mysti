# MYSTI

A private, encrypted personal AI operating layer. **Phase 0 (Foundation)** implements
the remote-memory, local-cache core: client-side encryption, pluggable object
storage, an encrypted RAM cache, a memory service, a chat CLI, and an HTTP API.

## Architecture (Phase 0)

```
CLI / FastAPI
      |
MemoryService / ConversationStore   <- plaintext exists only here, transiently
      |
envelope (AES-256-GCM, per-record keys, AAD-bound)
      |
KeyManager  (master key in OS keystore; wrapped category keys remotely)
      |
StorageBackend (local | S3-compatible)  <- ciphertext only
```

- **Key hierarchy:** master key -> category keys -> per-record data keys.
- **Envelope:** `MYST | version | key_version | wrapped_key | nonce | ct | tag`,
  with record id + category bound as AAD (anti ciphertext-swapping).
- **Cache:** RAM-only, ciphertext-only, LRU + TTL, bounded by `MYSTI_CACHE_MAX_MB`.
- **Audit log:** local, append-only, hash-chained JSONL (`data_dir/audit.jsonl`).

## Quickstart

```bash
# Python 3.11+
python -m venv .venv
.venv\Scripts\activate       # Windows   (source .venv/bin/activate on Linux)
pip install -e ".[dev]"

copy .env.example .env       # then edit; never commit .env
mysti init                   # first-run: creates master key + key hierarchy
mysti store personal "my favourite editor is vim"
mysti recall vim
mysti status
mysti start                  # interactive chat REPL (/store /recall /quit ...)
mysti serve                  # HTTP API on 127.0.0.1:8000
```

No paid services are required: `MYSTI_STORAGE_PROVIDER=local` uses the local
filesystem (ciphertext only) and `MYSTI_LLM_PROVIDER=none` disables chat. To
enable chat, point MYSTI at any provider, e.g. a local Ollama server:

```
MYSTI_LLM_PROVIDER=ollama
MYSTI_LLM_BASE_URL=http://localhost:11434/v1
MYSTI_LLM_MODEL=llama3.1
```

## Configuration

All settings come from `MYSTI_*` environment variables (see `.env.example`).
Never store secrets in the repository; `.env` is gitignored.

## Tests

```bash
pytest                 # full suite (hermetic: local storage + in-memory keystore + mocked HTTP)
ruff check src tests
black --check src tests
mypy src
```

## Security notes

- The master key lives only in your OS keystore (`keyring`). Back it up
  offline; losing it means losing your data.
- Plaintext never touches disk: the local "remote" storage backend stores
  ciphertext only, and the cache is RAM-only.
- Set `MYSTI_API_TOKEN` to require bearer auth on the HTTP API.
- Phase 0 is Passive Mode only: nothing executes on your machine.

Phase 0 implements only the Foundation phase; later phases (memory
intelligence, research agent, permissions, tools, UI) are not included.
