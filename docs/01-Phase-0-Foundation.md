# Phase 0: Foundation

## Phase Overview

Phase 0 establishes the foundational infrastructure for MYSTI. This phase creates the project scaffold, sets up the remote encrypted storage layer, implements encryption for personal data, manages encryption keys through the operating system's keystore, and provides a basic command-line interface for interacting with the system.

By the end of Phase 0, you will have a working system where you can store personal information encrypted locally and uploaded to remote storage, retrieve it through a chat interface, and verify that the encryption actually works. This is the minimum viable product — everything else in MYSTI builds on top of this.

The philosophy of Phase 0 is simple: **get the core working before adding complexity.** Do not worry about research agents, permission systems, or web interfaces yet. Focus on making encrypted memory storage reliable and secure.

---

## Goals and Success Criteria

### Primary Goals

1. **Project scaffold** — A well-organized Python project with FastAPI backend, remote storage interface, and development environment.
2. **Remote storage interface** — Pluggable storage backend for encrypted object storage (S3, Backblaze B2, Cloudflare R2).
3. **Encryption** — AES-256-GCM encryption for all personal data, with key hierarchy and rotation support. Encryption happens locally before upload.
4. **Key management** — OS keystore integration so encryption keys are never stored alongside encrypted data. Master key NEVER leaves your Arch machine.
5. **Local cache** — RAM-only ephemeral cache (100-256 MB) with TTL/LRU expiration. No permanent plaintext on disk.
6. **Memory service** — API endpoints for storing, retrieving, searching, and deleting encrypted records.
7. **CLI interface** — A command-line chat where you can interact with MYSTI and test all functionality.

### Success Criteria

You know Phase 0 is complete when:

- You can start the application and have a text-based conversation
- You can ask MYSTI to remember something, and it encrypts locally and uploads to remote storage
- You can ask MYSTI to recall something, and it downloads, decrypts, and returns the result
- Remote storage contains only encrypted ciphertext (no plaintext personal data)
- The encryption key is stored in your OS credential manager, not in a file
- The master key never leaves your Arch machine
- Local cache is RAM-only and disappears on shutdown
- All operations are logged for debugging
- The basic conversation has context from previous exchanges

---

## Architecture

### System Boundaries for Phase 0

Phase 0 covers a narrow slice of the full MYSTI architecture:

```
┌─────────────────────────┐
│       CLI Interface     │
└────────────┬────────────┘
             │
┌────────────▼────────────┐
│     Memory Service      │
│  (FastAPI + Endpoints)  │
└────────────┬────────────┘
             │
┌────────────▼────────────┐
│   Encryption Layer      │
│  (AES-256-GCM)          │
└────────────┬────────────┘
             │
┌────────────▼────────────┐
│   Key Management        │
│  (OS Keystore)          │
│  Master key NEVER       │
│  leaves Arch machine    │
└────────────┬────────────┘
             │
┌────────────▼────────────┐
│   Local RAM Cache       │
│  (100-256 MB, TTL/LRU) │
│  Disappears on shutdown │
└────────────┬────────────┘
             │
┌────────────▼────────────┐
│   Remote Storage        │
│  (S3/Backblaze/R2)     │
│  Encrypted blobs only   │
└─────────────────────────┘
```

### What Phase 0 Does NOT Cover

- Research agents (Phase 2)
- Permission system (Phase 3)
- Tool integration (Phase 4)
- Web dashboard (Phase 7)
- Voice interface (Phase 8)

This narrow scope is intentional. Building the encryption and memory layer first ensures that everything added later is built on a secure foundation.

---

## Data Models

### Memory Record

The central data structure for all personal information stored in MYSTI.

**Fields:**

- `id` — Unique identifier (UUID). Never reused, even after deletion.
- `category` — Classification of the record (personal, projects, relationships, technical, research, ideas).
- `encrypted_data` — The actual content, encrypted as a binary blob. Stored remotely, never in plaintext locally.
- `metadata` — Encrypted JSON containing non-sensitive information about the record: creation timestamp, last modified timestamp, data version, content hash for integrity verification.
- `created_at` — When the record was first created (stored in plaintext for indexing, but not personal content).
- `updated_at` — When the record was last modified.
- `deleted_at` — Soft deletion timestamp. Records are not immediately purged; they are marked as deleted and can be recovered within a grace period.
- `remote_path` — The path/key in remote storage where the encrypted blob is stored.

**Design Decisions:**

