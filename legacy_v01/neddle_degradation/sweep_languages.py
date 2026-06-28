"""Sweep llama3.1:8b across context windows AND languages using FLORES-200.

Languages: Thai, Tamil, Hindi, Khmer (+ English as baseline reference).
Windows : 4k, 8k, 16k, 32k, 64k, 128k.

Per language we calibrate tokens/char with a real Ollama tokenization call,
so non-Latin scripts (which have more tokens per character) actually fill
their requested context window instead of being undercounted.
"""
import json
import time
from pathlib import Path

import ollama

from sequential_prompt import ContextDegradationTest

MODEL = "llama3.1:8b"
WINDOWS = [4096, 8192, 16384, 32768, 65536, 131072]
LANGS = {
    "tha_Thai": "Thai",
    "tam_Taml": "Tamil",
    "hin_Deva": "Hindi",
    "khm_Khmr": "Khmer",
}
HERE = Path(__file__).parent
FLORES_DIR = HERE / "flores200_dataset"
RESULTS_FILE = HERE / "sweep_languages_results.json"


def load_sentences(lang_code):
    dev = (FLORES_DIR / "dev" / f"{lang_code}.dev").read_text(encoding="utf-8").splitlines()
    devtest = (FLORES_DIR / "devtest" / f"{lang_code}.devtest").read_text(encoding="utf-8").splitlines()
    return [s.strip() for s in dev + devtest if s.strip()]


def calibrate_tokens_per_char(sentences, sample=20):
    """Use Ollama's prompt_eval_count to learn real tokens/char for this script."""
    sample_text = " ".join(sentences[:sample])
    resp = ollama.chat(
        model=MODEL,
        messages=[{"role": "user", "content": sample_text}],
        options={"num_ctx": 4096, "num_predict": 1, "temperature": 0.0},
    )
    tokens = resp.get("prompt_eval_count", len(sample_text) // 4)
    ratio = tokens / max(1, len(sample_text))
    return ratio, tokens


def chunks_for_window(sentences, window, tokens_per_char):
    # Aim to fill ~110% of the window (Ollama will truncate to num_ctx)
    target_tokens = int(window * 1.1)
    cum = 0
    out = []
    i = 0
    while cum < target_tokens:
        s = sentences[i % len(sentences)]
        cum += int(len(s) * tokens_per_char) + 4  # +4 for role/markers overhead
        out.append(s)
        i += 1
        if i > 50000:  # safety
            break
    return out


def save(state):
    RESULTS_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def run_one(lang_code, lang_name, window, sentences, tpc):
    chunks = chunks_for_window(sentences, window, tpc)
    print(f"\n[{lang_name} @ {window}] feeding up to {len(chunks)} chunks (tpc={tpc:.3f})")
    test = ContextDegradationTest(
        max_context_tokens=window,
        model=MODEL,
        test_name=f"{lang_code}_window_{window}",
    )
    # Override token estimator using calibrated tokens-per-char
    test.calculate_tokens = lambda s, _r=tpc: max(1, int(len(s) * _r))

    start = time.time()
    for chunk_id, chunk in enumerate(chunks):
        util = test.add_chunk(chunk, chunk_id)
        if util >= 1.0:
            break
    fill_s = time.time() - start

    print(f"[{lang_name} @ {window}] running recall...")
    rec_start = time.time()
    rec = test.run_recall_test()
    rec_s = time.time() - rec_start

    return {
        "language": lang_name,
        "lang_code": lang_code,
        "window": window,
        "tokens_per_char": tpc,
        "tokens_at_full": test.current_tokens,
        "chunks_used": len([m for m in test.messages if m["role"] == "user"]) - 1,
        "fill_seconds": round(fill_s, 2),
        "recall_seconds": round(rec_s, 2),
        "injection_log": test.results["injection_log"],
        "recall_results": rec,
        "recall_response": test.results.get("recall_response", ""),
    }


def main():
    state = {"model": MODEL, "rows": []}
    if RESULTS_FILE.exists():
        try:
            state = json.loads(RESULTS_FILE.read_text())
        except Exception:
            pass
    done = {(r["lang_code"], r["window"]) for r in state["rows"] if "recall_results" in r}

    for lang_code, lang_name in LANGS.items():
        print(f"\n{'='*70}\n=== LANGUAGE {lang_name} ({lang_code}) ===\n{'='*70}")
        sentences = load_sentences(lang_code)
        tpc, n_tok = calibrate_tokens_per_char(sentences)
        print(f"[{lang_name}] sentences={len(sentences)} tokens/char={tpc:.3f} (sample={n_tok} tokens)")

        for window in WINDOWS:
            if (lang_code, window) in done:
                print(f"[{lang_name} @ {window}] skip (already done)")
                continue
            try:
                row = run_one(lang_code, lang_name, window, sentences, tpc)
                state["rows"].append(row)
                save(state)
            except Exception as e:
                err = f"{type(e).__name__}: {e}"
                print(f"[{lang_name} @ {window}] ERROR: {err}")
                state["rows"].append({
                    "language": lang_name, "lang_code": lang_code,
                    "window": window, "error": err,
                })
                save(state)

    # Final summary
    print(f"\n{'='*70}\n=== MULTI-LANG SUMMARY ===\n{'='*70}")
    print(f"{'lang':>6} | {'win':>6} | {'tok':>6} | {'rec_s':>7} | 5  25 50 75 95")
    for r in state["rows"]:
        if "error" in r:
            print(f"{r['language']:>6} | {r['window']:>6} | ERROR")
            continue
        rec = r["recall_results"]
        marks = ["Y" if next((x for x in rec.values() if x["injected_at_pct"] == p), {}).get("recalled") else "N"
                 for p in [5.0, 25.0, 50.0, 75.0, 95.0]]
        print(f"{r['language']:>6} | {r['window']:>6} | {r['tokens_at_full']:>6} | {r['recall_seconds']:>7.1f} | {'  '.join(marks)}")


if __name__ == "__main__":
    main()
