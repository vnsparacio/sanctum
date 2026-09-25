# Prompting the local 4B gate for grounded answers

This guide is for the **Mac prompt gate** model in a saved Open WebUI chat. It
covers public questions that Sanctum routes through Source-First and answers
with the local Qwen 4B model. Select **Mac prompt gate**, not the raw MLX model.
Ordinary text works; `/gate ask` is optional.

## Habits that help the local model

- Give it one main task and a small requested output, such as two cited facts
  or a short explanation. Split discovery, comparison, and verification into
  separate questions when each needs different evidence.
- Name any ambiguous person, product line, season, location, or version. Give
  the model the distinction you care about instead of asking it to guess what
  “latest” or “new” means.
- State the permitted uncertainty: “If the fetched source does not say, report
  that this source does not establish it.” This permits a useful, supported
  partial answer without turning missing evidence into a global claim.
- Treat identifiers, numbers, dates, and citations as claims to verify. Do not
  supply plausible invented examples that the model might repeat as real.
  The gate sets its own grounding format; a user prompt should describe the
  task, not dictate internal JSON fields or a `GROUNDED` label.

## What the failure means

For a current or otherwise externally verifiable question, the Mac requires
usable fetched evidence. A final answer must mark its supported claims
`GROUNDED` and cite at least one URL from the fetched evidence. The specific
`GROUNDING_REQUIRED` result means the evidence pack was inadequate, the model
did not mark its answer `GROUNDED`, or it supplied no citations. Malformed or
undelivered citations fail with other validation codes. The displayed source
excerpts are diagnostic snippets, not an answer or proof that the requested
fact was found.

No wording can guarantee a successful answer when readable sources do not
establish the fact. Do not ask the model to claim it is grounded, invent a
citation, or ignore the validation result.

## Write the request

1. **Lead with the subject and exact target.** Put the name, collection or
   version, and requested fact in the first few words. The current public
   query minimizer removes conversational scaffolding, and ordinary search
   uses the first six distinct searchable terms. A long preamble can displace
   the subject from the search sent to Parallel.
2. **Use a short, stable time or version label.** For a collection, prefer a
   label such as `FW26` over “most recent season as of September 25, 2026.”
   The current minimizer drops standalone numbers other than a public weather
   ZIP. Spell out any relative time only after naming the exact target.
3. **Ask one checkable question at a time.** A request to discover every code,
   prove each is new, decode each material, and compare every prior collection
   requires more evidence than one bounded retrieval often supplies. First
   establish the season and product codes; then ask a separate question about
   a specific code or claimed introduction.
4. **Name the evidence needed.** Ask for official product pages, collection
   guides, or a directly relevant published source. Request the exact source
   URL for each claim. A source preference in the prompt helps search, but it
   does not itself prove that an official page was fetched.
5. **Allow a narrow answer.** Ask the gate to report only what the fetched
   pages establish and to state a missing fact as unverified. “This source
   does not identify a new code” is supported by that source; “no new code
   exists anywhere” needs a much broader search.

Keep public research prompts free of private names, account data, and secrets.
Private context follows a different Mac-owned disclosure and approval path.

## Examples

The subject-first form below keeps the important words in the ordinary search
query. The examples are prompt patterns, not claims that the answer exists.

| Goal | Prompt to try |
| --- | --- |
| Identify a few product codes | `/gate ask Rick Owens FW26 material codes. From official product pages, identify up to two product codes and the material description on each page. Cite each page.` |
| Check whether a code is new | `/gate ask Rick Owens FW26 material code [CODE]. Does an official FW26 source explicitly call this code new? Cite the exact page. If it does not, say that novelty is unverified.` |
| Compare two subjects | `/gate ask Zen Buddhism Nietzsche scholarly comparison. Summarize one directly comparative source, distinguishing documented historical influence from later philosophical parallels. Cite that source.` |
| Check a changing fact | `/gate ask [ENTITY] [VERSION] [FACT]. Use a dated official source and cite it. If the source omits the requested fact, say so.` |

Avoid leading with phrases such as “search publicly what new...” or burying
the entity after long answer-format instructions. In the Rick Owens case, that
wording produced a search beginning `publicly new fabric codes were introduced`
and omitted the designer. The model could not repair that search by answering
more confidently.

## If `GROUNDING_REQUIRED` appears

1. Read the displayed excerpts as a clue to what was fetched. Check whether
   they actually address the requested fact, rather than merely sharing words
   with the prompt.
2. If the sources are off topic, retry once with the entity, exact season or
   version, and requested fact at the start. If they cover the topic but not
   the requested claim, narrow the question to a fact they can establish.
3. If the pages are blocked, raw PDFs, or otherwise unreadable, rephrasing
   cannot make their contents available through the guarded fetch path. Use
   another readable public source or accept that the answer is unavailable.
4. If a narrow request still fails despite a directly relevant fetched page,
   keep the exact prompt and diagnostic excerpts for a gate bug report. Do not
   treat the excerpts as a verified answer.

`/gate mode shadow` records a quality recommendation; it still uses the local
answer route. A hosted model selected through an explicit command has its own
disclosure approval and cannot make missing Source-First evidence appear.

## Engineering limit

Prompt wording is a workaround for the current ordinary-search truncation.
A focused code improvement would preserve named entities and season/version
tokens before applying the search-term cap, then require fetched pages to
support the requested relation or fact rather than merely matching two words.
That change would improve retrieval independently of the 4B model; it still
would not prove that an unpublished code or an exhaustive absence claim is
answerable from public sources.
