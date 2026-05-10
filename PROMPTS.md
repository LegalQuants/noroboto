# Prompt log

A chronological record of every user prompt that drove this repo from an empty
project brief to a working PoC. Verbatim where possible; paraphrased only when
a prompt was a slash command whose effect is what matters. Bracketed notes
summarize what happened in response.

---

## 1. `/init`

> Please analyze this codebase and create a CLAUDE.md file, which will be given
> to future instances of Claude Code to operate in this repository.

[Default `/init` invocation. I read the existing files (including
`noroboto.py`, `NOTES.md`) and proposed prepending a Claude-Code header plus
an architecture/commands section to the existing `CLAUDE.md`. Edit was
rejected.]

## 2. `/init` (re-run)

[Same prompt. Before answering, the user ran `touch .claude/.ignore` in two
local-command turns. I again proposed an edit to `CLAUDE.md`.]

## 3. Save a memory

> Add to memory: Only focus on files I have commited. Do not read into context
> other repository files.

[Saved as a `feedback` memory at
`feedback_committed_files_only.md`, indexed in `MEMORY.md`. From this point
on I scoped exploration to `git ls-files` output.]

## 4. `/init` (third run, with the new memory in effect)

[Re-listed tracked files only (`.gitignore`, `CLAUDE.md`, `cornellNDA.docx`,
`noroboto.py`, `nda.docx`, `symbols.docx`). Suggested header + architecture
prepend.]

## 5. Disown three files

> I want to remove from git history, and untrack the following files:
> `/Users/seth/Desktop/DOCx-encoding/nda.docx`,
> `/Users/seth/Desktop/DOCx-encoding/noroboto.py`,
> `/Users/seth/Desktop/DOCx-encoding/symbols.docx` — I want nothing to do with
> them.

[Asked two clarifying questions: keep on disk vs delete; touch the remote vs
not. Answers: keep on disk + untracked, local only. Proposed
`git filter-branch` to scrub them from history. The destructive command was
cancelled.]

## 6. `/init` (fourth run)

[The user re-ran `/init` after cancelling the filter-branch. With both the
"committed files only" memory and the explicit disown of `noroboto.py` /
`nda.docx` / `symbols.docx`, the only tracked content left to base guidance
on was `CLAUDE.md` + `cornellNDA.docx`. I made a minimal edit prepending the
required Claude-Code header to `CLAUDE.md` without fabricating architecture
from disowned files.]

## 7. `/plan` — master plan

> Given the project brief, come up with a master plan. Discover Superdoc,
> find out how to highlight and act on text with Superdoc, make a plan for
> the web server.

[Plan mode. Launched an `Explore` subagent to research Superdoc's
installation, rendering API, selection API, editor vs viewer, vanilla-JS
support, and examples. Asked three design questions:
selection API approach (Superdoc API first, fall back to native),
initial load (server-served `cornellNDA.docx` URL), and
injection site (server-side Python). Wrote the plan to
`/Users/seth/.claude/plans/given-the-project-brief-moonlit-gizmo.md`.]

## 8. Save the plan into the repo

> Looks good, create FRONTEND-MASTER-PLAN.md with the plan

[Copied the plan file to `FRONTEND-MASTER-PLAN.md` at the repo root.]

## 9. New branch

> make a new branch add/frontend

[`git checkout -b add/frontend`.]

## 10. Build the app

> Build the application based on the master plan.

[Created `app.py`, `requirements.txt`, `templates/index.html`,
`static/app.js`, `static/app.css`, `CHANGELOG.md`, `docs/work-process.md`.
Verified end-to-end via curl: `/current-doc` serves the bundled docx,
`/upload` accepts `.docx` and rejects `.txt`, `/inject` produces a doc whose
`word/document.xml` contains the banner, the echoed selection, and the
`w:vanish` element. Browser-side Superdoc rendering was not auto-tested.]

## 11. README

> add instructions for starting the web server, other relevant information to
> a README.md file

