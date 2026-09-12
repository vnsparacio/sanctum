# Capabilities and limits

The reference V1 includes local Qwen 4B agent work, private 80B reasoning, hosted 235B, bounded visual processing, frontier reasoning, read-only Messages/Gmail/Calendar, web retrieval, guarded browsing, create-only Markdown, File Steward and exact local utilities.

The package supplies those sources and boundaries. The default isolated configuration enables utilities; optional integrations require local configuration and separate acceptance. Feature completeness of the reference system is not proof of clean-install readiness of every integration.

No messaging/email sending, calendar mutation, generic deletion, arbitrary shell or remote access to Mac tools is included. File move/rename/undo remain approval-gated. Bigger models can hallucinate and failed policy/long-context cases remain relevant.

Image downsampling limits OCR. Video support is sampled frames only, without audio or continuous coverage. PDFs are bounded text extraction. Large, encrypted or unsupported inputs may be refused. Context limits are explicit; V1 has no mature general RAG system.

A restart can lose process-local gate jobs while GPU ownership remains durable. Closing a tab is not guaranteed to close a lease immediately. Provider/network/Mac outages can delay deletion and continue billing. Local-only operation, all-container deployment, universal factual accuracy and multi-tenant isolation are not promised.

## Fresh release evidence

On the owner’s Apple Silicon Mac, prefix-owned MLX installation, cached-weight startup, authenticated local inference, restart and stop passed. The WebUI application path completed local, 235B, frontier and image requests; normal automatic routing selected each of those tiers in synthetic cases. Fresh Calendar/Gmail reads and local generation, synthetic File Steward/Markdown actions, actual Browser Guard navigation/approvals, existing MCP transports and the bounded private GPU allocation/reuse/cleanup passed. Interactive WebUI local arithmetic also passed. The owner-run native Messages helper and the candidate broker/wrapper test passed after the app context was denied. The final test bounded raw reads to three and verified the supporting source quote. This does not establish universal personal-answer factual correctness. The small model selected an unavailable sandbox browser in one chat; the separate native browser test passed with the configured host-native isolated profile.
