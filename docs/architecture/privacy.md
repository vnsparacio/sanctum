# Privacy and data flow

The first audit packet contains the new prompt, retained risk state and small attachment summaries. Raw history, filenames, bytes and tool results are excluded. A classifier's request for context cannot authorize that context.

Exact disclosure tickets bind session/revision, purpose, destination, settings, expiry and one use. Changing the request cancels stale approval. Hosted answer tiers require the relevant approval even when eligible. Private compute eligibility does not give the model Mac tools or automatic access to local personal-source history.

The shared egress record represents this decision separately from tool permission. It binds the exact packet digest, data class, destination service/model, purpose, capability, scope, revision, expiry and one-use status. It contains no approval token. A decision for one provider, model, purpose or packet never authorizes another; missing or stale fields fail closed.

Prepare files locally through the rendered attachment utility. Images become bounded metadata-stripped JPEGs. Video becomes sparse timestamped frames with no audio. PDFs receive bounded text extraction; embedded images are not implicitly inspected. The prepared digest/token binds content and scope. Selecting a file does not itself authorize egress.

Ending a session closes its lease but does not erase original files or locally prepared snapshots. Review retention explicitly. Do not include snapshots, raw prompts, source results, browser state, nonces or auth stores in public evidence. Failure categories can be logged without content; full gateway logs are private and may contain sensitive operational material.

Hosted provider pinning, zero-retention routing flags and collection restrictions are controls, not an independent audit of provider internals. Revalidate provider availability and policy at deployment without silently weakening the configured route.

## Qualification disclosures

Live hosted qualification sent only synthetic arithmetic, database-reasoning and fictional safety prompts, plus a generated red square. The candidate enforced separate exact audit/answer disclosures, pinned providers, no fallback, ZDR/data-collection policy fields and budget accounting. Successful calls validate transport behavior, not an independent provider retention audit. One existing hosted API credential was explicitly staged into private candidate state; the production credential database was read-only and was not copied wholesale. No real Calendar, Gmail or Messages content was read.
