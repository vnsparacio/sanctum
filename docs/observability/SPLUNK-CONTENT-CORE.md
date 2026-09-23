# Restricted content telemetry in Splunk Enterprise

## Boundary and source contract

The source-controlled Splunk app in `splunk/sanctum_content` prepares the
separate TTE-52 content stream for later owner deployment. It does not perform
live Splunk, AWS, bucket, credential, role, retention, or scheduler changes.

The fixed Splunk contracts are:

| Stream | Index | Sourcetype | Source schema |
| --- | --- | --- | --- |
| Restricted interactions | `sanctum_content` | `sanctum:ai:interaction` | `sanctum.ai-interaction/v1` |
| Restricted append-only quality evidence | `sanctum_content` | `sanctum:quality:annotation` | `sanctum.quality-annotation/v1` |
| Existing metadata-only operations (unchanged) | `sanctum_ops` | `sanctum:runtime:event` | existing operational contract |

Interaction and quality records contain private content or evaluation evidence
and are more sensitive than metadata-only operations. Never route either
restricted sourcetype into `sanctum_ops`, and never change an interaction event
to add quality data. Quality annotations remain append-only records joined by
`interaction_id`.

## Review and deploy the app

The app includes `indexes.conf`, JSONL parsing in `props.conf`, disabled
saved-search definitions, an overview dashboard, and an administrator-only
metadata baseline. It deliberately contains no input, credential, bucket,
private prefix, retention, or deployment-server binding.

Before a later owner-authorized deployment:

1. Review the app and the content/quality schemas. Confirm the destination's
   encryption, backup, retention, deletion, and legal policy separately.
2. Install `splunk/sanctum_content` through the site's normal reviewed app
   deployment. Place `indexes.conf` on every indexer or indexer cluster peer,
   and place `props.conf` on the parsing tier that receives the AWS input.
3. Create a separate Splunk Add-on for AWS input using the already reviewed,
   content-prefix-only reader described in `docs/guides/operations.md`. Select
   `sanctum_content` and `sanctum:ai:interaction`; do not reuse the operational
   input. If an independently approved quality-annotation delivery is present,
   give it its own input with `sanctum:quality:annotation`.
4. Keep `SHOULD_LINEMERGE=false`, `LINE_BREAKER=([\r\n]+)`, `KV_MODE=json`, and
   `INDEXED_EXTRACTIONS=none`. Each canonical JSONL physical line is exactly one
   event; escaped newlines inside JSON strings remain part of that event.
5. Canary with synthetic records first. Confirm event counts equal physical
   JSONL record counts and inspect `_raw` before enabling any owner content
   delivery schedule. Do not use live owner content as a parsing probe.

The source `indexes.conf` uses only `$SPLUNK_DB` paths. A cluster or storage
site may override storage and retention in `local/` after owner review; do not
commit rendered volume names, bucket values, credentials, or private runtime
paths. Preserve the existing `sanctum_ops` index, input, sourcetype, roles,
dashboards, and retention unchanged.

## Least privilege

The packaged knowledge objects default to `admin` only and do not export
outside the app. Before granting access, create deployment-local roles rather
than broadening an existing operational role:

- a restricted content reader may search only `sanctum_content`, with no
  wildcard/all-index capability, export, sharing, scheduling, or edit rights;
- a content administrator may manage this app and index but should not receive
  AWS secrets or unrelated Splunk administration solely for this task;
- a correlation role may search both `sanctum_content` and `sanctum_ops`, but
  only when the reviewer is already authorized for restricted content;
- an operations-only role that can search `sanctum_ops` must not gain
  `sanctum_content` implicitly.

Grant access through deployment-local role and `metadata/local.meta` changes so
the source default remains deny-by-default. Review search-job artifacts,
scheduled-report ownership, alert actions, summary indexing, dashboard
sharing, export/download, and audit retention: each can create another copy of
restricted content. The supplied reports use `dispatchAs=user` and
`enableSched=0`; do not schedule or accelerate them without a separate content
handling review.