Using UUIDs instead of auto-incrementing integers prevents an observer from guessing how many records exist or in what order they were created. Soft deletion allows recovery from mistakes. The metadata is stored separately from the encrypted data to enable filtering and sorting without decryption. Remote storage is used instead of a local database to ensure plaintext never persists on disk.

### Conversation Record

Stores individual messages within a conversation session.

**Fields:**

- `id` — Unique identifier (UUID).
- `session_id` — Groups messages into conversations. All messages with the same session_id belong to the same conversation.
- `role` — Who said this: "user" (you) or "assistant" (MYSTI).
- `encrypted_content` — The message content, encrypted. Messages are encrypted individually so that retrieving a single message does not require decrypting the entire conversation.
- `timestamp` — When the message was sent.
- `metadata` — Encrypted JSON with optional information: token count, model used, processing time.

**Design Decisions:**

Encrypting each message individually provides finer-grained access control and reduces the amount of data that needs to be decrypted for any single retrieval. The session_id enables conversation threading without exposing message content.

### Audit Log Record

Tracks every significant action within MYSTI for accountability and debugging.

**Fields:**

- `id` — Unique identifier (UUID).
- `timestamp` — When the action occurred.
- `action` — What was done (memory.store, memory.retrieve, memory.delete, conversation.start, etc.).
- `resource` — What was affected (record ID, session ID, etc.).
- `status` — Outcome: success, blocked, failed, error.
- `reason` — Human-readable explanation of why the action was taken or why it was blocked.
- `metadata` — Additional context (error details, request parameters, etc.).

**Design Decisions:**

The audit log is append-only. Records are never modified or deleted. This provides a tamper-evident trail of all system activity. The log itself should be stored in an encrypted database for consistency, though the log entries do not contain personal data — they reference resources by UUID, not by content.

### Configuration Record

Stores system configuration and user preferences.

**Fields:**

- `key` — Configuration key (string, unique).
- `encrypted_value` — Configuration value, encrypted. Some configuration is sensitive (API keys, model endpoints).
- `category` — Grouping for configuration (general, ai, security, research).
- `updated_at` — When the configuration was last modified.

**Design Decisions:**

Storing configuration in the same encrypted database as personal data ensures that sensitive settings (like API keys) are protected by the same encryption infrastructure. Non-sensitive configuration could be stored in plaintext for easier debugging, but consistency is simpler.

---

## API Design

### Memory Endpoints

**Store a memory record**

- Method: POST
- Path: /memory/store
- Request body: category (string), content (string — plaintext to be encrypted), optional metadata (JSON)
- Response: record ID, created timestamp
- Behavior: Encrypts the content locally using the category-specific key, uploads encrypted blob to remote storage, creates an audit log entry, returns the record ID.

**Retrieve a memory record**

- Method: GET
- Path: /memory/retrieve/{record_id}
- Response: record ID, category, decrypted content, metadata, timestamps
- Behavior: Downloads the encrypted record from remote storage, decrypts it locally using the category key, returns the plaintext. Creates an audit log entry. Plaintext exists only transiently in RAM.

**Search memory records**

- Method: POST
- Path: /memory/search
- Request body: query (string), optional category filter, optional date range, optional limit
- Response: list of matching records (ID, category, preview, relevance score)
- Behavior: Searches across encrypted records. In Phase 0, this is keyword-based (requires decrypting metadata or maintaining a search index). Semantic search is added in Phase 1.

**Delete a memory record**

- Method: DELETE
- Path: /memory/{record_id}
- Behavior: Soft-delete. Sets deleted_at timestamp. Record can be recovered within the grace period (default: 30 days).

**List categories**

- Method: GET
- Path: /memory/categories
- Response: list of category names with record counts

### Conversation Endpoints

**Start a new conversation**

- Method: POST
- Path: /conversation/start
- Response: session ID
- Behavior: Creates a new conversation session.

**Send a message**

- Method: POST
- Path: /conversation/{session_id}/message
- Request body: content (string — plaintext to be encrypted)
- Response: the user's message (stored), MYSTI's response (generated)
- Behavior: Encrypts and stores the user's message, sends the conversation context to the LLM, receives a response, encrypts and stores the response, returns both.

**Retrieve conversation history**

- Method: GET
- Path: /conversation/{session_id}/messages
- Query parameters: limit (default 50), offset
- Response: list of messages (role, content, timestamp)
- Behavior: Fetches and decrypts messages for the specified session.

### Health and Status Endpoints

**Health check**

