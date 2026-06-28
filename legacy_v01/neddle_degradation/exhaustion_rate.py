"""Context window exhaustion rate experiment.

For each language in a FLORES-200 selection:
  1. Reset conversation.
  2. Feed sentences one at a time as user turns.
  3. After every turn (user + assistant), record the *real* tokens consumed
     using Ollama's prompt_eval_count (input) + eval_count (output).
  4. Stop when cumulative tokens >= num_ctx (window full).

Output: per-language list of (turn, user_tokens, assistant_tokens,
cumulative_tokens, utilization) plus the turn at which exhaustion happened.
"""
import json
import time
from pathlib import Path

import ollama

MODEL = "llama3.1:8b"
CONTEXT_WINDOW = 4096  # small enough to exhaust within a reasonable runtime

LANGS = {
    "eng_Latn": "English",
    "vie_Latn": "Vietnamese",
    "tha_Thai": "Thai",
    "tam_Taml": "Tamil",
    "hin_Deva": "Hindi",
    "khm_Khmr": "Khmer",
}

HERE = Path(__file__).parent
FLORES_DIR = HERE / "flores200_dataset"
RESULTS_FILE = HERE / "exhaustion_rate_results.json"

SYSTEM_PROMPT = (
    "You are a concise multilingual assistant. For each chunk the user sends, "
    "reply with one short sentence acknowledging the language and topic. "
    "Keep replies under 25 words."
)


def load_sentences(lang_code):
    dev = (FLORES_DIR / "dev" / f"{lang_code}.dev").read_text(encoding="utf-8").splitlines()
    devtest = (FLORES_DIR / "devtest" / f"{lang_code}.devtest").read_text(encoding="utf-8").splitlines()
    return [s.strip() for s in dev + devtest if s.strip()]


def run_language(lang_code, lang_name, sentences, window):
    print(f"\n=== {lang_name} ({lang_code}) @ ctx={window} ===")
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    turns = []
    cumulative = 0
    exhausted_turn = None

    t0 = time.time()
    for turn_id, sentence in enumerate(sentences):
        messages.append({"role": "user", "content": f"[Chunk {turn_id}] {sentence}"})

        resp = ollama.chat(
            model=MODEL,
            messages=messages,
            options={
                "num_ctx": window,
                "temperature": 0.2,
                "num_predict": 60,
            },
        )
        assistant_text = resp["message"]["content"]
        messages.append({"role": "assistant", "content": assistant_text})

        # Real token counts from Ollama
        user_tok = resp.get("prompt_eval_count", 0) - cumulative  # delta input this turn
        # prompt_eval_count is the *total* prompt tokens this call — we want the
        # delta added by this user message only.
        prompt_total = resp.get("prompt_eval_count", 0)
        assistant_tok = resp.get("eval_count", 0)

        # Cumulative = prompt the next turn would see = prompt_total + assistant_tok
        cumulative = prompt_total + assistant_tok
        util = cumulative / window

        # Recover this-turn user delta against the previous cumulative
        prev_cum = turns[-1]["cumulative_tokens"] if turns else 0
        user_delta = prompt_total - (prev_cum)

        turns.append({
            "turn": turn_id,
            "user_tokens_delta": user_delta,
            "assistant_tokens": assistant_tok,
            "prompt_eval_count_total": prompt_total,
            "cumulative_tokens": cumulative,
            "utilization": round(util, 4),
            "assistant_preview": assistant_text[:80].replace("\n", " "),
        })

        print(
            f"  turn {turn_id:>3}: +user={user_delta:>4} +asst={assistant_tok:>3} "
            f"cum={cumulative:>5} util={util*100:5.1f}%"
        )

        if cumulative >= window:
            exhausted_turn = turn_id
            print(f"  >>> EXHAUSTED at turn {turn_id} (cum {cumulative} >= window {window})")
            break

    elapsed = round(time.time() - t0, 2)
    return {
        "language": lang_name,
        "lang_code": lang_code,
        "window": window,
        "model": MODEL,
        "exhausted_turn": exhausted_turn,
        "total_turns": len(turns),
        "final_cumulative_tokens": cumulative,
        "elapsed_seconds": elapsed,
        "turns": turns,
    }


def main():
    state = {"model": MODEL, "window": CONTEXT_WINDOW, "rows": []}
    if RESULTS_FILE.exists():
        try:
            state = json.loads(RESULTS_FILE.read_text())
        except Exception:
            pass
    done = {r["lang_code"] for r in state["rows"] if r.get("exhausted_turn") is not None
            or r.get("total_turns", 0) > 0}

    for lang_code, lang_name in LANGS.items():
        if lang_code in done:
            print(f"[{lang_name}] skip (already recorded)")
            continue
        try:
            sentences = load_sentences(lang_code)
            row = run_language(lang_code, lang_name, sentences, CONTEXT_WINDOW)
            state["rows"].append(row)
            RESULTS_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            print(f"[{lang_name}] ERROR: {err}")
            state["rows"].append({
                "language": lang_name, "lang_code": lang_code,
                "window": CONTEXT_WINDOW, "error": err,
            })
            RESULTS_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))

    print(f"\n{'=' * 60}\nEXHAUSTION SUMMARY (window={CONTEXT_WINDOW})\n{'=' * 60}")
    print(f"{'language':>12} | {'turns_to_full':>13} | {'avg_tok/turn':>12} | {'elapsed_s':>9}")
    for r in state["rows"]:
        if "error" in r:
            print(f"{r['language']:>12} | ERROR: {r['error']}")
            continue
        avg = r["final_cumulative_tokens"] / max(1, r["total_turns"])
        ex = r["exhausted_turn"] if r["exhausted_turn"] is not None else "—"
        print(f"{r['language']:>12} | {str(ex):>13} | {avg:>12.1f} | {r['elapsed_seconds']:>9.1f}")


if __name__ == "__main__":
    main()
