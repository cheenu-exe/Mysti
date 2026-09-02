# Phase 8: Advanced Features

## Phase Overview

Phase 8 adds the final layer of sophistication to MYSTI — features that transform it from a capable personal AI into a polished, production-ready system. This phase focuses on convenience, resilience, extensibility, and accessibility.

The major additions are:

- **Voice interface** — Speak to MYSTI and hear responses using your cloned voice (KikiVoice + Coqui TTS)
- **Multi-model routing** — Automatically use the right model for the right task, optimizing cost and quality
- **Backup and recovery** — Protect your knowledge base with encrypted backups and disaster recovery
- **Mobile access** — Interact with MYSTI from your phone via PWA
- **Notification system** — Get alerts for important events
- **Export and sharing** — Export your knowledge in various formats
- **Cross-platform** — Works on Windows and Linux

Phase 8 completes the MYSTI project, making it a fully-featured personal AI operating layer.

---

## Voice Clone Integration

### How It Works

MYSTI uses **Coqui TTS XTTS v2** locally to generate speech in your voice. Your KikiVoice clone (MP3) serves as the **one-time reference sample** — Coqui TTS learns your voice characteristics from it and generates new speech without needing KikiVoice again.

```
┌─────────────────────────────────────────────────────────┐
│  Voice Clone Pipeline                                    │
│                                                          │
│  ┌──────────────┐    ┌──────────────┐    ┌────────────┐ │
│  │ Your Voice   │───>│ KikiVoice    │───>│ Clone MP3  │ │
│  │ (recording)  │    │ (one-time)   │    │ (reference)│ │
│  └──────────────┘    └──────────────┘    └─────┬──────┘ │
│                                                 │        │
│                                    (one-time load)       │
│                                                 │        │
│                                                 ▼        │
│  ┌──────────────┐    ┌──────────────┐    ┌────────────┐ │
│  │ Generated    │<───│ Coqui TTS    │<───│ XTTS v2    │ │
│  │ WAV output   │    │ (local)      │    │ model      │ │
│  └──────────────┘    └──────────────┘    └────────────┘ │
│                                                          │
│  Coqui TTS uses your clone MP3 as reference for EVERY    │
│  generation. No internet needed after initial setup.     │
└─────────────────────────────────────────────────────────┘
```

### Voice Sample

- **Source:** `C:\Users\srini\Downloads\kikivoice-cloned-file-2026-09-01-23-50-48-7408.mp3`
- **Project location:** `src/mysti/voice/assets/clone_reference.mp3`
- **Used as:** Reference audio for Coqui XTTS v2 (loaded once, reused for all TTS)

### Voice Interface Features

- **Text-to-Speech:** Generate speech in your voice using Coqui XTTS v2 (your clone MP3 as reference)
- **Speech-to-Text:** Transcribe voice input using OpenAI Whisper (local)
- **Voice Sessions:** Full-duplex voice conversation with MYSTI
- **Multi-language:** XTTS v2 supports 17 languages with the same voice clone
- **Streaming:** Real-time audio streaming with <200ms latency on GPU
- **Fully Local:** No internet needed after initial model download

### Dependencies

- `coqui-tts` (v0.27.5+) — XTTS v2 model for voice cloning TTS
- `openai-whisper` — Local speech-to-text
- `sounddevice` — Audio playback
- `soundfile` — WAV file reading/writing
- `torch` — PyTorch backend for Coqui TTS

### Hardware Requirements

- **GPU recommended:** CUDA-enabled GPU for fast inference (<200ms latency)
- **CPU fallback:** Works on CPU but slower (~2-5s per sentence)
- **RAM:** 4GB minimum, 8GB recommended
- **Storage:** ~2GB for XTTS v2 model (downloaded on first use)

---

## Goals and Success Criteria

### Primary Goals

