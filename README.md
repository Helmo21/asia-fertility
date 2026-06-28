# asia-fertility 🌏

**The hidden multilingual tax in your tokenizer — measured before you deploy.**

[![CI](https://github.com/Helmo21/asia-fertility/actions/workflows/ci.yml/badge.svg)](https://github.com/Helmo21/asia-fertility/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](pyproject.toml)

> **Status: v0.2 under active construction.** See [`ROADMAP.md`](ROADMAP.md) and the per-phase specs in [`tasks/`](tasks/).

`asia-fertility` measures the structural cost penalty that LLM tokenizers impose on lower-resource Asian languages. The same content can cost up to 11× more tokens in Burmese than in English on a frontier tokenizer — silent inflation of API bills, smaller usable context windows, and fewer in-context examples.

## Quickstart (once v0.3 ships)

```bash
pip install "asia-fertility[oai]"
asia-fertility reproduce
```

## What's currently usable

- v0.1 Python prototype: `legacy_v01/fertiscope/` (EN↔VI only, CLI).
- Live Next.js web demo: [fertiscope.vercel.app](https://fertiscope.vercel.app).
- 41 implementation specs: [`tasks/`](tasks/).

## License

MIT © 2026 Antoine Pedretti. Bundled FLORES-200 data: CC-BY-SA 4.0 (Meta NLLB).
