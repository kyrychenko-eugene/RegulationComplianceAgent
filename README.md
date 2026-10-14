# Regulation Compliance Agent

An agent that checks marketing materials of a retail investment platform **rule by rule** against the FCA Consumer Duty (PS22/9 → **PRIN 2A**) and gives a verdict with reasoning and evidence for every rule.

## Quick start

You need Python 3.9 or newer and your own OpenAI API key. Run everything from the repository root.

```bash
git clone https://github.com/kyrychenko-eugene/RegulationComplianceAgent.git
cd RegulationComplianceAgent
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # Windows: copy .env.example .env
```

Open `.env` and put your key after `OPENAI_API_KEY=`. Then check a text:

```bash
python -m agent "Install our app and get rich tomorrow 🚀🚀🚀"
```

It prints a Markdown report (overall verdict, every rule checked, quotes and reasons for failed rules), then the background judge's second opinion. The rules are already built (`data/rules.json`), so no ingest step is needed. Each check costs about $0.003, plus about $0.01 for the judge.

Other ways to use it:

```bash
streamlit run ui/app.py          # web UI: Check, History, Rules tabs
python -m agent --file text.txt  # check a text from a file
python -m eval run               # run the golden dataset (≈ $0.40)
pip install -r requirements-dev.txt && python -m pytest   # offline tests, no key needed
```

The default models are `gpt-6-luna` (checks and classifier) and `gpt-6.1-sol` (judge); change them in `.env` if your account uses others. More commands, the architecture and the measured results: [`docs/technical-overview.md`](docs/technical-overview.md).

---

## Thinking doc

### What I built and what I cut

I built an ingest pipeline, an agent and a light UI that check marketing materials rule by rule against the FCA Consumer Duty, PS22/9 → PRIN 2A.

- **Golden dataset first.** It was a clear decision to start with the golden dataset before any ingest or agent work, so that it stays agnostic to the implementation and isn't fitted to how the rules ended up worded.
- **Cut as much as possible in ingest.** Ingest is a one-time process, so the decision was to filter out as many irrelevant provisions as possible right there, instead of carrying them into every run.
- **Rules, not paragraphs.** The output of ingest is not just the relevant paragraphs but rules: each one an atomic yes/no question that an LLM can check from the text alone (pass / fail), with a verbatim quote from the source. Every rule goes through deterministic checks in code and a critic. Ingest uses the more powerful model, because it runs once.
- **Checking the rules themselves.** The rules became the critical part of the whole system, so they needed their own checks: the quality gate (code checks + critic) for every rule, and `eval coverage`, which maps the golden dataset onto the rules and shows which expected violations have no rule at all.
- **Tags and a real classifier.** In ingest, rules that only apply in some situations get tags. At runtime the OpenAI Decisions API classifier (a classifier, not just another LLM call) returns a probability for each tag, and code picks the tags above a threshold. That decides which conditional rules are run.
- **Parallel checks with a cheaper model.** All relevant rules are checked in parallel by a less powerful, cheaper model.
- **Code checks the LLM.** Every LLM answer is validated by deterministic rules in code: a quote must exist verbatim in the text, a fail must say what is wrong or missing, and anything invalid becomes `unclear` instead of a fail.
- **Deterministic final decision.** The final verdict (PASS / FAIL / NEEDS_HUMAN_REVIEW) is made by business rules in code, not by an LLM. This is a conscious decision by design. Severity comes from the source itself: binding rules (R) block, guidance (G) is advisory.
- **Background judge.** A stronger model reviews every run as a second opinion, so I can see whether the answer looks right. It never changes the verdict, and it runs in the background so the user doesn't wait for it.
- **Separate layers.** Ingest, agent, eval and UI are separate layers that only talk through `rules.json` and the public `agent.check()`, for better composition.
- **No LangChain.** The flow is clear and fixed, with no tools, memory or loops, so a graph framework would only add a layer of complexity and hide the prompts.

What I cut:
- **Ingest retry with critic feedback.** It was planned as an optional stage and cut first, so rules rejected by the critic stay rejected.
- **Other sources.** The FCA guidance (FG22/5), the financial promotions rules (COBS 4) and other jurisdictions are out of scope.
- **Rewrite suggestions and non-English input.** The task was to check, not to rewrite.

### Key prompt design decisions