1. **Voice interface** — Speech-to-text input and text-to-speech output using your cloned voice (KikiVoice + Coqui TTS).
2. **Multi-model routing** — Automatically select the best model for each task.
3. **Backup and recovery** — Encrypted backups with automated scheduling and recovery procedures.
4. **Mobile access** — Progressive Web App (PWA) installable on phones.
5. **Notification system** — Alerts for daily briefings, security events, and important discoveries.
6. **Export and sharing** — Export memories, research, and knowledge in various formats.

### Success Criteria

You know Phase 8 is complete when:

- You can speak to MYSTI and receive spoken responses in YOUR cloned voice
- MYSTI automatically routes tasks to the optimal model
- Your knowledge base is automatically backed up and recoverable
- You can install MYSTI as a PWA on your phone
- You receive notifications for important events
- You can export your data in standard formats
- MYSTI works on both Windows and Linux

---

## Architecture

### What Phase 8 Adds

Phase 8 adds the finishing touches:

```
Existing Components:
├── Complete MYSTI Core (Phases 0-6)
├── Web Dashboard (Phase 7)

Phase 8 Adds:
├── Voice Interface (KikiVoice Clone + Coqui TTS)
│   ├── Speech-to-Text (Whisper, local)
│   ├── Text-to-Speech (Coqui XTTS v2, voice cloning)
│   │   └── Reference: KikiVoice cloned MP3
│   └── Voice Session Manager
├── Multi-Model Router
│   ├── Task Classifier
│   ├── Model Selector
│   └── Cost Optimizer
├── Backup System
│   ├── Encrypted Backup
│   ├── Incremental Backup
│   ├── Recovery Manager
│   └── Backup Scheduler
├── Notification System
│   ├── Desktop Notifications
│   ├── Email Notifications
│   └── Webhook Notifications
├── Export System
│   ├── Memory Export
│   ├── Research Export
│   └── Knowledge Graph Export
└── PWA (Progressive Web App)
    ├── Manifest
    ├── Service Worker
    └── Offline Support
```

---

## Data Models

### Voice Session Record

Tracks voice interaction sessions.

**Fields:**

- `id` — Unique identifier (UUID).
- `started_at` — When the voice session started.
- `ended_at` — When the voice session ended.
- `transcriptions` — List of transcribed messages.
- `tts_enabled` — Whether text-to-speech is enabled.
- `voice_clone_path` — Path to the reference voice file (KikiVoice clone).
- `language` — Detected or configured language.
- `accuracy_score` — Transcription accuracy (if measurable).

### Model Routing Record

Tracks how tasks are routed to models.

**Fields:**

- `id` — Unique identifier (UUID).
- `task_type` — What type of task was performed.
- `model_id` — Which model was used.
- `reason` — Why this model was selected.
- `cost` — Cost of the request.
- `quality_score` — Quality of the response.
- `recorded_at` — When the routing decision was made.

### Backup Record

Tracks backup operations.

**Fields:**

- `id` — Unique identifier (UUID).
- `backup_type` — Full or incremental.
- `encrypted_path` — Where the encrypted backup is stored.
- `size_bytes` — Size of the backup.
- `duration_seconds` — How long the backup took.
- `status` — Success or failure.
- `created_at` — When the backup was created.
- `retention_days` — How long the backup is kept.

### Notification Record

Tracks sent notifications.

**Fields:**

- `id` — Unique identifier (UUID).
- `type` — Notification type (briefing, security, reminder, discovery).
- `title` — Notification title.
- `message` — Notification content.
- `channel` — How it was sent (desktop, email, webhook).
- `sent_at` — When the notification was sent.
- `read` — Whether the notification was read.

---

## API Design

### Voice Endpoints

**Start voice session**

- Method: POST
- Path: /voice/start
- Request body: tts_enabled (boolean), language (optional)
- Response: session_id, websocket_url
- Behavior: Initiates a voice session using your pre-loaded clone reference and returns a WebSocket URL for streaming audio.

**Transcribe audio**

- Method: POST
- Path: /voice/transcribe
- Request body: audio_data (binary), session_id
- Response: transcribed_text, confidence
- Behavior: Sends audio data for transcription using local Whisper.

**Text-to-speech**

