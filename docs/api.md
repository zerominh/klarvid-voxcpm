# Klarvid VoxCPM TTS — API integration

Machine-readable spec: [openapi.yaml](openapi.yaml). Live docs when the server is up: `http://127.0.0.1:8000/docs` and `http://127.0.0.1:8000/openapi.json`.

This document is the contract for clients and coding agents. Follow it exactly. Do not assume OpenAI `/v1/audio/speech` compatibility.

## Agent rules

1. Base URL default: `http://127.0.0.1:8000`. No auth, no API key.
2. One GPU: at most one synthesis runs at a time. If busy, wait then retry on **503**.
3. TTS/clone success bodies are **raw WAV bytes**, not JSON, not base64. `/health` and `/v1/voices*` are JSON.
4. Audio: **PCM16 little-endian, mono, 48 kHz** (`sample_rate` from `/health` if unsure).
5. Voice design is **not** a separate field. Put the description in parentheses at the start of `text`.
6. Do not send parallel TTS requests from the same pipeline unless you handle 503 + retry.
7. Text longer than ~400 characters is split on sentence boundaries server-side; keep scripts under a few sentences per request when possible.
8. Saved voices: `POST /v1/voices` with sample audio **and** the exact transcript (`prompt_text`). Later TTS uses only `voice_id` — do not re-upload the clip.
9. One-shot clone (`POST /v1/clone`) still requires the file every time. Prefer `/v1/voices` + `voice_id` for reuse.
10. Clone/register clips should be **3–10 seconds**. Do not set `denoise=true` on an 8 GB GPU unless the operator enabled the denoiser.

## Concurrency

| Situation | HTTP | Client action |
|-----------|------|----------------|
| GPU free | 200 + WAV | Save or play the body |
| GPU busy > `GPU_LOCK_TIMEOUT` (default 180s) | 503 | Retry with backoff (5–15s), max 3–5 times |
| Bad request | 400 / 422 | Fix payload; do not retry blindly |
| Unknown `voice_id` | 404 | Create the voice first or list `GET /v1/voices` |
| Server/OOM | 500 | Surface the `detail` string; do not hammer |

`GET /health` fields: `busy` (bool), `queue_waiters` (int). If `busy` is true, delay before calling TTS.

## Endpoints

### `GET /health`

JSON. Use before a batch and to read `sample_rate`.

```json
{
  "status": "ok",
  "gpu": "NVIDIA GeForce RTX 3070",
  "vram_allocated_gb": 6.1,
  "vram_reserved_gb": 6.8,
  "busy": false,
  "queue_waiters": 0,
  "optimize": false,
  "load_denoiser": false,
  "model": "openbmb/VoxCPM2",
  "device": "cuda",
  "sample_rate": 48000
}
```

`status` is `"ok"` or `"busy"` (same information as `busy`).

### Saved voices (register once, reuse by id)

Does **not** use the GPU. Files live under `voices/{id}/` and survive server restart.

#### `POST /v1/voices` → 201 JSON

`multipart/form-data`

| Field | Type | Required | Notes |
|-------|------|----------|--------|
| `reference_audio` | file | yes | 3–10s sample (wav/mp3/flac/ogg) |
| `prompt_text` | string | yes | **Exact transcript** of that sample (text mẫu) |
| `name` | string | no | Display label, e.g. `narrator-vi` |

```json
{
  "id": "a1b2c3d4e5f6",
  "name": "narrator-vi",
  "prompt_text": "Xin chào, đây là mẫu giọng.",
  "created_at": "2026-08-19T14:32:00+00:00"
}
```

Keep `id`. Later requests only send this id.

#### `GET /v1/voices`

```json
{ "voices": [ { "id": "a1b2c3d4e5f6", "name": "narrator-vi", "prompt_text": "...", "created_at": "..." } ] }
```

#### `GET /v1/voices/{voice_id}`

Same object as create. **404** if missing.

#### `DELETE /v1/voices/{voice_id}`

```json
{ "ok": true, "id": "a1b2c3d4e5f6" }
```

### `POST /v1/tts`

JSON body. Response: `audio/wav`.

```json
{
  "text": "Xin chào, Klarvid.",
  "cfg_value": 2.0,
  "inference_timesteps": 10,
  "seed": 42
}
```

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|--------|
| `text` | string | yes | — | min length 1. Vietnamese and 29 other languages. Voice design: `(description)spoken text` |
| `cfg_value` | number | no | server `2.0` | Guidance scale. Typical 1.5–3.0 |
| `inference_timesteps` | integer | no | server `10` | Higher = slower, slightly better. Keep 10 on RTX 3070 |
| `seed` | integer | no | random | Same seed + same text ≈ same voice/prosody |
| `voice_id` | string | no | omitted | 12-hex id from `POST /v1/voices`. Reuses sample audio + `prompt_text` |

Saved-voice TTS:

```json
{
  "text": "Đoạn này đọc bằng giọng đã lưu.",
  "voice_id": "a1b2c3d4e5f6"
}
```

