# Antigravity Agent Guidelines

## 1. Context Hygiene & Speed (CRITICAL FOR PERFORMANCE)
- **Token Conservation**: Keep conversation context lean (<15k tokens). Every extra 20k tokens adds 1-2 minutes of latency per turn.
- **Output Suppression**: NEVER dump entire file contents, full PDF text, or massive command logs into tool outputs.
  - To verify a build/script: check exit code (`$LASTEXITCODE -eq 0`) and file existence/size. Do NOT print 5 pages of text to verify.
  - To inspect code: view only the specific 10-20 lines needed (`StartLine`/`EndLine`).
- **Use Subagents for Heavy/Trial-and-Error Tasks**:
  - When writing multi-page documents, compiling complex PDFs, or running iterative scripts: delegate to an isolated subagent or execute cleanly in 1-2 direct disk writes.
  - An isolated subagent keeps the main chat context clean (0 cache invalidation), ensuring the main chat responds in 2-3 seconds.

## 2. In-Place File Modifications (STRICT REQUIREMENT)
- **NEVER** rewrite or regenerate an entire file (>30 lines) when fixing bugs, fonts, strings, or formatting.
- **ALWAYS** perform fast in-place modifications directly on disk:
  - Run a 1-line Python/PowerShell regex or `replace()` script. Execution time: 0.1s.
  - Never generate thousands of boilerplate tokens in chat.

## 3. PDF and Document Handling
- **NEVER** load full-page images or multi-page scanned PDFs into chat context using `view_file`.
- Always extract text to a local `.txt` file using Python (`pypdf`) and inspect only the required text snippet.
- For scanned documents without text: never convert all pages to PNG to view in chat. Either run local OCR to a file or ask for the specific page.

## 4. Subagent & Process Efficiency
- Kill hung or runaway tasks immediately.
- Do not poll in tight loops.
- Keep responses compact and immediate.