- Method: POST
- Path: /voice/speak
- Request body: text (string), speed (optional), language (optional)
- Response: audio_data (binary WAV)
- Behavior: Converts text to speech using Coqui XTTS v2 with your pre-loaded voice clone reference.

**Stop voice session**

- Method: POST
- Path: /voice/stop
- Request body: session_id
- Response: confirmation, session_summary

### Multi-Model Routing Endpoints

**Get routing decision**

- Method: POST
- Path: /routing/decide
- Request body: task_type, task_description, quality_requirement
- Response: model_id, reason, estimated_cost
- Behavior: Determines the best model for the task.

**Get routing statistics**

- Method: GET
- Path: /routing/stats
- Response: routing decisions by model, cost breakdown, quality metrics

**Update routing rules**

- Method: PUT
- Path: /routing/rules
- Request body: rules (JSON)
- Response: confirmation
- Behavior: Updates the routing rules for model selection.

### Backup Endpoints

**Trigger backup**

- Method: POST
- Path: /backup/trigger
- Request body: backup_type (full/incremental)
- Response: backup_id
- Behavior: Starts a backup operation.

**List backups**

- Method: GET
- Path: /backup/list
- Response: list of backups with metadata

**Restore from backup**

- Method: POST
- Path: /backup/restore/{backup_id}
- Response: confirmation
- Behavior: Restores the system from the specified backup.

**Delete backup**

- Method: DELETE
- Path: /backup/{backup_id}
- Response: confirmation

**Backup schedule**

- Method: PUT
- Path: /backup/schedule
- Request body: schedule (cron expression), retention_days
- Response: confirmation

### Notification Endpoints

**Get notifications**

- Method: GET
- Path: /notifications
- Query parameters: unread_only (boolean), type (optional), limit
- Response: list of notifications

**Mark notification as read**

- Method: PUT
- Path: /notifications/{notification_id}/read
- Response: confirmation

**Mark all as read**

- Method: PUT
- Path: /notifications/read-all
- Response: count of marked notifications

**Configure notifications**

- Method: PUT
- Path: /notifications/config
- Request body: config (desktop, email, webhook settings)
- Response: confirmation

**Send test notification**

- Method: POST
- Path: /notifications/test
- Request body: channel (desktop/email/webhook)
- Response: confirmation

### Export Endpoints

**Export memories**

- Method: GET
- Path: /export/memories
- Query parameters: format (json/csv/markdown), category (optional), encrypted (boolean)
- Response: exported file
- Behavior: Exports memories in the specified format.

**Export research**

- Method: GET
- Path: /export/research
- Query parameters: format (json/csv/markdown), date_range (optional)
- Response: exported file

**Export knowledge graph**

- Method: GET
- Path: /export/knowledge-graph
- Query parameters: format (json/graphml), depth (optional)
- Response: exported file

**Export all**

- Method: POST
- Path: /export/all
- Request body: format, encryption_password (optional)
- Response: exported archive
- Behavior: Creates a complete export of all MYSTI data.

---

## Implementation Details

### Step 1: Voice Interface (Coqui TTS + Your Clone Reference)

**Voice clone setup**

1. Copy your KikiVoice cloned MP3 to `src/mysti/voice/assets/clone_reference.mp3`
2. Convert MP3 to WAV format for Coqui TTS compatibility
3. Load reference audio once on TTS engine initialization
4. Coqui TTS extracts voice characteristics and reuses them for all generation

**Text-to-speech with voice cloning**

Use Coqui TTS XTTS v2 for voice-cloned TTS:
- Load the XTTS v2 model (~1.8GB, downloaded on first use)
- Use your KikiVoice clone as speaker reference (loaded once)
- Generate speech at 24kHz sampling rate
- Support streaming for real-time playback
- Support 17 languages with the same voice clone

```python
from TTS.api import TTS

# Initialize with voice clone reference (loaded once)
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to("cuda")
tts.tts_to_file(
    text="Hello, this is MYSTI speaking in your voice.",
    file_path="output.wav",
    speaker_wav="src/mysti/voice/assets/clone_reference.wav",
    language="en"
)
```