- Method: GET
- Path: /health
- Response: status (ok/error), database connectivity, encryption status

**System status**

- Method: GET
- Path: /status
- Response: current mode, memory record count, conversation count, last activity timestamp

---

## Implementation Details

### Step 1: Project Initialization

**Create the project directory structure**

The project should follow a standard Python layout:

- `pyproject.toml` — Project metadata, dependencies, build configuration
- `src/mysti/` — Main source package
- `src/mysti/core/` — Core agent logic
- `src/mysti/memory/` — Memory and encryption
- `src/mysti/api/` — FastAPI application
- `src/mysti/database/` — SQLAlchemy models and migrations
- `src/mysti/config/` — Configuration management
- `tests/` — Test suite
- `docker/` — Docker configurations
- `.env.example` — Template for environment variables

**Initialize Git repository**

Set up version control from the start. Use a `.gitignore` that excludes:
- `.env` (contains secrets)
- `*.db` (database files)
- `__pycache__/`
- `.venv/`
- `dist/`
- `*.egg-info/`

**Set up development environment**

Create a virtual environment and install core dependencies. The initial dependency list includes:
- FastAPI and Uvicorn (web framework and ASGI server)
- SQLAlchemy and Alembic (database and migrations)
- cryptography (encryption library)
- pydantic (data validation)
- python-dotenv (environment variable management)
- python-keyring (OS keystore integration)
- click or typer (CLI interface)
- rich (terminal formatting)
- pytest and httpx (testing)

### Step 2: Configuration Management

**Environment variables**

Define the following configuration through environment variables:

- `MYSTI_STORAGE_PROVIDER` — Which storage provider to use (s3, backblaze, r2, local)
- `MYSTI_STORAGE_BUCKET` — Storage bucket name
- `MYSTI_STORAGE_ENDPOINT` — Storage endpoint URL
- `MYSTI_STORAGE_ACCESS_KEY` — Storage access key
- `MYSTI_STORAGE_SECRET_KEY` — Storage secret key
- `MYSTI_CACHE_MAX_SIZE` — Maximum local cache size in MB (default: 256)
- `MYSTI_CACHE_TTL` — Cache entry TTL in seconds (default: 86400)
- `MYSTI_ENCRYPTION_ALGORITHM` — Encryption algorithm (default: AES-256-GCM)
- `MYSTI_LOG_LEVEL` — Logging verbosity (default: INFO)
- `MYSTI_API_HOST` — API server host (default: 127.0.0.1)
- `MYSTI_API_PORT` — API server port (default: 8000)
- `MYSTI_LLM_PROVIDER` — Which LLM to use (openai, anthropic, local)
- `MYSTI_LLM_MODEL` — Model name (default depends on provider)
- `MYSTI_LLM_API_KEY` — API key for cloud LLM providers

**Configuration loading**

Create a configuration module that:
1. Loads `.env` file if present
2. Reads environment variables
3. Validates all required variables are present
4. Provides defaults for optional variables
5. Exposes a singleton configuration object

### Step 3: Storage Layer

**Remote storage interface**

Instead of a local database, MYSTI uses remote object storage for persistent data. The storage interface is abstract to support multiple providers:

- **S3** — AWS Simple Storage Service
- **Backblaze B2** — Cost-effective cloud storage
- **Cloudflare R2** — S3-compatible with no egress fees
- **MinIO** — Self-hosted S3-compatible storage
- **Local** — Local filesystem for development

**Storage abstraction**

Define a storage interface with methods:
- `put(key, data)` — Upload encrypted data to remote storage
- `get(key)` — Download encrypted data from remote storage
- `delete(key)` — Remove data from remote storage
- `list(prefix)` — List objects with a given prefix
- `exists(key)` — Check if an object exists

**Local cache**

A RAM-only cache holds recently accessed items:
- Maximum size: configurable (default 256 MB)
- Eviction: LRU (Least Recently Used)
- TTL: configurable (default 24 hours)
- Encryption: cached items remain encrypted
- Persistence: none — cache disappears on shutdown

**Cache behavior**

When storing:
1. Encrypt the data locally
2. Upload encrypted blob to remote storage
3. Optionally cache the encrypted blob in RAM

When retrieving:
1. Check RAM cache for the encrypted blob
2. If cache hit: decrypt and return
3. If cache miss: download from remote storage, cache encrypted blob, decrypt and return
4. Plaintext exists only transiently during decryption

**Remote storage structure**

