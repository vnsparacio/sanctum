## Summary

- What changed?
- Why is this change needed?

## Validation

- Tests added or changed:
- Commands run and results:

## Safety review

- **Authority boundary:** Does this change who can authorize actions, grant capabilities, or make completion/routing decisions? If not, say `None`.
- **Egress / privacy:** Does this change what data can leave the Mac, its destination, or handling of private data or secrets? If not, say `None`.
- **Replay / approvals:** Does this affect approval scope, expiry, one-use enforcement, replay protection, or idempotency? If not, say `None`.
- **Source / runtime integrity:** List source-manifest, hash, dependency-pin, or runtime-manifest changes and explain why each is intentional. Investigate and resolve unexplained drift; do not refresh hashes merely to silence it.

## Rollback

- How can this change be safely reverted or disabled?

## Out of scope

- Follow-up work discovered but intentionally left out of this PR:
