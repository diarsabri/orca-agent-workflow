# Receiving-side recovery

1. Identify exact project/worktree, source provider and session/terminal from the
   user's request and Orca metadata. Read installed `orca-cli` guidance. Match the
   source identity; never pick merely the latest session or your own/another worker.
   Ask if genuinely ambiguous before stopping anything.
2. Capture source terminal screen and bounded retained history when available.
   The local helper reads Claude/Codex JSONL without prompting either client:

   ```sh
   python3 .agents/skills/session-recover/scripts/session_context.py list \
     --agent claude --cwd /absolute/task-checkout
   python3 .agents/skills/session-recover/scripts/session_context.py read \
     --agent claude --cwd /absolute/task-checkout --file /exact/session.jsonl
   ```

   Replace the provider as needed. The adapter reports bounded/truncated evidence;
   read earlier relevant records when objectives or decisions are missing. Do not
   enable disabled Orca history indexing or treat snippets as a complete transcript.
3. Inspect current Git status/head, full relevant diff and the approved task. Save
   raw evidence only after verifying its local directory is ignored. Record a
   provisional curated checkpoint in the project's approved handover location.
4. When takeover/closure was requested, stop only the identified source using its
   supported exact-session mechanism. Supervised workers require the owning
   coordinator's guarded stop/recovery protocol. A missing handle, quiet display,
   quota error or logical fence is not physical exit. Account for owned background
   writers; never kill unrelated servers or process names. If shutdown cannot be
   verified, preserve evidence and report the blocker without another writer.
5. Read any final persisted additions and reconcile Git after confirmed exit.
   Finalize the checkpoint with source identity, actual capture/exit receipts,
   objective, branch/head, changes, check provenance, decisions, limits and next action.
   Preserve histories and existing uncommitted work.
6. Continue in the exact existing source checkout, or use Orca's supported handoff
   into that checkout with the checkpoint. A fresh worktree will not carry uncommitted
   changes. Honor prompt-delivery replay receipts and yield ownership after delivery.

Local histories cannot recover remote-only sessions; use the source host/provider
history interface. Keep model budgets, tool permissions and human merge gates intact.