**Speech-to-text**

Use OpenAI Whisper for local STT:
- Download and run Whisper locally for privacy
- Support multiple languages
- Handle real-time transcription via WebSocket
- Provide confidence scores for transcriptions

**Voice session management**

Voice sessions work through WebSocket:
1. Browser captures audio from microphone
2. Audio is streamed to the server in chunks
3. Server transcribes audio using Whisper
4. Transcribed text is sent to MYSTI for processing
5. MYSTI's response is sent back
6. Response is spoken aloud using your cloned voice

### Step 2: Multi-Model Router

**Task classification**

Classify incoming tasks by type:
- Coding: code generation, debugging, explanation
- Reasoning: logic, math, analysis
- Writing: articles, summaries, creative content
- Research: information gathering, fact-checking
- General: conversation, simple questions

**Model selection**

For each task type, select the best model based on:
- Capability scores from the model registry
- Current cost of each model
- Latency requirements
- Quality requirements
- Budget constraints

**Routing rules**

Configure routing rules:
- Coding: DeepSeek V4 Flash (free) -> GPT-4 -> Claude
- Research: DeepSeek V4 Flash -> GPT-3.5 -> local
- Conversation: DeepSeek V4 Flash -> local model

**Cost optimization**

Track and optimize costs:
- Log the cost of each request
- Monitor total daily/weekly/monthly spending
- Alert when approaching budget limits
- Suggest cheaper alternatives for routine tasks

### Step 3: Backup System

**Encrypted backups**

Backups are encrypted using the same encryption infrastructure:
1. Export all database records
2. Export configuration
3. Export knowledge graph
4. Encrypt everything with the master key
5. Store the encrypted archive

**Incremental backups**

For efficiency, support incremental backups:
1. On first backup, create a full backup
2. On subsequent backups, only back up changes
3. Track which records have been modified
4. Store deltas alongside the full backup

**Backup storage**

Store backups in a configurable location:
- Local directory (default)
- External drive
- Cloud storage (optional, encrypted)
- Network location

**Recovery procedures**

Recovery process:
1. Select a backup to restore from
2. Decrypt the backup archive
3. Verify backup integrity
4. Restore database records
5. Restore configuration
6. Restore knowledge graph
7. Verify the restoration worked
8. Log the recovery event

**Backup scheduling**

Automate backups with a scheduler:
- Daily incremental backups
- Weekly full backups
- Configurable retention period
- Automatic cleanup of old backups

### Step 4: Mobile Access (PWA)

**Progressive Web App (PWA)**

Make the dashboard installable as a PWA:
- Add a web manifest
- Implement service workers for offline support
- Add to home screen capability
- Push notification support

**Mobile-specific features**

