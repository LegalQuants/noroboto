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
