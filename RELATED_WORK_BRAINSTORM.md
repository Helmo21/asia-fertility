# FertiScope — Related Work brainstorm (Global South AI Safety Hackathon)

**Template constraint:** 4-page report. Intro + Related Work = **~1 page combined**. Realistic Related Work budget: **~½ page, ~350–450 words, 12–18 citations**. Rubric questions to answer inside the section: (a) when/why use FertiScope over SOTA? (b) what insight does it provide that we did not have?

**Safety reframe (vs. cost framing of v0.1 README):** for this submission, FertiScope is not a cost-optimization tool — it is an **upstream safety audit** for low-resource Asian language deployments. The fertility signal is the same; the framing changes. Fertility predicts where (1) cross-lingual jailbreaks land, (2) safety classifiers degrade on fragmented input, (3) multi-turn jailbreaks open up earlier because context compresses faster. Vietnamese is the canonical case because no IndoSafety-tier Vietnamese benchmark exists.

Sources reused from prior turn: A = Failure-Modes overview · B = Vietnamese deep-dive · C = Safety-Benchmark Design · S = synthesis.

---

## Draft A — tight ½-page version (paste-ready, ~430 words)

### 2. Related Work

**Tokenizer fertility as a structural penalty.** Petrov et al. (2023) established that BPE tokenizers fragment low-resource languages at 5–15× English rates, with direct economic and accuracy consequences; Tao et al. (2026) extended this across tokenizer families. Practitioner accounts (Kamali, 2025; "Don't Touch My Diacritics", 2024) document the same gap in deployment. These works frame fertility as an efficiency or fairness problem. **We reframe it as a safety signal:** high fertility fragments inputs before any safety classifier sees them, weakens the universal refusal direction (Chen et al., arXiv 2505.17306), and compresses the context budget so multi-turn jailbreaks open earlier (Direction 5, synthesis).

**Cross-lingual safety failures.** Yong et al. (2023) showed that simply translating English jailbreaks into low-resource languages lifts GPT-4 attack success from <1% to 79%; Wang et al. (2023, "All Languages Matter") found low-resource languages elicit harmful content ~3× more often than English; the 2026 systematic eval (arXiv 2511.00689) confirms defenses validated in English do not transfer. These works document the *behavioral* gap. None of them connect it to a tokenizer-level upstream predictor that a deployer can compute pre-deployment.

**Vietnamese-specific risk surface.** Vietnamese sits in a uniquely demanding regime: 6 phonemic tones, syllable-based segmentation, hierarchical kinship-based pronouns, and a diacritic system where ~52.8% of caption vocabulary has a meaning-changing twin one tone-mark away (ViTextCaps, arXiv 2604.27712). VinAI's PhoGPT (arXiv 2311.02945) responds with a byte-level BPE that preserves diacritics; VinaLLaMA (arXiv 2312.11011) and Vistral (arXiv 2403.02715) extend the open Vietnamese LLM stack. Doc C identifies Vietnamese-specific adversarial transforms (diacritic perturbation, kinship-pronoun manipulation, Northern↔Southern dialect shift) that bypass English-trained safety classifiers — yet **no IndoSafety-tier Vietnamese benchmark exists**: XL-SafetyBench (arXiv 2605.05662) excludes Vietnamese; SEA-HELM (arXiv 2502.14301) covers Vietnamese with toxicity detection only.

**Regional response, still upstream-blind.** SEA-LION (arXiv 2504.05747) and SeaLLMs 3 (arXiv 2407.19672) close headline benchmark gaps via continue-training on Llama / Gemma weights, and SEA-HELM, IndoSafety (arXiv 2506.02573), and SGToxicGuard (arXiv 2509.15260) operationalize multi-pillar regional safety evaluation. All measure outcomes *after* the tokenizer has fragmented the input. **FertiScope closes this loop by surfacing the tokenizer-level signal — fertility ratio, cost multiplier, and context-budget consumption curve — against the tokenizers actually shipped (cl100k, o200k, Llama-3.1, SEA-LION v3) on the deployer's own Vietnamese↔English corpus, locally and without API calls.** A team auditing a Vietnamese deployment can run FertiScope *before* paying for SEA-HELM evaluation and predict which classifier will degrade.