1. **Order for prompt caching.** Everything shared across rules (instructions + the marketing text) goes first and the rule goes last, so the shared part is cached and reused by every rule check.
2. **Reasoning first in the response.** The response schema starts with `reasoning`, then the violation type, the quote and only then the verdict, to encourage the model to think before it decides.
3. **No examples from the golden dataset in prompts.** I avoided wording from the golden dataset in the prompts, so the eval isn't measuring a model that has seen the answers.
4. **Proportionality and materiality** (added after eval). Judge the message, not a full disclosure document; fail only what a compliance reviewer would actually raise; judge language rules on the whole message in its app context. This removed most of the false FAILs.
5. **Unclear is better than guessing.** If the text doesn't give enough to decide, the model answers `unclear` instead of guessing. Code turns that into "needs human review", never into a pass.
6. **Content vs omission.** A violation is either something the text says ("Guaranteed 20% a year"), which must be quoted word for word, or something it leaves out (no risk warning), which has nothing to quote, so the model must name exactly what is missing.

### What I'd do differently with more time

1. **Put more focus on the golden dataset.** It was hard for me to review it properly because it's a new business domain for me. A compliance professional should review the cases and labels.
2. **Make the rules concrete, not only faithful to the source.** The hardest trade-off in rule decomposition was faithfulness vs specificity. PRIN 2A is principles-based, so a rule that stays faithful to the source is abstract ("Does the communication avoid creating a misleading impression?"), while a concrete test ("Does it avoid presenting returns as guaranteed?") is an interpretation the source doesn't spell out, and the critic's `faithful` score rejects exactly that kind of rule. As a result the rules overlap (about five of them ask in different words whether the text gives enough information for a decision), and the reference case fails 13 of 18 rules instead of three clear findings. The concrete knowledge moved into the examples of the check prompt, where it can't be reviewed rule by rule. With more time I'd add a second layer of concrete tests under each principle (guaranteed returns, a risk warning as prominent as the benefit, past performance shown as a forecast, hidden conditions of a "free" offer, artificial urgency), each marked as an interpretation and approved by a human. The critic would then check that a test follows from the source instead of rejecting anything the quote doesn't say word for word; near-duplicate rules would be merged, and severity would be set per test instead of per R/G marker.
3. **Group the answer by finding, keep the full list in the history.** Today the user sees every failed rule, so the reference case shows 13 failed rules, most of them saying the same thing in different words. A compliance reviewer wants three findings: a misleading promise of returns, missing risk information, and emotional pressure. I'd give each rule a `concept` once, in ingest (proposed by the LLM, approved by a human), and have code group the failed rules by it: one finding per concept, with the strongest severity, the evidence and the rules behind it. The verdict and the history stay as they are today, with every rule and its reasoning, so nothing is hidden from an audit. I wouldn't cluster the results with an LLM at runtime: it would add a non-deterministic step, latency and cost to every run, and the grouping depends on the rules, not on the text.
4. **Human approval of the rules.** Rejected rules, especially those the critic rejected, should get a human review instead of being dropped.
5. **Polish the code and logic to get to 100% on the golden dataset.** Today it's about 75% on the overall verdict, but every miss is stricter than the label, all 34 expected violations are caught, and the stronger judge model also says FAIL on 4 of the 6 misses. So the gap is mostly in the labels and the rule set, not the model.
6. **More metrics in the history.**
7. **More test coverage.** The core logic is covered by offline tests with a mocked OpenAI client, but there are no live tests against the real API (important for the Decisions API, which is still in beta), no UI tests, and no regression tests that catch a prompt change breaking a case that used to pass.
8. **More evals, on different parameters.** Today the eval is one run on 23 cases, and only the classifier threshold is swept. I'd run each configuration several times to see the variance, and compare models (cheap vs strong for the checks), prompt versions, caching on/off and concurrency, on quality, latency and cost together. I'd also add an eval for ingest itself: how good the extracted rules are compared with a human review.

### What surprised me

1. **Tags weren't that efficient.** Most rules ended up as "always apply" (17 of 24), so the runtime filtering by tags removes only a few checks per run.
2. **A lot of the document was dropped: 154 of 169 provisions.** At first I thought it was a mistake, but most of those articles are about firm processes (governance, product approval, fair value, monitoring) that can't be judged from a marketing text at all.
3. **The rules mattered more than the model.** A simple feature announcement ("set price alerts on any instrument") was rejected because "instrument" was called jargon. The cause was the rule set: two almost identical language rules (one of them blocking) failed on the same word, and the rule that said "explain jargon only where it's unavoidable" had been rejected by the critic during ingest.

### How I built it with AI

1. I used the grill-me skill with Opus 5.5 to create the spec.
2. Opus 5.5 split the spec into stages.
3. Each stage except the final one was executed by the cheaper Sonnet 5.5, each against its own stage file.
4. Opus 5.5 also created the golden dataset, and ran the final review against the spec and the task.
