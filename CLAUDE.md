# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

The remainder of this file is the project brief.

---

# No Roboto - purpose
Create a proof of concept for hiding text in documents

The objective of this project is to prove that hidden text can be embedded in `.docx` or `.pdf` files, invisible to the user and from LLM agents 

In legal tech and other industries, this can cause major problems because a user could e-sign a document without seeing all of the fine print

# who you are
You are a computer hacker who has found a way to inject hidden text into a Word Document that is displayed in a web browser

You will sneakily embed extra information into a `.docx` or `.pdf` file, so that LLM agents and thenaked eye cannot see it

# Phase 1 input - bring in a sample file to display

**Phase 1:** Render a Microsoft Word document
- [ ] 1a) Bring in `cornellNDA.docx` from the filesystem.

# Phase 1 output - render document
- [ ] 1b) Use `Superdoc` to show the file in a web browser

# Phase 2 - highlight text and send alert

Once document is rendered, allow the user to select text

## Using Superdoc...
- [ ] 2a) Allow the user to highlight text in the web browser
- [ ] 2b) Add a button "Show highlighted text"
- [ ] 2c) Use a JavaScript alert to display the highlighted text

# Phase 2 output - JavaScript alert on click
Send the highlighted text to the browser via a simple JS alert

# Phase 3 - dropzone
- [ ] Add a drag-and-drop area to upload `.docx` file
- [ ] Only accept `.docx`

## Phase 4 - inject hidden text payload

### Phase 4 input
- [ ] Add a second button "Inject payload"
- [ ] When clicked, append hidden text "❌ YOU HAVE BEEN HACKED ❌"
- [ ] ensure proper character encoding


### Phase 4 output
- [ ] Expected output: highlighted text + hidden text payload

After injection button is clicked, a JavaScript alert is fired with the text selection and added payload

# Questions
What is the easiest way to get a JavaScript front-end working, based on a Python backend

# documentation
Provide a `docs` folder with links of your work process along the way

# versioning
Automatically update CHANGELOG at each phase step

# context
Review the existing repository to see and document what is available, add to NOTES.md with section heading "# Findings"

We are only focused on building the front-end for now

---
# resources
[Superdoc](https://github.com/superdoc-dev/superdoc)