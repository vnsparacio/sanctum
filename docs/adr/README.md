# Architecture Decision Records

Architecture Decision Records (ADRs) preserve the context and rationale for
important Sanctum engineering decisions. Keep them concise. Link to detailed
designs, issues, pull requests and historical handoffs instead of copying those
reports into the ADR.

ADRs describe decisions and their history. They do not grant authority or
override current reviewed code, security policy, privacy policy, runtime pins
or owner controls. When an ADR conflicts with a current governing artifact,
the governing artifact controls and the ADR should be superseded or corrected.

## Location and naming

Store ADRs in this directory using:

```text
NNNN-short-kebab-case-title.md
```

- Use the next unused four-digit number, starting with `0001`.
- Never reuse a number, including after an ADR is superseded.
- Copy [`TEMPLATE.md`](TEMPLATE.md) and replace its guidance text.
- Keep supporting evidence in its existing canonical location and link to it.

## When to write an ADR

Write an ADR when a change makes or reverses a durable choice that future
contributors will need to understand. Examples include:

- changing authority, security, privacy or trust boundaries;
- introducing or replacing a major component, dependency or integration;
- defining a durable interface, data ownership rule or deployment boundary;
- choosing among meaningful alternatives with lasting operational cost; or
- reversing a decision recorded by an Accepted ADR.

An ADR is usually unnecessary for a local bug fix, routine implementation of
an accepted design, editorial documentation, dependency maintenance with no
architectural effect or an experiment that creates no lasting commitment. If
the decision can be fully explained in the pull request and is unlikely to
matter after that change, keep it in the pull request.

## Status

Use exactly one of these values in the `Status` field:

- **Proposed**: under discussion and not an approved architecture decision.
- **Accepted**: approved through normal human review and present in the
  accepted development history. A pull request may change Proposed to Accepted
  as part of its owner-approved merge.
- **Superseded**: replaced in whole or in material part by a newer Accepted
  ADR. This remains historical evidence rather than current direction.

Do not rewrite an Accepted ADR to make a different decision appear original.
Create a new Proposed ADR that links to the old one, and explain what changes.
When the replacement is accepted, change the old ADR to Superseded and add a
`Superseded by` link. Make both updates in the same pull request when practical.

Small factual fixes and repaired links may edit an Accepted ADR when they do
not change the recorded decision or rationale.

## Lightweight workflow

1. Copy the template and assign the next unused number.
2. State the context, decision, consequences and considered alternatives in a
   few focused paragraphs or bullets.
3. Link the ADR from the implementing pull request. Add stable references to
   the relevant Linear issue, design or historical handoff when useful.
4. Use normal review to accept the ADR with the implementation. If the decision
   changes later, supersede it instead of deleting its history.

An ADR records why a decision exists. Implementation details that are clear
from code, tests or operational guides should stay there.
