# Cognitive Companion

A privacy-first AI watchdog for multigenerational households, designed to support seniors facing early cognitive decline while preserving their independence and dignity.  

[![Watch the video](https://img.youtube.com/vi/38H_yJTrEFg/default.jpg)](https://youtu.be/38H_yJTrEFg)

## Philosophy

Cognitive decline doesn't have to mean loss of independence. Cognitive Companion acts as a careful, unobtrusive presence in the home, watching for situations where a gentle reminder or nudge might help, without automating away the small acts of daily life that give seniors agency and routine.

Rules are written in natural language and evaluated by on-premise vision and language models, so the system understands *context* rather than just triggering on rigid conditions.

### Why local AI?

All cameras and sensitive data stay on-premises. No video or audio leaves your network. By self-hosting the VLMs and LLMs, household members never have to worry about their privacy being traded for convenience.

### Tamil language support

Feedback is delivered in Tamil, the language that is natural and familiar to the members of this household. Audio responses are generated via [edge-tts](https://github.com/travisvn/openai-edge-tts) (Microsoft's neural TTS), currently the most capable option for Tamil among *'freely'* available solutions. Audio playback is handled through Home Assistant.


## Architecture Overview

```
Cameras / Sensors
      │
      ▼
 FastAPI Gateway  ──►  MinIO (media storage)
      │
      ├──► VLLM - Cosmos Reason2 (vision reasoning)
      ├──► Ollama - Gemma3  (logic & feedback)
      ├──► VLLM - TranslateGemma  (Tamil translation)
      ├──► Visual notification ──►  e-ink Display
      └──► TTS - (edge-tts)  ──►  Home Assistant  ──►  Speaker
```

- **Rules engine** - configurable natural language rules with time-of-day and room-location contexts
- **Gradio console** - internal debug UI for rules, sensors, vision, and translation
- **Scheduler** - APScheduler runs periodic rule evaluations against live camera feeds
- **WhatsApp** - optional caretaker notifications via WhatsApp Business API


## Prerequisites

| Service | Purpose |
|---------|---------|
| **Kubernetes** (MicroK8s or similar) | Hosts the API gateway |
| **MinIO** | Object storage for captured media and audio clips |
| **Home Assistant** | Audio playback via media player integration |

### AI Endpoints

| Environment Variable | Model | Notes |
|---------------------|-------|-------|
| `VLLM_COSMOS_API_URL` | `nvidia/Cosmos-Reason2-8B` | Vision-language reasoning; served via vLLM |
| `VLLM_TRANSLATE_API_URL` | `Infomaniak-AI/vllm-translategemma-12b-it` | English ↔ Tamil translation; served via vLLM |
| `OLLAMA_API_URL` | `gemma3:27b` | Logic evaluation and feedback generation; served via Ollama |
| `TTS_API_URL` | `edge-tts` (OpenAI-compatible wrapper) | TTS for Tamil and English audio |

All endpoints must expose an OpenAI-compatible `/v1/` API.

## Deployment

### 1. MinIO

Create the bucket and note your credentials:

```bash
# create bucket (adjust endpoint as needed)
mc alias set local http://<minio-host>:9000 <access-key> <secret-key>
mc mb local/ai-media
```

Edit `kubernetes/configmap-minio.yaml` and set the minio configs and keys:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: minio-config
  labels:
    app: ai-api-gateway
data:
  MINIO_ENDPOINT: "<end-point>:80"
  MINIO_BUCKET_NAME: "ai-media"
  MINIO_SECURE: "false"
---
apiVersion: v1
kind: Secret
metadata:
  name: minio-secret
  labels:
    app: ai-api-gateway
type: Opaque
stringData:
  MINIO_ACCESS_KEY: "<ACCESS_KEY>"
  MINIO_SECRET_KEY: "<SECRET_KEY>"

```

### 2. Configure the Deployment

Edit `kubernetes/deployment.yaml` and set the AI endpoint URLs to match your infrastructure:

```yaml
env:
  - name: VLLM_COSMOS_API_URL
    value: "http://<cosmos-host>:8000/v1/"
  - name: VLLM_TRANSLATE_API_URL
    value: "http://<translate-host>:8001/v1/"
  - name: OLLAMA_API_URL
    value: "http://<ollama-host>:11434/v1/"
  - name: TTS_API_URL
    value: "http://<tts-host>:6060/v1/"
  - name: HOME_ASSISTANT_URL
    value: "http://homeassistant.local:8123"
  - name: HOME_ASSISTANT_TOKEN
    value: "<long-lived-access-token>"
```

### 3. Build and Push the Image

```bash
# builds and pushes to the local MicroK8s registry by default
./build_image.sh
```

### 4. Deploy

```bash
kubectl apply -f kubernetes/configmap-minio.yaml
kubectl apply -f kubernetes/deployment.yaml
kubectl apply -f kubernetes/service.yaml
```

Check that the pod is running:

```bash
kubectl get pods -l app=ai-api-gateway
kubectl logs -f deployment/ai-api-gateway
```

The API gateway will be available on port `8100`.

### 5. Run the Debug Console (optional)

```bash
cd cognitive-companion
pip install -r requirements.txt
python ui.py
```

Console available at `http://localhost:7860`.

---

## Configuration

All settings are read from environment variables (or a `.env` file in the project root):

| Variable | Description |
|----------|-------------|
| `VLLM_COSMOS_API_URL` | Cosmos reasoning endpoint |
| `VLLM_TRANSLATE_API_URL` | Translation endpoint |
| `OLLAMA_API_URL` | Ollama endpoint |
| `TTS_API_URL` | TTS endpoint |
| `HOME_ASSISTANT_URL` | Home Assistant base URL |
| `HOME_ASSISTANT_TOKEN` | Long-lived HA access token |
| `MINIO_ENDPOINT` | MinIO host:port |
| `MINIO_BUCKET_NAME` | Target bucket name |
| `MINIO_ACCESS_KEY` | MinIO access key |
| `MINIO_SECRET_KEY` | MinIO secret key |

---

## Project Structure

```
cognitive-companion/
├── app.py              # FastAPI application & routes
├── workflow.py         # Rule evaluation pipeline
├── scheduler.py        # APScheduler job management
├── database.py         # SQLite models (rules, sensors, contexts)
├── integrations.py     # TTS, Home Assistant, WhatsApp clients
├── utils.py            # VLLM/Ollama call helpers
├── minio_utils.py      # MinIO upload/download helpers
├── ui.py               # Gradio debug console
├── config.py           # Pydantic settings
├── routers/            # FastAPI routers (rules, sensors, images)
├── kubernetes/         # K8s deployment manifests
└── Dockerfile
```