---

## Draft B — what to cut if you need to fall back to 250 words

If Methods/Results push Related Work down further, collapse to two paragraphs:

1. Merge **fertility** + **cross-lingual safety** into one paragraph that frames fertility as a safety signal (Petrov 2023, Yong 2023, Refusal Direction Universal 2025).
2. Merge **Vietnamese specifics** + **regional response** into one paragraph that ends on the niche claim (no IndoSafety-tier Vietnamese; FertiScope is the upstream audit).

Cut: VinaLLaMA, Vistral, Tao 2026, SGToxicGuard, Kamali blog. Keep: Petrov, Yong, Refusal Direction Universal, ViTextCaps, PhoGPT, SEA-HELM, IndoSafety, SEA-LION.

---

## Rubric-question answers (work these into Intro contributions list, not Related Work prose)

**(a) When/why over SOTA?**
- Existing tools are **post-hoc**: SEA-HELM evaluates a deployed model; MultiJail / IndoSafety probe a deployed model; refusal-direction interpretability requires open weights and GPU compute.
- FertiScope is **pre-deployment, local, free, and tokenizer-only**: a Vietnamese product team can run it in minutes against their own corpus before they pick a model. The output is actionable at the procurement stage.

**(b) What insight that we did not have?**
- A **per-tokenizer fertility ratio** on the deployer's actual Vietnamese corpus (not FLORES-200 only).
- A **cost multiplier in dollars** at OpenAI / Bedrock / Together pricing — tokenizer choice translated to a budget number.
- A **context-budget collapse curve** showing how fast the 4096 / 8192 window fills per turn, predicting the multi-turn jailbreak surface.

---

## Citation shortlist (12 — enough for ½-page Related Work, leaves room for Methods / Results citations)

Core (must cite):
1. Petrov et al. 2023 — Language Model Tokenizers Introduce Unfairness Between Languages. arXiv 2305.15425.
2. Yong, Menghini, Bach 2023 — Low-Resource Languages Jailbreak GPT-4. arXiv 2310.02446.
3. Wang et al. 2023 — All Languages Matter: On the Multilingual Safety of LLMs. arXiv 2310.00905.
4. Chen et al. 2025 — Refusal Direction is Universal Across Safety-Aligned Languages. arXiv 2505.17306.
5. ViTextCaps / Phonological Attention 2026 — arXiv 2604.27712 (the 52.8% diacritic-collision number).
6. VinAIResearch PhoGPT 2023 — arXiv 2311.02945.
7. SEA-HELM 2025 — arXiv 2502.14301.
8. IndoSafety 2025 — arXiv 2506.02573.
9. XL-SafetyBench 2026 — arXiv 2605.05662 (explicitly note Vietnamese exclusion).
10. SEA-LION 2025 — arXiv 2504.05747.

Optional (cite if space):
11. Tao et al. 2026 — Equity with Efficiency. arXiv 2606.15044.
12. "Don't Touch My Diacritics" 2024 — arXiv 2410.24140.
13. VinaLLaMA 2023 — arXiv 2312.11011.
14. SeaLLMs 3 2024 — arXiv 2407.19672.
15. Do Methods to Jailbreak and Defend LLMs Generalize Across Languages? 2026 — arXiv 2511.00689.

Drop unless they appear in Methods:
- VerChol, SambaLingo, Mangosteen, Stingray, Damanik et al., Stanford HAI blog, LILT blog, IndicGenBench/IndicQuest (the paper is Asia-focused; Indic data is supporting, not load-bearing).

---

## Two framing risks to flag before you submit

1. **Is FertiScope safety-load-bearing or just safety-adjacent?** The honest claim is "fertility is an upstream proxy for known cross-lingual safety failure surfaces." Don't overclaim it as a safety classifier or a defense. If a reviewer asks "what attack does this stop?", the answer is "none directly — it tells you *where* attacks will land hardest, so you can prioritize red-team budget."
2. **The submission is Global South — keep the Vietnamese / SEA framing primary.** OpenAI / Llama tokenizers are the deployment reality; SEA-LION is the regional response. Don't drift into Indic or African examples (interesting but off-scope for v0.1). Save them for Future Work.
