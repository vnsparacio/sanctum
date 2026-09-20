# First Splunk Observability Cloud slice

## Boundary

This integration adds one manual application trace for an authenticated Sanctum
gate request and a small custom metric set. It is observational only. Tracing,
metrics, configuration, export, flush, and shutdown failures are swallowed and
cannot grant or deny authority, change routing or egress, alter evaluation, or
change task completion.

The two telemetry paths remain separate:

```text
Sanctum metadata-only operational events
  -> existing private spool -> S3 -> Splunk Add-on for AWS -> Splunk Enterprise
  -> index=sanctum_ops sourcetype=sanctum:runtime:event

Sanctum manual traces and custom metrics
  -> @splunk/otel direct OTLP ingest -> Splunk Observability Cloud
```

No logs are sent to Observability Cloud. This slice installs no macOS Collector,
profiling, runtime/host metrics, automatic HTTP or provider instrumentation,
dashboards, detectors, RUM, GPU monitoring, or agent observability.

The supported gateway launcher preloads the manual OTel provider before
OpenClaw starts so active span context remains available to the gate and Core
event writer. The preload catches initialization failures and continues normal
gateway startup; it enables no automatic instrumentation.

## Service and signal model

The single service is `sanctum-gateway`, versioned with the Sanctum package.
Defaults include `deployment.environment=development` and the current semantic
convention `deployment.environment.name=development`,
`host.name=sanctum-authority-mac`, and `sanctum.host_role=authority`. The code
rebuilds resources from an allowlist, so detected process, path, command-line,
and personal host values are not exported.

The first root span is `sanctum.request`. Real children are emitted only when
their stages run: `authority.decide`, `egress.decide`, `model.inference`,
`source_need.classify`, `source_first.research`, and `reasoner.route`. Span
attributes use a bounded `sanctum.*` allowlist. Prompts, answers, content,
arbitrary exception messages, URLs, paths, headers, cookies, and credentials
are never span attributes or events.

Custom metrics are:

- `sanctum.request.count`
- `sanctum.request.duration` in milliseconds
- `sanctum.model.call.count`
- `sanctum.model.duration` in milliseconds
- `sanctum.model.tokens`
- `sanctum.authority.decision.count`
- `sanctum.egress.decision.count`

Metric dimensions are limited to bounded outcome/request class, model
role/provider, token direction, and decision values. Correlation IDs are never
metric dimensions.

## Private configuration

The required private runtime names are `SPLUNK_REALM` and
`SPLUNK_ACCESS_TOKEN`. Never place their values in Git, a proposal file, chat,
logs, or a report. Recommended non-secret values are:

```text
SANCTUM_O11Y_ENABLED=1
OTEL_SERVICE_NAME=sanctum-gateway
OTEL_RESOURCE_ATTRIBUTES=deployment.environment=development,deployment.environment.name=development,host.name=sanctum-authority-mac,sanctum.host_role=authority
```

The supported stopped-gateway amendment reads the two private values from the
owner's local process environment and writes them only to the private prefix's
mode-`0600` `config/environment.json` and private rollback transaction. It does
not print the token:

```sh
SANCTUM_PREFIX=/absolute/private/prefix
make down PREFIX="$SANCTUM_PREFIX"
read "SPLUNK_REALM?Splunk realm: "
read -rs "SPLUNK_ACCESS_TOKEN?Splunk access token: " && printf '\n'
export SPLUNK_REALM SPLUNK_ACCESS_TOKEN
.venv/bin/python -B scripts/configure.py \
  --prefix "$SANCTUM_PREFIX" --observability-env
unset SPLUNK_ACCESS_TOKEN SPLUNK_REALM
make doctor PREFIX="$SANCTUM_PREFIX"
make up PREFIX="$SANCTUM_PREFIX"
```

Missing, malformed, or conflicting exporter configuration leaves observability
disabled and does not prevent gateway startup. Explicit OTLP endpoint overrides
and configuration files are refused by this slice so a realm token cannot be
redirected to an unreviewed endpoint.

To disable direct O11y export immediately, stop the gateway and apply:

```sh
.venv/bin/python -B scripts/configure.py \
  --prefix "$SANCTUM_PREFIX" --disable-observability
make doctor PREFIX="$SANCTUM_PREFIX"
make up PREFIX="$SANCTUM_PREFIX"
```

## Bounded canary and correlation

After offline validation, run one ordinary authenticated `/gate` request that
uses the local answer path. In Splunk Observability Cloud, open APM, select
`sanctum-gateway`, find the `sanctum.request` trace, inspect its real children,
and copy the lowercase 32-character trace ID. Confirm that no private content
appears in the trace.

After the existing Core ingestion delay, run:

```spl
index=sanctum_ops trace_id="<TRACE_ID>"
```

The Core event writer reads the active OpenTelemetry context. It does not create
a context or reuse an authority/evidence digest. The APM and Core `trace_id`
values must match byte for byte; correlated Core events also contain the active
16-character `span_id`.

Confirm the request, model, authority, and egress custom metrics in Metrics
Finder. Stop after this canary; do not expand into infrastructure, vLLM, GPU,
Collector, dashboard, detector, profiling, or agent instrumentation.

## Rollback

Disable O11y with the command above to stop new direct exports while preserving
ordinary Sanctum operation and the existing Core path. A private configuration
transaction can be rolled back with `scripts/configure.py --rollback` while the
gateway is stopped. Source rollback is a revert of this project's commit and a
normal dependency reinstall from the prior lockfile. Neither action deletes
Core spool/S3 data or already-ingested Splunk data.