Organize remote storage as:
```
mysti/
├── memories/
│   ├── {category}/
│   │   ├── {uuid}.enc
│   │   └── {uuid}.enc
│   └── index.enc
├── conversations/
│   ├── {session_id}/
│   │   ├── {message_uuid}.enc
│   │   └── {message_uuid}.enc
│   └── index.enc
├── research/
│   ├── {item_uuid}.enc
│   └── index.enc
└── metadata/
    ├── categories.enc
    └── config.enc
```

### Step 4: Encryption Layer

**Encryption functions**

Implement the core encryption module:

- `generate_key()` — Generate a new AES-256 key (32 bytes random)
- `encrypt(key, plaintext)` — Encrypt plaintext using AES-256-GCM, return ciphertext with nonce and tag
- `decrypt(key, ciphertext)` — Decrypt ciphertext, verify tag, return plaintext
- `hash_data(data)` — SHA-256 hash for integrity verification

**AES-256-GCM specifics**

AES-256-GCM is an authenticated encryption mode that provides:
- Confidentiality (encryption)
- Integrity (authentication tag)
- Nonce-based (each encryption uses a unique nonce)

The nonce should be 12 bytes (96 bits), generated randomly for each encryption operation. The authentication tag is 16 bytes (128 bits) and is appended to the ciphertext. The stored format should be: nonce (12 bytes) + ciphertext + tag (16 bytes).

**Key hierarchy**

Implement a key hierarchy where:
- A master key (stored in OS keystore, NEVER uploaded) encrypts category keys
- Category keys encrypt individual records
- Each category has its own key (personal, projects, relationships, technical, research, ideas)
- Category keys are generated randomly on first use
- The master key is never stored in the remote storage

This hierarchy means that compromising one category key only exposes that category's data, not everything.

**Encryption flow**

```
Plaintext memory
       │
       ▼
Category key encrypts data
       │
       ▼
Master key encrypts category key (stored locally only)
       │
       ▼
Encrypted blob uploaded to remote storage
       │
       ▼
Remote storage sees only ciphertext
```

**Key rotation support**

Implement versioned keys so that:
- Old keys can be retained for decryption
- New encryptions use the latest key
- A rotation function can re-encrypt all records in a category with a new key
- Key versions are tracked to know which key was used for each record

### Step 5: Key Management

**OS keystore integration**

Use the Python `keyring` library to interface with your operating system's credential store:

- On Linux: SecretService (GNOME Keyring, KDE Wallet)
- On macOS: Keychain
- On Windows: Windows Credential Manager

The integration should:
- Store the master key under a unique service name ("mysti-master-key")
- Retrieve the key on demand (never cache it in memory longer than needed)
- Handle the case where the key doesn't exist (first run — generate and store)
- Handle the case where the keyring is locked (prompt for unlock)

**First-run setup**

When MYSTI starts for the first time:
1. Check if the master key exists in the OS keystore
2. If not, generate a new master key
3. Store the master key in the OS keystore
4. Generate category keys and encrypt them with the master key
5. Store encrypted category keys in remote storage
6. Confirm setup is complete

**Key retrieval flow**

When the AI needs to decrypt data:
1. The AI requests data through the Memory Service API
2. The Memory Service determines which category key is needed
3. The Memory Service retrieves the encrypted category key from remote storage
4. The Memory Service requests the master key from the OS keystore
5. The Memory Service decrypts the category key using the master key
6. The Memory Service decrypts the data using the category key
7. The Memory Service returns the plaintext to the AI
8. The master key and category key are cleared from memory as soon as possible

The AI process never has direct access to either the master key or the category keys. It only sees plaintext through the Memory Service API.

**Key backup**

The master key should have an offline backup:
- Store on an encrypted USB drive
- Store in a secure location you control
- Never store in remote storage
- Never store in source code
- Never store in environment variables

If you lose the master key, your encrypted memories are unrecoverable.

### Step 6: Memory Service

**Core memory operations**

Implement the Memory Service as a Python class with methods:

- `store(category, content, metadata)` — Encrypt locally and upload to remote storage
- `retrieve(record_id)` — Download from remote storage, decrypt locally, return plaintext
- `search(query, category, date_range, limit)` — Search across records (metadata-based in Phase 0)
- `delete(record_id)` — Soft-delete a record
- `list_categories()` — List all categories with counts

**Storage flow**

