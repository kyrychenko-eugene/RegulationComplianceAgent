# NOTES

Findings recorded while building. Numbers are measured, not estimated.

## Stage 1 — ingest

### Source structure (measured on the real PS22/9 PDF, 161 pages)
- PRIN 2A in Appendix 1 splits into **169 provisions**, all ids unique: **89 R, 78 G, 2 E** (2A.3.30, 2A.4.35). E does occur, contrary to the spec's "not observed in 2A.2 or 2A.5" (true for those sections only); the splitter handles it and maps it to `advisory`.
- Per section: 2A.1: 18 · 2A.2: 28 · 2A.3: 30 · 2A.4: 35 · 2A.5: 15 · 2A.6: 6 · 2A.7: 5 · 2A.8: 5 · 2A.9: 17 · 2A.10: 5 · 2A.11: 5.
- Located by heading search (`Appendix 1` cover page → `2A The Consumer Duty` → next `Amend/Insert/Annex` instruction), no page numbers.

### Surprises
- The FCA PDF is AES-encrypted: `pypdf` fails with `DependencyError` until `cryptography` is installed. Added to `requirements.txt`.
- Sub-headings ("Application", "Manufacturers: product approval process …") are not marked in the text. Long ones wrap onto a second line with no indent, and my first splitter glued that tail (e.g. "products", "distributors") onto the previous provision. Caught by a check that every provision text ends in sentence punctuation; fixed by dropping the wrapped line after a sub-heading. 169 provisions before and after, so only the text was wrong, not the count.
- Environment: Python 3.9 here, so schemas use `typing.Optional/List`, not `X | Y` (pydantic evaluates annotations). Installed `openai` is 2.48.0, not the ≥ 3.26.0 in spec §10; ingest only needs the Responses API, which 2.48.0 has. The Decisions API (stage 3) needs the newer SDK — bump `requirements.txt` then.

### Design choices the spec left open
- `id` is built by code: `PRIN<provision>-<sub>-<a,b,…>`, e.g. `PRIN2A.5.3-1c-a`; `source_ref` is built by code from the provision and the model's `sub_ref`. The model only proposes the sub-paragraph.
- `source_quote` is verified against **its own provision's** text, stricter than "anywhere in the source"; a final assert also checks all approved quotes against the whole chapter.
- The critic runs on every drafted rule, including ones that already failed a deterministic check, so rejected rules still carry scores.
- "Single question" is a heuristic: exactly one `?` at the end, no `;`, no `(a)` labels, no "x, y, and z" lists. It cannot see two conditions joined by a bare "and"; that is the critic's `atomic` job.
- Tag vocabulary: rules are extracted in parallel and cannot see each other's tags, so `prompts/ingest/extract.md` seeds a starting vocabulary and asks the model to reuse it. Review the resulting tag counts (printed by `python -m ingest`) before stage 3.

### Counts (provisions total / kept / dropped; rules approved / rejected)
**Pending the live run.** No `OPENAI_API_KEY` was available in the build session, so `data/rules.json` has not been generated. Provisions total: 169 (measured above). Everything else: to be filled after running `python -m ingest`, together with whether rules exist for PRIN 2A.5.3(1)(c), 2A.5.3(2) and 2A.2.3(b) / 2A.2.10(2).

### Verification done without a key
- 18 offline tests (`pytest`): splitter, heading search, id/ref/severity by code, every deterministic check, critic thresholds, full pipeline with a mocked client, `--limit`, the verbatim assertion, empty-parse error, and the failure paths (filter/critic/extract call fails).
- The three Pydantic output schemas convert to OpenAI strict structured-output format.
- Not verified: real model behaviour, the live `responses.parse` call, usage field names (`cache_write_tokens` is read with a default of 0 in case the SDK does not expose it).
