# FastAPI service + Next.js wiring (optional moat)

Status: pending (v0.4 optional)
Tags: `web`, `fastapi`, `nextjs`, `integration`, `optional`
Depends on: #006, #007, #008, #019
Blocks: None

## Scope

Bridge the Python package and the Next.js web app. The current web app uses `js-tiktoken` + `llama3-tokenizer-js` in the browser — 3 tokenizers. To expose all 11+ tokenizers without bundling 500MB to the browser, ship a thin FastAPI service that the Next.js app calls.

### Files to create

- `services/fertiscope_api/main.py` — FastAPI app.
- `services/fertiscope_api/Dockerfile`
- `services/fertiscope_api/pyproject.toml` — service-specific deps.
- `services/fertiscope_api/README.md` — deploy instructions for Modal / Vercel Python / Fly.io.
- `fertiscope-web/app/api/analyze/route.ts` — Next.js proxy that calls the FastAPI service.

### Files to modify

- `fertiscope-web/components/AnalyzerTab.tsx` (or similar) — add a "server-side (11 tokenizers, slower)" toggle.

### Interface and contract

`services/fertiscope_api/main.py`:

```python
"""FertiScope API — minimal HTTP surface for the web app.

POST /analyze
{
  "text": "...",
  "lang": "vie",
  "tokenizers": ["openai/o200k_base", "google/gemma-4"]
}

Returns:
{
  "results": [
    {"tokenizer": "...", "tokens": 27, "fertility": 1.42, "cpt": 4.5, "bpt": 7.2,
     "available": true},
    {"tokenizer": "google/gemma-4", "available": false, "reason": "gated repo, HF_TOKEN missing"}
  ]
}
"""
from __future__ import annotations
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from fertiscope.tokenizers import get_tokenizer, list_tokenizers, TokenizerUnavailable, TokenizerNotFound
from fertiscope.corpora import Sentence
from fertiscope.core import per_sentence
from fertiscope.core.segmentation import count_words
from fertiscope.core.aggregate_ci import aggregate_with_cis


app = FastAPI(title="FertiScope API", version="0.1.0")


class AnalyzeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=100_000)
    lang: str = Field(default="eng")
    tokenizers: list[str] = Field(min_length=1, max_length=20)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "available_tokenizers": [t.id for t in list_tokenizers(available_only=True)]}


@app.post("/analyze")
def analyze(req: AnalyzeRequest) -> dict:
    results = []
    sentences = [Sentence(id="api:0", lang=req.lang, text=req.text)]
    for tid in req.tokenizers:
        try:
            tok = get_tokenizer(tid)
        except TokenizerNotFound:
            results.append({"tokenizer": tid, "available": False, "reason": "unknown tokenizer id"})
            continue
        except TokenizerUnavailable as e:
            results.append({"tokenizer": tid, "available": False, "reason": e.reason})
            continue
        try:
            metrics = [per_sentence(s, tok, segmenter=count_words) for s in sentences]
            agg = aggregate_with_cis(metrics, baseline=None, n_resamples=200)
            results.append({
                "tokenizer": tid, "available": True,
                "tokens": metrics[0].tokens,
                "words": metrics[0].words,
                "fertility": agg.fertility[0],
                "cpt": agg.cpt[0],
                "bpt": agg.bpt[0],
            })
        except Exception as e:
            results.append({"tokenizer": tid, "available": False, "reason": f"runtime: {e}"})
    return {"results": results}
```

`services/fertiscope_api/Dockerfile`:

```dockerfile
FROM python:3.12-slim AS base

WORKDIR /app

# Copy package source and service entry
COPY pyproject.toml /tmp/build/pyproject.toml
COPY src /tmp/build/src
COPY services/fertiscope_api/pyproject.toml /app/pyproject.toml
COPY services/fertiscope_api/main.py /app/main.py

RUN pip install --no-cache-dir \
    "fastapi[standard]>=0.115" \
    /tmp/build[oai,hf]

ENV PORT=8000
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

`fertiscope-web/app/api/analyze/route.ts`:

```typescript
import { NextRequest, NextResponse } from 'next/server';

const FERTISCOPE_API_URL = process.env.FERTISCOPE_API_URL ?? 'https://api.fertiscope.vercel.app';

export async function POST(request: NextRequest) {
  const body = await request.json();
  // Pass through validation; service does its own with pydantic
  const upstream = await fetch(`${FERTISCOPE_API_URL}/analyze`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!upstream.ok) {
    return NextResponse.json({ error: `upstream ${upstream.status}` }, { status: 502 });
  }
  return NextResponse.json(await upstream.json());
}
```

`fertiscope-web/components/AnalyzerTab.tsx` change (simplified):

```tsx
const [mode, setMode] = useState<'client'|'server'>('client');

async function analyze(text, lang) {
  if (mode === 'client') {
    return runClientSide(text, lang);   // existing js-tiktoken path
  } else {
    const r = await fetch('/api/analyze', {
      method: 'POST',
      body: JSON.stringify({ text, lang, tokenizers: ALL_TOKENIZERS }),
    });
    return r.json();
  }
}
```

`services/fertiscope_api/README.md`: deploy instructions for Modal (free tier), Vercel Python (free tier), and Fly.io.

### Notes

- Service-side `n_resamples=200` for quick response (~200ms for 11 tokenizers on a warm container). Full bootstrap (1000) is too slow for interactive UX.
- Deploy on Modal: ~$10/month for moderate traffic. Free tier covers occasional use.
- Vercel Python supports the service via `vercel.json` config; cold start ~10s for HF tokenizer downloads.
- Service-side validation is via FastAPI's pydantic; client-side validation is duplicated for UX. Document.
- The `FERTISCOPE_API_URL` env var defaults to a hosted prod URL; can override for local dev.

## Acceptance Criteria

- [ ] `services/fertiscope_api/main.py` runs locally with `uvicorn main:app` (port 8000).
- [ ] `GET /health` returns 200 with `status: ok` and a tokenizer list.
- [ ] `POST /analyze` with valid body returns 200 with `results: [...]`.
- [ ] Unknown tokenizer → row with `available: false, reason: "unknown..."`.
- [ ] Gated tokenizer without HF_TOKEN → row with `available: false, reason: "gated..."`.
- [ ] Dockerfile builds; container runs and serves /health.
- [ ] Next.js route `/api/analyze` proxies the request.
- [ ] Analyzer tab toggle works: client-side (3 tokenizers, instant) vs server-side (11 tokenizers, ~500ms).
- [ ] Deployed instance reachable from production fertiscope.vercel.app.

## User Stories

### Story: Web user analyzes their Vietnamese text with Gemma-4

1. Opens fertiscope.vercel.app.
2. Pastes Vietnamese text.
3. Toggles "server-side (11 tokenizers)".
4. Hits Analyze.
5. After ~500ms: result table with rows for cl100k, o200k, Llama-3.1, Llama-4, Gemma-4, Mistral, Qwen3, etc.
6. Sees Gemma-4 is best for Vietnamese, switches recommendation.

### Story: Indian Tamil deployer

1. Pastes Tamil product copy.
2. Toggles server-side.
3. Sees IndicSuperTokenizer fertility = 2.4× vs GPT-4 = 11×.
4. Concrete decision data, no Python required.

### Story: Maintainer debugs a service crash

1. Modal logs show a Gemma-4 OOM on tokenization.
2. Restart, redeploy with `--memory 2048`.
3. Service stable.

---

Blocked by: #006, #007, #008, #019