Storing a memory:
1. Receive plaintext content from the AI
2. Generate a UUID for the record
3. Encrypt the content using the category key
4. Create encrypted metadata
5. Upload the encrypted blob to remote storage
6. Update the local search index (if applicable)
7. Return the record ID to the AI

Retrieving a memory:
1. Receive the record ID from the AI
2. Check RAM cache for the encrypted blob
3. If cache miss: download from remote storage
4. Cache the encrypted blob in RAM
5. Decrypt the content using the category key
6. Return the plaintext to the AI
7. Clear plaintext from memory as soon as possible

**Conversation management**

Implement conversation handling:

- `start_session()` — Create a new conversation session
- `add_message(session_id, role, content)` — Add a message to a conversation
- `get_messages(session_id, limit, offset)` — Retrieve conversation history
- `build_context(session_id, max_tokens)` — Build LLM context from conversation history

**Audit logging**

Every operation through the Memory Service should create an audit log entry with:
- Timestamp
- Action performed
- Resource affected
- Outcome (success/failure)
- Reason (if applicable)

### Step 7: LLM Integration

**Model abstraction**

Create a simple abstraction layer for LLM calls:

- `send_message(messages, model)` — Send a list of messages to the LLM, return the response
- Support multiple providers: OpenAI, Anthropic, local models (Ollama)
- Handle rate limiting, retries, and error responses
- Log all LLM interactions for debugging

**Conversation context**

Build a context window management system:

- Load recent conversation history (last N messages)
- Include a system prompt that defines MYSTI's personality and capabilities
- Truncate or summarize if context exceeds model limits
- Include relevant memory records in context (if available)

**System prompt**

Define MYSTI's initial system prompt:

- Identity: MYSTI, a personal AI assistant
- Capabilities: Can remember things, recall information, have conversations
- Limitations: Cannot access the user's system (Passive Mode only in Phase 0)
- Personality: Helpful, direct, slightly technical, remembers user preferences
- Instructions: Always be honest, ask for clarification when needed, remember important details

### Step 8: CLI Interface

**Command structure**

Build the CLI using Click or Typer:

- `mysti start` — Start the interactive chat session
- `mysti store <category> <content>` — Store a memory directly
- `mysti recall <query>` — Search and display matching memories
- `mysti history` — Show recent conversation sessions
- `mysti status` — Show system status (record count, last activity, etc.)
- `mysti config` — View or modify configuration

**Interactive chat mode**

The main interface is a REPL (Read-Eval-Print Loop):

1. Display a prompt (e.g., "you > ")
2. Read user input
3. If it's a command (starts with /), handle it directly
4. Otherwise, send to the LLM with conversation context
5. Display the response
6. Store both user message and assistant response
7. Repeat

**Built-in commands**

During chat, you can use:
- `/store <category> <content>` — Store a memory
- `/recall <query>` — Search memories
- `/categories` — List memory categories
- `/history` — Show recent conversations
- `/clear` — Clear current conversation context
- `/status` — Show system status
- `/quit` or `/exit` — Exit the application

**Terminal formatting**

Use the `rich` library for:
- Colored output
- Formatted tables for search results
- Markdown rendering for responses
- Progress indicators for long operations
- Syntax highlighting for code blocks

---

## Dependencies

### Core Dependencies

- **FastAPI** — Web framework for the API layer
- **Uvicorn** — ASGI server to run FastAPI
- **cryptography** — AES-256-GCM encryption
- **pydantic** — Data validation and serialization
- **python-dotenv** — Environment variable loading
- **python-keyring** — OS keystore integration
- **boto3** — S3-compatible storage client
- **click** or **typer** — CLI framework
- **rich** — Terminal formatting and markdown rendering

### Development Dependencies

- **pytest** — Test framework
- **httpx** — HTTP client for testing FastAPI endpoints
- **pytest-asyncio** — Async test support
- **black** — Code formatting
- **ruff** — Linting
- **mypy** — Type checking

### Optional Dependencies

- **sentence-transformers** — Local embedding model (for semantic search in Phase 1)
- **ollama** — Local LLM management (can be added later)

---

## Testing

### Unit Tests

**Encryption tests**

- Test that encrypt then decrypt returns the original plaintext
- Test that different encryptions of the same plaintext produce different ciphertexts (random nonce)
- Test that tampering with ciphertext causes decryption failure
- Test that wrong keys cause decryption failure
- Test key generation produces valid keys

**Storage tests**

- Test uploading encrypted data to remote storage
- Test downloading encrypted data from remote storage
- Test that remote storage contains only ciphertext
- Test cache hit and miss behavior
- Test cache TTL expiration
- test cache LRU eviction

