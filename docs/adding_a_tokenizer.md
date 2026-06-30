# Adding a new tokenizer

`asia-fertility` ships 12 tokenizers (10 with full BPE data, 2 API-only count-only). Adding more is a 2-file change.

## Anatomy of the registry

`src/asia_fertility/tokenizers/registry.py` declares each tokenizer as an `info` dict and a lazy `loader` callable. The loader runs the first time the tokenizer is asked for, raising `TokenizerUnavailable` if its backend (tiktoken / transformers / API key) isn't ready. Unavailable tokenizers produce `skip_reason` rows in study output rather than crashing.

Tokenizers fall into three backend categories:

1. **`tiktoken` BPE** — OpenAI vocabularies (`openai/o200k_base`, `openai/cl100k_base`, `openai/o200k_harmony`). Adapter: `tokenizers/tiktoken_adapter.py`.
2. **HuggingFace** (`transformers` / `tokenizers`) — anything with a `tokenizer.json` on the Hub. Adapter: `tokenizers/hf_adapter.py`. May be gated (Llama, Gemma) — requires `HF_TOKEN`.
3. **API-only count-only** — Anthropic Claude, Google Gemini. Adapter: `tokenizers/api_adapter.py`. Needs the vendor's API key + python client. Not used for cost calculations (cost calls fall back to `openai/o200k_base` sizing).

## Adding a HuggingFace tokenizer (most common case)

1. **Find the repo + tokenizer file**. The minimum requirement is that `tokenizer.json` exists at the root of the repo, and that your `HF_TOKEN` can download it. Test:
   ```bash
   uv run python - <<'PY'
   from huggingface_hub import HfApi
   api = HfApi()
   api.hf_hub_download(repo_id="vendor/repo", filename="tokenizer.json")
   print("ok")
   PY
   ```

2. **Register it** in `src/asia_fertility/tokenizers/registry.py`. Pattern:
   ```python
   _register(
       TokenizerInfo(
           id="vendor/short-name",
           family="vendor",
           backend="hf",
           gated=False,                                # True if the HF repo is gated
           extra="hf",                                 # pip extra needed to install it
           notes="Optional one-line description.",
       ),
       loader=lambda info: HFTokenizer(info, repo_id="vendor/repo-with-tokenizer.json"),
   )
   ```

3. **Add it to the canonical model registry** if you're going to benchmark it. Edit `src/asia_fertility/_defaults/models_2026-06.yaml`:
   ```yaml
   vendor/model-id:
     family: vendor
     pricing: {input: 0.10, output: 0.30}
     context_window: 128000
     sizing_tokenizer: openai/o200k_base    # or your new id, if loadable
     native_tokenizer: vendor/short-name
     routes:
       openrouter: vendor/model-id          # or null
       native: model-id-on-native-api       # or null
     benchmarked_in: []                     # populate after running benchmarks
   ```

4. **Verify it loads + measures**:
   ```bash
   asia-fertility tokenizers list --available-only | grep vendor
   asia-fertility measure --text "test" --lang eng --tokenizer vendor/short-name
   ```

5. **Run the drift guard** to catch typos:
   ```bash
   uv run pytest tests/unit/test_model_id_sync.py -v
   ```

## Adding a `tiktoken` tokenizer

OpenAI publishes BPE vocabularies through `tiktoken.get_encoding(name)`. Register with `backend="tiktoken"`:

```python
_register(
    TokenizerInfo(
        id="openai/new_encoding",
        family="openai",
        backend="tiktoken",
        extra="oai",
        notes="Some GPT-N family",
    ),
    loader=lambda info: TiktokenTokenizer(info, encoding_name="new_encoding"),
)
```

## Adding an API-only count-only tokenizer

For vendors whose tokenizer ships only behind an API (Claude, Gemini), use `tokenizers/api_adapter.py`. The class should raise `TokenizerUnavailable` if the API key env var is missing, otherwise wrap the vendor's `count_tokens` method. Mark with `gated=True, extra="api"`.

Count-only tokenizers cannot participate in the leaderboard (their internal vocabulary isn't downloadable), but they CAN be referenced from `models_2026-06.yaml` as the `native_tokenizer` for billing-accurate cost calculation when the user has the API key.

## Updating prices

Tokenizers and models are separate concerns. After registering the tokenizer, add or update the related model entries in:
- `src/asia_fertility/_defaults/models_2026-06.yaml` (canonical source of truth)
- `src/asia_fertility/_defaults/prices_2026-06.yaml` (the cost subsystem's view; should mirror the canonical entries)

Bump `snapshot_date` in both files when you change pricing. The `test_model_id_sync.py::test_every_benchmarked_model_has_pricing` test catches missed entries.

## What the registry guarantees

- **Lazy loading.** Missing backends never crash imports; they produce a skip row at study time.
- **Idempotent listing.** `tokenizers list --available-only` always reflects the current environment's installed extras + env vars.
- **Stable IDs.** Renaming a tokenizer is breaking; add a new one and deprecate the old via `alias_of` in `models_2026-06.yaml`.

## When NOT to add a tokenizer

- If the underlying vocabulary is closed-source AND the vendor has no count-only API, there's no way to measure fertility.
- If the tokenizer is functionally identical to an existing one (e.g., a fine-tune that reuses the base tokenizer), reuse the existing ID.