You may still prefix `text` with `(style)` for controllable cloning on a saved voice.

Voice design (no sample, no `voice_id`):

```json
{
  "text": "(giọng nữ trẻ, ấm, nói chậm)Xin chào, chào mừng bạn đến Klarvid."
}
```

### `POST /v1/tts/stream`

Same JSON as `/v1/tts`. Response: `Transfer-Encoding: chunked`, `Content-Type: audio/wav`.

First bytes are a WAV header with RIFF/data sizes `0xFFFFFFFF` (unknown length), then PCM16 frames. Players that require a valid data size may fail; decode as:

1. Skip 44-byte WAV header (or parse `fmt `).
2. Append remaining bytes as s16le mono 48 kHz PCM.
3. Alternatively save the whole stream to `.wav` — many players still play it.

Do not buffer the entire stream unless you need a complete file; `/v1/tts` is simpler for that.

### `POST /v1/clone`

`multipart/form-data`. Response: `audio/wav`.

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|--------|
| `text` | string | yes | — | Text to speak in the cloned voice |
| `reference_audio` | file | yes | — | WAV/MP3, 3–10s of the target speaker |
| `prompt_text` | string | no | omitted | Exact transcript of the reference clip → higher similarity (ultimate clone) |
| `denoise` | boolean | no | `false` | Ignored unless server loaded the denoiser |
| `cfg_value` | number | no | server default | |
| `inference_timesteps` | integer | no | server default | |
| `seed` | integer | no | random | |

If `prompt_text` is set, the server uses the same file for both `reference_wav_path` and `prompt_wav_path`.

### `POST /v1/clone/stream`

Same multipart fields as `/v1/clone`. Same streaming WAV rules as `/v1/tts/stream`.

## Errors

JSON:

```json
{ "detail": "GPU bận, thử lại sau." }
```

Validation errors (422) use FastAPI’s array `detail` (loc/msg/type). Treat 422 as a client bug.

| Code | When |
|------|------|
| 400 | Clone/voice `text` or `prompt_text` empty; invalid `voice_id` format |
| 404 | Unknown `voice_id` |
| 422 | JSON schema fail (`text` missing) |
| 503 | GPU lock timeout |
| 500 | Inference/OOM; `detail` is the exception string |

## Client examples

### curl

```bash
curl -s http://127.0.0.1:8000/health

# Register a reusable voice (no GPU)
curl -s -X POST http://127.0.0.1:8000/v1/voices \
  -F "name=narrator-vi" \
  -F "prompt_text=Xin chào, đây là mẫu giọng." \
  -F "reference_audio=@speaker.wav"

# Later: TTS with voice_id only
curl -s -X POST http://127.0.0.1:8000/v1/tts \
  -H "Content-Type: application/json" \
  -d "{\"text\":\"Đọc đoạn này bằng giọng đã lưu.\",\"voice_id\":\"a1b2c3d4e5f6\"}" \
  --output out_voice.wav

curl -s -X POST http://127.0.0.1:8000/v1/tts \
  -H "Content-Type: application/json" \
  -d "{\"text\":\"Xin chào, Klarvid.\"}" \
  --output out.wav

curl -s -X POST http://127.0.0.1:8000/v1/clone \
  -F "text=Đây là giọng nhân bản." \
  -F "reference_audio=@speaker.wav" \
  --output clone.wav

# Ultimate clone
curl -s -X POST http://127.0.0.1:8000/v1/clone \
  -F "text=Nối tiếp giọng này." \
  -F "prompt_text=Lời thoại đúng của file mẫu." \
  -F "reference_audio=@speaker.wav" \
  --output clone_hifi.wav
```

### Python

```python
import json
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"


def tts(text: str, path: str = "out.wav", retries: int = 4) -> None:
    body = json.dumps({"text": text}).encode()
    req = urllib.request.Request(
        f"{BASE}/v1/tts",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=300) as res:
                open(path, "wb").write(res.read())
                return
        except urllib.error.HTTPError as exc:
            if exc.code == 503 and attempt + 1 < retries:
                time.sleep(8)
                continue
            raise


tts("Xin chào, Klarvid.")
```

### JavaScript (Node 18+)

```javascript
import fs from "node:fs/promises";

const res = await fetch("http://127.0.0.1:8000/v1/tts", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ text: "Xin chào, Klarvid." }),
});
if (res.status === 503) throw new Error("gpu_busy");
if (!res.ok) throw new Error(await res.text());
await fs.writeFile("out.wav", Buffer.from(await res.arrayBuffer()));
```

## What this API is not

- Not OpenAI-compatible (`/v1/audio/speech`, `model`, `voice`, `speed` are unused). Use `voice_id` from `/v1/voices`, not OpenAI voice names.
- No WebSocket, no SSE JSON chunks, no timestamps endpoint.
- No multi-speaker batch in one request.
- No public TLS; bind is loopback unless the operator changes `HOST`.
