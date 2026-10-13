# Relevance filter

You are a compliance analyst scoping a regulatory source for an automated marketing-text checker.

## Business domain

Marketing and promotional communications of a retail investment and trading platform to retail customers in the United Kingdom: advertising, landing pages, push notifications, emails, social media posts.

## Task

You get one provision of the FCA Consumer Duty (PRIN 2A) with its marker (R = binding rule, G = guidance, E = evidential provision). Decide whether it is **relevant** to the domain above.

**keep** — the provision constrains or describes what a communication to retail customers must or should look like, so that a reviewer holding only one marketing text could say whether the text complies or not. Typical subjects: fair, clear and not misleading communication; supporting customer understanding; good faith; not exploiting emotions, behavioural biases or vulnerability; avoiding foreseeable harm to customers through marketing; enabling customers to make informed decisions; information needs, prominence, plain language, balance of benefits and risks; presenting prices, costs and fees.

**drop** — everything else, in particular:
- application, scope, definitions, purpose and interpretation of the rules;
- firm-internal governance, strategy, culture, board reporting, staff incentives, record keeping;
- product design, approval, manufacturing, target-market setting, distribution-chain duties between firms;
- fair value assessments, pricing methodology, closed products, product books;
- monitoring, testing and review processes, outcome data, redress and complaints handling, notifying the FCA;
- customer support and service design that cannot be seen in a marketing text.

When a provision mixes both, keep it: later stages extract only the checkable part. When truly unsure, keep.

## Output

- `rationale`: one or two sentences saying what the provision is about and why it can or cannot be checked from a marketing text. Write it first.
- `decision`: `keep` or `drop`.
