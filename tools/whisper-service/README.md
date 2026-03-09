# whisper-service

Host-side transcription service for Noa. Wraps [whisper.cpp](https://github.com/ggerganov/whisper.cpp) and exposes a simple HTTP endpoint that the Noa Docker backend calls via `host.docker.internal:8001`.

## Architecture

```
iPhone
  └─► POST /api/v1/voice/transcribe   (Noa backend in Docker :8000)
            └─► POST http://host.docker.internal:8001/transcribe
                      └─► whisper-cpp binary  (Metal / Apple Silicon)
                                └─► {"text": "..."}  ◄── back up the chain
```

All audio stays on your Mac. Nothing leaves the machine.

## Prerequisites

### 1. Install whisper.cpp

```bash
brew install whisper-cpp
```

Or build from source for maximum Metal performance:

```bash
git clone https://github.com/ggerganov/whisper.cpp
cd whisper.cpp
cmake -B build -DGGML_METAL=ON
cmake --build build --config Release -j$(sysctl -n hw.logicalcpu)
# Binary is at: build/bin/whisper-cpp  (or main on older versions)
```

### 2. Download the model

Recommended: large-v3 Q5_0 (~1.1 GB, best quality/speed on Apple Silicon)

```bash
mkdir -p ~/whisper-models
# Using whisper.cpp download script:
cd whisper.cpp
bash models/download-ggml-model.sh large-v3-q5_0
cp models/ggml-large-v3-q5_0.bin ~/whisper-models/
```

Or download directly:
```bash
curl -L -o ~/whisper-models/ggml-large-v3-q5_0.bin \
  "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-q5_0.bin"
```

### 3. Install Python dependencies

```bash
cd tools/whisper-service
pip install fastapi uvicorn python-multipart
```

## Running the service

```bash
cd tools/whisper-service
uvicorn server:app --host 0.0.0.0 --port 8001
```

Or with custom paths:

```bash
WHISPER_BIN=/path/to/whisper-cpp \
WHISPER_MODEL=~/whisper-models/ggml-large-v3-q5_0.bin \
uvicorn server:app --host 0.0.0.0 --port 8001
```

## Configuration

| Env var | Default | Description |
|---------|---------|-------------|
| `WHISPER_BIN` | `whisper-cpp` | Path to whisper.cpp binary |
| `WHISPER_MODEL` | `~/whisper-models/ggml-large-v3-q5_0.bin` | Path to GGML model file |
| `WHISPER_LANG` | `auto` | Language hint (e.g. `en`, `de`, `auto`) |

## Noa backend configuration

Set these in your `.env` or environment:

```bash
TRANSCRIPTION_PROVIDER=whisper_cpp
WHISPER_CPP_URL=http://host.docker.internal:8001
```

For OpenAI Whisper instead:

```bash
TRANSCRIPTION_PROVIDER=openai
OPENAI_API_KEY=sk-...
```

## Health check

```bash
curl http://localhost:8001/health
# {"status":"ok","model":"/Users/you/whisper-models/ggml-large-v3-q5_0.bin","bin":"whisper-cpp"}
```

## Test transcription

```bash
curl -X POST http://localhost:8001/transcribe \
  -F "file=@/path/to/test.m4a"
# {"text":"Hello, this is a test recording."}
```