**Memory service tests**

- Test storing and retrieving a record through the API
- Test that stored data is encrypted before upload
- Test search returns correct results
- Test deletion marks records as deleted
- Test audit log entries are created

**Key management tests**

- Test key generation and storage
- Test key retrieval from OS keystore
- Test key hierarchy (master key encrypts category keys)
- Test key rotation

### Integration Tests

**API endpoint tests**

- Test each endpoint with valid inputs
- Test each endpoint with invalid inputs
- Test authentication and authorization (if applicable)
- Test error responses

**CLI tests**

- Test command parsing
- Test interactive chat flow
- Test built-in commands
- Test graceful exit

### Manual Testing Checklist

After building Phase 0, manually verify:

- Start the application and confirm it initializes correctly
- Store a memory and confirm it's encrypted and uploaded to remote storage
- Retrieve a memory and confirm it downloads and decrypts correctly
- Verify remote storage contains no plaintext personal data
- Verify the master key is in your OS keystore, not in a file
- Verify the master key is never sent to remote storage
- Verify local cache is RAM-only and disappears on restart
- Have a multi-turn conversation and confirm context is maintained
- Restart the application and confirm previous memories are accessible

---

## Edge Cases

### First Run

When MYSTI starts for the first time:
- No remote storage configured → prompt for storage credentials
- No master key exists → generate and store in OS keystore
- No category keys exist → generate and encrypt them
- No configuration exists → use defaults
- No conversations exist → start fresh

Handle this gracefully with clear messages about what's happening.

### Keyring Unavailable

If the OS keystore is not available (e.g., running in a container, headless server):
- Fall back to an encrypted key file with passphrase prompt
- Warn the user that this is less secure than OS keystore
- Provide instructions for setting up the keystore

### Remote Storage Unavailable

If the remote storage is unreachable:
- Check RAM cache for the requested data
- If cache hit: serve from cache (with warning about stale data)
- If cache miss: return an error with clear message
- Log the connectivity issue
- Retry with exponential backoff

### Cache Exhaustion

If the local RAM cache is full:
- Evict least recently used entries
- Evict entries that have exceeded their TTL
- Log cache eviction events
- Consider warning the user if eviction rate is high

### Encryption Failures

If encryption or decryption fails:
- Log the failure with full context
- Return a clear error message to the user
- Do not expose raw encryption errors (they might contain sensitive information)
- Suggest possible causes (wrong key, corrupted data)

### Network Latency

If remote storage is slow:
- Use the local cache for recent items
- Show loading indicators for remote operations
- Consider prefetching likely-needed data
- Log slow operations for monitoring

### Large Records

If a user tries to store very large content:
- Set a reasonable maximum record size (e.g., 1MB)
- Warn the user if they're approaching the limit
- Reject records that exceed the limit with a clear message

### Conversation Context Overflow

If a conversation grows beyond the LLM's context window:
- Summarize older messages
- Keep the most recent messages in full
- Include the summary in the context
- Inform the user that summarization occurred

---

## Deliverables

When Phase 0 is complete, you will have:

1. **A working Python project** with proper structure, dependencies, and configuration.

2. **Remote encrypted storage** that stores all personal information as ciphertext. The remote provider never sees plaintext.

3. **OS keystore integration** where the master encryption key lives in your system's credential manager, not in any file. The master key never leaves your Arch machine.

4. **A key hierarchy** where the master key protects category keys, which protect individual records.

5. **A local RAM cache** that holds recently accessed items (100-256 MB) with TTL/LRU expiration. No permanent plaintext on disk.

6. **A Memory Service API** that handles storing, retrieving, searching, and deleting encrypted records with remote storage.

7. **A basic LLM integration** that maintains conversation context and generates responses.

8. **A CLI interface** where you can chat with MYSTI, store memories, recall information, and manage the system.

9. **A test suite** that verifies encryption, storage operations, and API endpoints.

10. **An audit log** that tracks all system activity for debugging and accountability.

---

## What Comes Next

After Phase 0, you will move to **Phase 1: Memory Intelligence**, which adds:
- Semantic search using vector embeddings
- Memory categories with different access rules
- Conversation summarization
- Memory consolidation and contradiction detection

But first, make sure Phase 0 is solid. A flawed foundation will cause problems in every subsequent phase.

---

*Phase 0 establishes the secure remote-memory, local-cache foundation that everything else in MYSTI is built upon.*
