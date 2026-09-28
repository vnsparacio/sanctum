# Local patch recovery diagnostic amendment

The owner initially requested an on-the-fly repair. This local amendment is now
included in the assisted MoodLog review PR. Its diagnostic behavior was
validated separately from the later assisted application result.

## Observed behavior

A focused MoodLog continuation made one exact edit, then stalled on repeated unchanged reads. The isolated candidate test failed because the jsdom import was removed while a JSDOM constructor remained. A synthetic signed-transport check confirmed that updated source and successful edit history reach subsequent model requests; this did not establish a stale-read defect.

A continuation using the existing unified-diff tool repeatedly returned EDIT_PATCH_INVALID without changing any file. The owner-facing run was cancelled. Content-minimized receipts do not retain the rejected patch, so the precise original syntax fault is unknown. Neither run reached full app acceptance.

## Local repair

Replace the generic patch-format error with fixed categories and static correction guidance for headers, hunk syntax, line markers, counts, positions, order, and missing hunks. Return the guidance through the existing disclosed tool-result path. Do not echo rejected patch content or local paths. The parser, exact context checks, mutation authority, limits, and rollback rules are unchanged.

Synthetic tests exercise malformed patches, unchanged file inventories, absence of mutation authority calls, successful corrected patches, and guidance reaching the next reasoner request. These checks do not qualify live Qwen recovery or MoodLog acceptance.

SOURCE-MANIFEST.json was explicitly refrozen for the reviewed editor, regression
tests, and this document. Runtime pins stayed unchanged. The supported
stopped-gateway Work Mode amendment was applied and checked with doctor; its
receipt and any subsequent live result remain in private owner evidence.