## Search examples

The saved searches contain the deployable versions. This detail query answers
what was received and delivered, whether it succeeded, the bounded failure
reason, and model/latency/token context:

```spl
index=sanctum_content sourcetype=sanctum:ai:interaction
| spath
| rename "failure.stage" AS failure_stage "failure.category" AS failure_category "failure.code" AS failure_code "model.model" AS model_name "model.revision" AS model_revision "model.provider" AS model_provider "usage.latency_ms" AS latency_ms "usage.input_tokens" AS input_tokens "usage.output_tokens" AS output_tokens
| table _time interaction_id user_query delivered_response outcome failure_stage failure_category failure_code model_name model_revision model_provider latency_ms input_tokens output_tokens
```

Success rate and structured failure analysis:

```spl
index=sanctum_content sourcetype=sanctum:ai:interaction
| spath
| stats count AS interactions count(eval(outcome="success")) AS successes BY model.provider model.model model.revision
| eval success_rate=round(100*successes/interactions,2)
```

```spl
index=sanctum_content sourcetype=sanctum:ai:interaction outcome!="success"
| spath
| rename "failure.stage" AS failure_stage "failure.category" AS failure_category "failure.code" AS failure_code
| fillnull value="NONE" failure_stage failure_category failure_code
| stats count BY outcome failure_stage failure_category failure_code
| sort - count
```

Quality annotations can be summarized without rewriting or treating them as
authority:

```spl
index=sanctum_content sourcetype=sanctum:quality:annotation
| spath
| rename "evaluator.evaluator_id" AS evaluator_id "evaluator.evaluator_version" AS evaluator_version "grounding.status" AS grounding_status "citation.status" AS citation_status
| table _time interaction_id source owner_rating evaluator_id evaluator_version scores{} pass semantic_failure_category grounding_status citation_status
```

## Correlate with metadata-only operations

Use the 32-character `correlation.trace_id` from an authorized content record
as the preferred cross-stream key. Operational events keep the same value in
top-level `trace_id`. The supplied trace-correlation saved search accepts a
`trace_id` token; the equivalent explicit SPL is:

```spl
(index=sanctum_content sourcetype=sanctum:ai:interaction) OR (index=sanctum_ops sourcetype=sanctum:runtime:event)
| spath
| eval correlated_trace_id=coalesce(trace_id,'correlation.trace_id'), correlated_run_id=coalesce(run_id,'correlation.run_id'), correlated_session_id=coalesce(session_id,'correlation.session_id')
| where correlated_trace_id="<TRACE_ID>"
| eval telemetry_stream=if(index="sanctum_content","restricted_content","metadata_only_ops")
| sort 0 _time
| table _time telemetry_stream sourcetype interaction_id event_id correlated_run_id correlated_session_id correlated_trace_id outcome stage category code
```

Replace the placeholder only in the search UI; do not commit live IDs. If a
trace is absent, use a stable `correlation.run_id` or
`correlation.session_id` only when the corresponding operational event exposes
the same stable ID. Never correlate on query/response text or a digest that has
an authority or approval meaning. Access to both indexes is required, and the
resulting search job is itself restricted content.

## Validation and rollback

Run the fixture/config checks without a Splunk instance:

```sh
.venv/bin/python -B -m unittest tests.test_splunk_content_assets
```

The fixture contains two interaction lines and one annotation line, including
an escaped response newline. The test checks physical-line/event parity,
parsing settings, searches, dashboard XML, and the absence of operational
index/sourcetype definitions from the restricted app.

Rollback is an owner-controlled removal or disablement of this app and its
separate content input after searches/jobs are stopped. Removing the app does
not delete indexed content. Data deletion, retention changes, credential
revocation, and bucket lifecycle remain separate owner security actions. Do
not roll back by changing `sanctum_ops` or broadening access.