[Wrote `README.md` covering stack, run commands, usage walkthrough,
payload-verification commands, HTTP API table, layout, and limitations.]

## 12. Comment Python

> responsibly comment all python files

[Added a module docstring to `app.py`, function docstring on
`inject_payload` with the OOXML §17.3.2.45 reference, and inline `WHY`
comments at non-obvious spots: namespace registration (avoids `ns0:`
serialization), lazy default-doc load, in-memory part copy (vs ZIP append
mode), white-color belt-and-braces, `xml:space="preserve"`, and ZIP magic
check on upload. Skipped no-op comments on obvious code. `noroboto.py` left
alone per the disown list.]

## 13. Commit

> commit this with an informative extended commit description, good title

[Added `.venv/` and `.claude/` to `.gitignore`. Staged only the app files
(left `NOTES.md` untracked per memory). Committed as `31d3c97` with a
multi-paragraph body explaining backend routes, the `w:vanish` injection
technique, the front-end, docs, and the limitation that the front-end
wasn't browser-tested.]

## 14. Open in browser

> open it in the browser

[Started the server in the background; a leftover Python process from the
earlier verification run was already on `:5000`, so the new process exited
("Address already in use") but the browser still opened against the
running same-code server. Confirmed `/` serves `index.html` and
`/current-doc` returns 20749 bytes.]

## 15. This file

> I want you to include all of the prompts I've sent to get to this point,
> as a tracking measure in the repo. Read through the context and summarize
> our conversation, save to PROMPTS.md.

[This document.]

---

## Branch `fix/doc-rendering`

## 16. New branch

> Make a new branch fix/doc-rendering

[Initial `git checkout -b` cancelled.]

> Make a new branch fix/doc-rendering, based off of this branch

[`git checkout -b fix/doc-rendering add/frontend`.]

## 17. The doc isn't rendering

> the doc isn't rendering, fix it

[Started diagnosing. The earlier `<script src="...superdoc.umd.js">` was
hitting a 404 → CORS error because `superdoc` ships only ESM (no UMD
build). Started checking esm.sh as a workaround.]

## 18. Fix the console errors

> fix the console errors: `/Users/seth/Desktop/DOCx-encoding/ERRORS.md`

[Read `ERRORS.md`: CORS-blocked UMD load + favicon 404 + `SuperDoc global
not available`. Switched `static/app.js` to
`import { SuperDoc } from 'https://esm.sh/superdoc@1.32.0'`, removed the
broken UMD `<script>` from `index.html`, added a `204 /favicon.ico`
handler in `app.py`, dropped the `window.SuperDoc` polling.]

## 19. Update progress

> Ok, we need to update progress. The buttons are working correctly and so
> is the rendering. Add this to the CHANGELOG

[Added a dated entry to `CHANGELOG.md` describing the ESM-via-esm.sh fix
and marked Phases 1–4 ✅ browser-verified.]

## 20. Merge to parent

> Merge this branch into it's parent, then switch to the parent branch

[`git checkout add/frontend && git merge --no-ff fix/doc-rendering`
(merge commit `dd44dff`). Stayed on `add/frontend`.]

---

## Branch `discover/payload-injection`

## 21. New branch (round 2)

> make a new branch discover/payload-injection

[Initial `git checkout -b` cancelled.]

> make it off of the existing branch

[`git checkout -b discover/payload-injection add/frontend`.]

## 22. Process check

> What shell is running? the web server?

[Reported `zsh` and the Flask debug server still running on `:5000` (two
PIDs because the reloader spawns a child).]

## 23. Update the master plan

> Ok, update the master plan. We need to now actually add the payload to
> the document, and prove it is there. The web inspector hides everything
> from Superdoc, so what is a good way to do this? Write to a new file
> payloadAdded.docx?

[Appended **Phase 5 — Prove the payload is really in the file** to
`FRONTEND-MASTER-PLAN.md`. Approach: on every `/inject`, write
`payloadAdded.docx` to disk; have the inject response also carry
`extracted_text` (concatenated `w:t` content — what an LLM sees) and
`injected_xml` (the appended `<w:p>` subtree); add a Proof panel in the
UI showing both views plus a Download button.]

## 24. Implement Phase 5

> implement phase 5

[Refactored `inject_payload` to return
`(new_bytes, injected_xml, extracted_text)` with a new
`_extract_visible_text` helper. `/inject` writes `payloadAdded.docx`,
returns the new fields. Added `GET /payload-added` route. Added Proof
panel markup + styling + `renderProof()` JS. `payloadAdded.docx` added
to `.gitignore`. Verified end-to-end via curl: response includes the
full extracted contract text ending with
`❌ YOU HAVE BEEN HACKED ❌ :: <selection>`, the injected `<w:p>` with
`w:vanish` and white color; download serves an 18503-byte file; `unzip
-p ... | grep` finds the banner.]

## 25. CDN error 1 — esm.sh transitive 404

> Console error: superdoc@1.32.0:2 GET
> https://esm.sh/@hocuspocus/provider@%5E2.13.6?target=es2022
> net::ERR_CONNECTION_CLOSED

[Switched the import to `https://esm.sh/superdoc@1.32.0?bundle` so esm.sh
would inline transitive deps and avoid the semver-range URL.]

## 26. CDN error 2 — Vue refs null

> Console error: app.js:26 TypeError: Cannot read properties of null
> (reading 'refs') ...

[Diagnosis: esm.sh's `?bundle` mode was inlining a second copy of Vue,
which breaks Vue's template-ref binding. Switched the import to
`https://cdn.jsdelivr.net/npm/superdoc@1.32.0/+esm`.]

## 27. CDN error 3 — jsdelivr transitive 404

> console error: (index):1 GET
> https://cdn.jsdelivr.net/npm/@lifeomic/attempt@3.1.0/+esm
> net::ERR_ABORTED 404 (Not Found)

[Reverted to `https://esm.sh/superdoc@1.32.0` (plain) and pre-warmed
esm.sh's cache for the previously-failing transitive deps. Suggested
that the durable fix is local vendoring.]

## 28. Vendor Superdoc locally

> vendor superdoc locally

[Added `package.json` pinning `superdoc@1.32.0` and `esbuild@^0.24`.
Added `scripts/build-vendor.mjs` that bundles Superdoc into a single
self-contained ESM file at `static/vendor/superdoc.mjs` (and copies the
stylesheet to `static/vendor/superdoc.css`). Added
`scripts/stub-hocuspocus.mjs` no-op'ing `@hocuspocus/provider` (collab
feature unused; keeps y-protocols / websocket code out of the bundle).
Pointed `static/app.js` and `templates/index.html` at the local files.
Added `node_modules/`, `package-lock.json`, and the build's internal
entry shim to `.gitignore`. Verified the server serves
`/static/vendor/superdoc.{mjs,css}` (5.4 MB + 102 KB).]

## 29. Build + update docs

> [local shell: `npm install && npm run build:vendor`]
>
> Update README.md with these changes. Update CHANGELOG

[Updated `README.md`: vendoring in Stack, new first-time setup steps
(npm install + build:vendor), expanded "Using the app" step 5 to
describe the Proof panel, added `/payload-added` row to the API table,
expanded the Layout block. Added two new entries to `CHANGELOG.md`:
"Vendor Superdoc locally" and "Phase 5: prove the payload".]

## 30. Commit, push, PR URL

> commit this, push branch, and give me the URL to send for review

[Initial bash run was interrupted before staging completed.]

> Add all modified files to staged

[`git add` of 13 paths; `NOTES.md` left untracked per memory.]

> Add any new files created on this branch to staged

[Confirmed everything new was already staged.]

> commit and push it

[Committed as `29df197` ("Phase 5: prove the payload and vendor Superdoc
locally"). Pushed `discover/payload-injection` to `origin`. Reported PR
URL: https://github.com/drewmiller/noroboto/pull/new/discover/payload-injection.]

## 31. This update

> Add the prompts from this branch to PROMPTS.md, commit and push