- Quick capture (store a memory from your phone)
- Voice input (use phone's microphone)
- Camera integration (photograph documents for OCR)
- Location awareness (optional, for context)

### Step 5: Notification System

**Notification types**

- **Daily briefing** — Summary of research findings
- **Security alerts** — Unauthorized access attempts, injection detection
- **Goal reminders** — Approaching deadlines, tasks due
- **Backup status** — Backup completed or failed
- **Model updates** — New models available, recommendations
- **System events** — Errors, warnings, milestones

**Notification channels**

- **Desktop notifications** — Browser notifications (via web API)
- **Email notifications** — Send emails to configured address
- **Webhook notifications** — POST to configured URLs
- **In-app notifications** — Badge and notification center in the dashboard

**Notification preferences**

Configure per notification type:
- Enable/disable each type
- Choose channel(s) for each type
- Set quiet hours (no notifications during certain times)
- Set priority levels

### Step 6: Export System

**Export formats**

- **JSON** — Complete data export with all fields
- **CSV** — Tabular format for spreadsheet import
- **Markdown** — Human-readable format for documentation
- **GraphML** — Graph format for knowledge graph visualization

**Export scope**

Export options:
- All data
- Memories only
- Research only
- Knowledge graph only
- Specific categories or date ranges
- Specific projects or goals

**Encrypted exports**

For sensitive data:
- Encrypt exports with a user-provided password
- Use the same encryption as the main database
- Provide a recovery key

---

## Dependencies

### New Dependencies for Phase 8

- **coqui-tts** (v0.27.5+) — XTTS v2 model for voice cloning TTS (uses KikiVoice clone as reference)
- **openai-whisper** — Local speech-to-text
- **sounddevice** — Audio playback
- **soundfile** — WAV file reading/writing
- **torch** — PyTorch backend for Coqui TTS
- **python-socketio** or **fastapi WebSocket** — Real-time voice streaming

### Existing Dependencies Used

- **cryptography** — Encrypting backups
- **APScheduler** — Backup scheduling
- **Next.js** — PWA support

### Platform Support

- **Windows** — Full support (Windows 10/11)
- **Linux** — Full support (Ubuntu, Arch, Fedora, etc.)
- **macOS** — Not supported (can be added later)

---

## Testing

### Unit Tests

**Voice tests**
- Test transcription accuracy with Whisper
- Test TTS output with Coqui XTTS v2 and voice clone reference
- Test voice session lifecycle
- Test voice clone reference loading (once)

**Routing tests**
- Test task classification accuracy
- Test model selection logic
- Test cost optimization

**Backup tests**
- Test full backup creation
- Test incremental backup creation
- Test backup restoration
- Test backup encryption

**Notification tests**
- Test notification delivery
- Test notification preferences
- Test quiet hours

### Integration Tests

**End-to-end voice flow**
- Start voice session → speak → transcribe → process → respond → speak back in cloned voice

**End-to-end backup flow**
- Trigger backup → verify encrypted archive → restore → verify data integrity

### Manual Testing

After Phase 8 is complete:
- Test voice input and output with your cloned voice
- Verify model routing works correctly
- Create and restore a backup
- Receive a notification on your phone
- Export your data and verify the export
- Install MYSTI as PWA on your phone

---

## Edge Cases

### Voice Quality Issues

If voice cloning quality is poor:
- Ensure reference audio is clean (no background noise)
- Use 6-20 seconds of clear speech for reference
- Adjust temperature parameter (lower = more stable)
- Try different XTTS v2 model versions
- Provide visual feedback for detected speech
- Allow manual correction of transcriptions

### Model Routing Errors

If the wrong model is selected:
- Allow manual override
- Track routing accuracy over time
- Adjust routing rules based on feedback

### Backup Failures

If a backup fails:
- Log the failure with details
- Retry the backup
- Alert the user if retries fail
- Maintain the last good backup

### Mobile Performance

If the dashboard is slow on mobile:
- Optimize bundle size
- Implement lazy loading
- Use server-side rendering where appropriate
- Reduce data transfer

---

## Deliverables

When Phase 8 is complete, you will have:

1. **Voice interface** — Speak to MYSTI and hear responses in YOUR cloned voice (KikiVoice + Coqui TTS).

2. **Multi-model routing** — Automatic model selection for cost optimization.

3. **Backup system** — Encrypted, automated backups with recovery.

4. **Mobile access** — PWA installable on phones with offline support.

5. **Notification system** — Alerts for important events across channels.

6. **Export system** — Export your data in multiple formats.

---

## Project Completion

With Phase 8 complete, MYSTI is a fully-featured personal AI operating layer:

- **Encrypted memory** that remembers everything about you
- **Research agent** that discovers what matters to you
- **Security layer** that keeps you in control
- **Tool system** that can interact with your computer
- **Knowledge graph** that connects your information
- **Self-improvement** that helps MYSTI get better over time
- **Web interface** that makes everything accessible
- **Voice interface** that speaks with YOUR cloned voice
- **Advanced features** that make MYSTI convenient and resilient
- **Cross-platform** — Works on Windows and Linux

The project is now ready for daily use as your personal AI assistant.

---

*Phase 8 completes MYSTI — your private, secure, intelligent personal AI with YOUR voice, running on YOUR platform.*
