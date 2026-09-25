# Local ask reliability: architectural plan and acceptance

## Problem and evidence

The September 2026 saved-chat failure was not a stale installation or a failed
web search. The local model reached the answer stage, received a Source-First
view, then returned prose claiming that untrusted fetched evidence was unusable.
The gate correctly withheld that non-JSON response. Earlier successful JSON
outputs were not proof of factual correctness: the host checks shape and
delivered citations, not sentence-level entailment.

The old `LOCAL_4B` answer path sends even tool-free evidence questions through
the full OpenClaw agent. That adds its system prompt, tool/session context and
possible compaction to a small model's answer task. It also asks the model to
obey a seven-field JSON contract solely through user-message instructions.
OpenClaw's [session documentation](https://docs.openclaw.ai/reference/session-management-compaction/store)
confirms that an agent session retains transcripts and compaction summaries.
The pinned MLX-LM HTTP server's [documented request fields](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/SERVER.md)
do not list a JSON-schema response constraint; do not assume that a
`response_format` parameter is enforced by this runtime.

Fresh direct calls to the *existing* cached Qwen 4B model answered small
synthetic weather, headline and unsupported-fact prompts in JSON. They also
occasionally mislabeled missing fields or repeated an instruction embedded in
a source. This is a useful architectural probe, not broad live qualification.

## Implemented source slice

1. Keep the Mac's audit, source decision, retrieval, risk, egress, approval,
   budget and final citation validation unchanged. The model never acquires
   authority from this change.
2. Select a fresh, tool-free MLX synthesis call only for local requests that do
   not require private/local tools, prior conversation, or media. Evidence is
   passed as a bounded typed view, not concatenated into the user question.
   The direct endpoint is pinned to the configured loopback model; no second
   model server, model weights, provider, or new dependency is started.
3. Preserve the existing OpenClaw agent for Gmail, Messages, Calendar, other
   local tool work and retained-context questions. Do not strip its tool loop.
4. For evidence answers, use a short host-authored system contract. Allow at
   most one *local-only* format retry with the same evidence, without sending
   the malformed output back as instructions. The Mac still rejects invalid
   shape, fabricated/undelivered citations, or insufficient required evidence.
   A model's factual claims are **not** certified by schema success alone.
5. Keep failures explicit and fail closed. There is no automatic hosted
   fallback, new disclosure, changed GPU policy, or permission escalation. If
   an adequate public evidence pack exists but model synthesis fails, the Mac
   may show a short, exact, labeled source excerpt. It never displays the
   rejected model answer as a verified answer.
6. Require a fetched page to match substantive terms in a non-weather public
   query before it can make a pack adequate. Search title/snippet relevance
   alone does not establish that the fetched body answers the question. This
   lexical check is conservative triage, not a semantic proof.

## Release qualification, not just unit tests

The source tests must cover routing, identity/budget drift, tool isolation,
malformed responses, bounded repair, citation rejection and injected source
commands. A reproducible local-model probe should exercise several domains:
self-contained explanation, calculations, public forecast with a missing
field, newest-headline selection, multi-source synthesis, conflicting sources,
unsupported requests and hostile instructions in fetched text. Score factual
support, requested-field completeness, source choice, format and latency
separately; do not count a parseable object as a correct answer.

`scripts/probe_local_synthesis.mjs` is an opt-in, synthetic-content probe of
the actual running local weights. Its first eight-case run passed six cases.
The failures were (1) a supported partial forecast labeled `PARTIAL`, which
the host correctly rejected under `WEB_REQUIRED`, and (2) an irrelevant
source question where the model added a fact not in the source. A generic
few-shot prompt made the forecast pass but also changed the unsupported
answer to `GROUNDED`, so that prompt change was reverted. A separate
model-selected extractive-output experiment selected irrelevant and hostile
source text; it was not adopted. The deployed fallback selects and labels a
bounded fetched excerpt deterministically without trusting the model's
selection. The reproducible probe remains a
diagnostic, **not** a passing release gate or saved-WebUI qualification.

The first saved-WebUI qualification on September 24 failed despite valid
output. A "latest headline" answer confused an article's event date with its
publication date and used an older article. A September 25 forecast mixed
Thursday night's cloud and wind conditions into Friday and asserted an
unsupported precipitation percentage. Both were accepted by the original
shape-and-citation validator. The candidate was rolled back and the PR remains
draft; neither failure is evidence that the old installed version is sound.

The follow-up candidate adds bounded Mac-owned checks before the local model
answers: a "latest headline" source must have a recent publication date
explicitly labeled in fetched body text or independently corroborated by the
search date and fetched publisher's dated final URL; a dated ZIP forecast must expose the
requested daytime period from a fetched National Weather Service page, not an
adjacent period or a stale commercial page. The final validator rejects
unsupported numbers and sky-condition phrases in that selected forecast and
rejects a headline publication date that does not match the verified date.
These are conservative checks, not general semantic entailment. A missing or
unparseable period/date becomes an explicit failure rather than a confident
answer. In the second saved-WebUI trial the revised forecast answered the
September 25 daytime period correctly and marked the absent precipitation
chance unavailable. The headline still failed closed because the fetched
article's readability text omitted its publication label, motivating the
dated-URL corroboration rule. A later headline attempt still failed because
the minimized search query selected generic indexes and a blocked article.
The candidate now uses two bounded, date-focused public searches and ranks
their combined results before the unchanged three-page fetch budget; a live
retrieval-only probe found recent, corroborated article evidence. The next
saved-WebUI answer cited a relevant recent article but omitted the requested
publication date; the Mac correctly rejected it. A repeated saved-WebUI
headline answer still mixed
event dates into a long summary, so the host rejected it rather than treating
any event date as publication evidence. The labeled source fallback now
suppresses retrieval-warning boilerplate, selects a subject-relevant excerpt,
and shows the verified publication date. This is a useful partial result, not
a passing headline answer. Broader requalification remains required before
this follow-up can merge.

After review and owner merge, deploy only through the stopped-stack
Source-First amendment and `make doctor`. Then run fresh saved-WebUI-chat
acceptance with ordinary and strong public-source questions plus read-only
Gmail, Messages and Calendar requests. A hosted strong answer still needs its
exact owner disclosure. Keep private source content and approval tokens out of
the repository and test reports. Preserve rollback evidence until those live
checks pass.

## Remaining work / limits

- Local 4B can still make unsupported claims inside valid JSON. A future
  claim-level evidence verifier or extractive answer mode must be evaluated
  against genuine paraphrases before it may be treated as proof of support.
- Source ranking and extraction must be benchmarked independently. A perfect
  answerer cannot recover fields missing from fetched pages.
- The local tool agent's personal-source answers need their own diverse,
  privacy-safe end-to-end evaluation. This slice deliberately does not rewrite
  those read-only broker contracts or add a remote tool loop.
- No finite test suite can guarantee arbitrary questions. Release criteria
  should be defined per capability lane with repeated live canaries and a
  zero-tolerance safety/authority regression gate, rather than a single
  successful weather prompt.
