# Recover a stuck task or worker session with evidence and a reversible cleanup

> When a task says 'in progress' but its worker is dead or hung, first classify it from read-only evidence, then snapshot everything (git bundle, patch, untracked files, a VACUUM INTO copy of the tracker DB) before proposing a cleanup. Nothing is deleted without the owner's approval.

- id: `ab-002-stuck-session-recovery` · version 0.1.0 · status private-review · updated 2026-11-15
- last tested 2026-11-15 (partially) · review by 2027-02-15 · retracted: false
- default mode: read-only · digest: `sha256:c59d32607a327732cee0d383698d1a7ec36e8a1f5f35af46f02d023537a6c14b`
- canonical: https://notesfromthebox.dev/packs/ab-002-stuck-session-recovery/

## Fit
- goal: Get a task unstuck without losing the worker's uncommitted work and without making a change to the task database that can't be undone.
- env: A git worktree per task or worker
- env: A task tracker backed by SQLite (the DB steps); adapt for other stores
- env: Workers in terminal sessions or background processes
- env: git 2.47 (tested); git-bundle and git-worktree as documented 2026-11
- env: SQLite with VACUUM INTO (3.27+)
- needs: Read access to the worktree and DB file
- needs: Enough free disk for one copy of the DB and the bundle
- permission: Read-only for steps 1–5
- permission: Owner approval for any step that changes task state, kills a process, or removes a worktree/branch
- do not use: Not for a worker that is alive and making progress; leave it alone.
- do not use: Not for databases you can't safely open read-only (e.g. a server DB); use that system's own backup tool.
- output: An evidence directory with a manifest, a one-line classification, and a written cleanup plan with exact commands and a rollback for each, waiting on the owner.

## Procedure
_Reference material. It never authorises killing a process, editing a DB or deleting anything._

1. [read] Read the task row: Open the DB read-only and read the stuck task's status, assignee, lease/heartbeat time and last update.
   `python3 -c "import sqlite3;c=sqlite3.connect('file:tasks.db?mode=ro',uri=True);print(c.execute('select * from task where id=?',(ID,)).fetchall())"`
   expect: You know what the tracker believes.
2. [read] Is the worker alive?: Look for its process and its terminal session; read the session's last screen or log without typing into it.
   `ps -eo pid,etime,stat,cmd | grep -i '<worker>'`
   expect: Alive & progressing / alive & waiting on input / gone.
3. [read] What's in the worktree?: Status, recent commits, worktree registration.
   `git -C <wt> status --porcelain=v1 --branch; git -C <wt> log --oneline -n 10; git -C <wt> worktree list`
   expect: Commits ahead, uncommitted changes, untracked files: the work at risk.
4. [read] Classify: Pick one: (a) alive and progressing: stop here; (b) alive and blocked on a prompt; (c) dead with unsaved work; (d) dead, nothing at risk; (e) tracker row wrong but worker fine.
   expect: One letter plus the evidence lines.
5. [read] Snapshot before anything else: Write an evidence directory: git status/log, binary patch, untracked tarball, verified bundle, VACUUM INTO copy of the DB with integrity_check, SHA-256 manifest. Source is opened read-only.
   `.venv/bin/python tools/snapshot_before_cleanup.py --worktree <wt> --db <tasks.db> --out ~/backups/stuck-<task>-$(date +%Y%m%d-%H%M%S)`
   expect: 'snapshot written … (N files)'; snapshot.json shows integrity_check ok.
6. [read] Write the cleanup plan: For each proposed change, list the exact command, why, and its rollback. Typical: answer the blocked prompt (b); release or reassign the task (c, d, e); keep the worktree and lock it with a reason rather than removing it.
   expect: A plan the owner can approve line by line.
7. [write] (Gated) Change task state: Use the tracker's own API or CLI to release or reassign the task, not a hand-written UPDATE, if one exists.
   expect: Tracker shows the new state; the step 5 snapshot still exists.
   GATE: Owner approval. Rollback = restore the field values recorded in step 1, or the db-backup copy as a last resort.
8. [write] (Gated) Stop a hung worker: Send a polite interrupt or quit through the session first; a signal only if that fails.
   expect: Process gone, worktree unchanged since the latest snapshot.
   GATE: Owner approval. Re-run step 5 afterwards if the worker wrote anything while stopping.
9. [irreversible] (Gated) Remove a worktree or branch: Only after its commits are pushed or bundled and its uncommitted work is in the snapshot. Dry-run first.
   `git worktree prune -n -v   # then, if approved: git worktree remove <wt>`
   expect: Removed only what was named.
   GATE: Owner's explicit yes for each worktree/branch named. Default answer is keep (or 'git worktree lock --reason').

## Verification
- success: An evidence directory exists whose MANIFEST.sha256 re-verifies, the DB copy passes integrity_check, the task is in the state the owner approved, and no worktree, branch or session was removed without a recorded yes.
- fail: snapshot tool: 'refusing to write into non-empty …' → You pointed it at an existing evidence directory. → Use a new timestamped path; never overwrite evidence.
- fail: VACUUM INTO fails with 'output file already exists' → The target must not exist (S1). → New path.
- fail: 'database is locked' or busy errors while reading → A writer holds a lock. VACUUM INTO only needs a read transaction, but a long write can still block it. → Retry after the write; don't kill the writer just to take a backup.
- fail: Restored files differ from the worktree → Work was written after the snapshot, or the patch didn't include binaries. → Re-snapshot; the tool uses 'git diff --binary HEAD'.
- fail: Worktree directory gone but 'git worktree list' still shows it → Someone deleted it by hand; stale admin files remain (S3). → 'git worktree prune -n -v' to see, then prune with approval.
- fail: Task row flips back to in progress → The worker was alive after all and renewed its lease. → Back to step 2; it was class (a) or (b).
- rollback: Steps 1–6 change nothing. Step 7: restore the recorded field values via the tracker (or, if the tracker is broken, restore db-backup.sqlite with the owner's approval after backing up the current file). Step 8: restart the worker on the same worktree. Step 9 has no rollback except recreating from the bundle + patch + tarball, which is why it is gated hardest.
- tested scope: Tested: step 5 (snapshot tool) end to end on synthetic fixtures, including read-only proof and a full restore. Not tested this edition: steps 1–4 and 6–9 against a live tracker and real worker sessions.

## Sources
- S1 [VACUUM (INTO clause)](https://sqlite.org/lang_vacuum.html) (SQLite, primary, fetched 2026-11-15): VACUUM INTO leaves the original unchanged and writes a consistent snapshot; the target must not already exist; it's an alternative to the backup API.
- S2 [git-bundle documentation](https://git-scm.com/docs/git-bundle) (Git project, primary, fetched 2026-11-15): Bundles back up refs and commits only, not the index, working tree or stash, so uncommitted work needs a separate patch; bundles can be verified and cloned from.
- S3 [git-worktree documentation](https://git-scm.com/docs/git-worktree) (Git project, primary, fetched 2026-11-15): worktree list/lock/prune/remove; deleting a worktree directory by hand leaves stale admin files that 'prune' cleans; 'prune -n' is a dry run.

## Uncertainty
- Tested on a toy repo and DB, not a large production tracker. VACUUM INTO needs free space roughly equal to the DB size.
- Classification of 'hung vs. thinking' is a judgment call; the pack asks for evidence, not certainty.
- The tool doesn't capture git stash entries or per-repo config/hooks (S2). Note them by hand if they matter.

License: CC BY 4.0 for text; snapshot tool MIT. Permissions: Read-only by default; deletion always needs a per-item owner yes.
