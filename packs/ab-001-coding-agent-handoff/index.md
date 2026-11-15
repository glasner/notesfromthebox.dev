# A coding-agent handoff with acceptance checks and no implicit merge or deploy permission

> Hand work to a coding agent as a brief pinned to a commit SHA, with re-runnable acceptance checks and a Permissions section that withholds merge, default-branch push and deploy in writing. Then enforce that on the server, because client-side deny rules are easy to sidestep.

- id: `ab-001-coding-agent-handoff` · version 0.1.0 · status private-review · updated 2026-11-15
- last tested 2026-11-15 (helper tools only) · review by 2027-02-15 · retracted: false
- default mode: dry-run · digest: `sha256:e93854b98fd1cebcd2c094eae59e311dd459e1c2d4c78808d77ecc5d7323c781`
- canonical: https://notesfromthebox.dev/packs/ab-001-coding-agent-handoff/

## Fit
- goal: Delegate a bounded code change to an agent (or another bot) so that 'done' means the reviewer re-ran checks and they passed, and the agent could not have landed or shipped the change by itself.
- env: Git repository hosted on GitHub (enforcement section)
- env: Any coding agent that reads a Markdown brief
- env: GitHub protected branches as documented 2026-11
- env: Claude Code permission rules as documented 2026-11 (as one example of a client-side control)
- needs: You can create branch protection rules or rulesets on the repo
- needs: The agent's credentials are not repository-admin credentials
- permission: Repo admin, once, to set branch protection
- do not use: Not a code-review checklist; it covers the contract around the change.
- do not use: Not for exploratory spikes where there is nothing to accept yet; write a research brief instead.
- output: A brief that passes tools/handoff_lint.py, a protected default branch the agent's identity can't bypass, and a report-back containing commands, exit codes and output tails the reviewer can re-run.

## Procedure
_This pack describes a contract. It never grants a consuming agent permission to merge, push or deploy._

1. [read] Pin the base: Record the full commit SHA the work starts from.
   `git rev-parse HEAD`
   expect: 40 hex characters. Branch names move; SHAs don't.
2. [read] Write the brief: Fill packs/assets/ab-001-handoff-template.md: Goal, Base, Scope in/out, Acceptance checks (command + expected result each), Permissions (explicit 'Not allowed' lines for merge, default-branch push, deploy), Stop conditions, Report back.
   expect: Every check is something you, not the agent, can re-run.
3. [read] Lint it: Run the linter and fix what it reports.
   `.venv/bin/python tools/handoff_lint.py brief.md`
   expect: Exit 0, no output.
4. [read] Check server-side enforcement: Confirm the default branch requires a PR, required status checks and an approving review, and that 'Do not allow bypassing' is on or the agent's identity isn't an admin (S1).
   expect: The agent's identity could not merge or push the default branch even if it tried.
5. [write] (Gated) Tighten protection if step 4 failed: Add or edit the branch protection rule / ruleset.
   expect: Re-run step 4; it passes.
   GATE: Repository admin (the owner).
6. [write] Isolate the workspace: Give the agent its own branch and linked worktree from the pinned SHA (S3).
   `git worktree add -b agent/<name> ../wt-<name> <sha>`
   expect: The agent works in a directory no one else is using.
   GATE: Whoever owns the repo checkout; reversible with 'git worktree remove' after the work is saved.
7. [read] Hand off: Send the brief. Client-side deny rules (S2) are a seatbelt, not the lock; the lock is step 4.
   expect: Agent acknowledges Scope and Permissions.
8. [probe] Accept on your own re-run: Check out the agent's final SHA and run every acceptance check yourself. Compare exit codes and output with the report.
   expect: All checks pass on your run. Disagreement with the agent's report is itself a finding.
9. [irreversible] (Gated) Land: Merge and, separately, deploy. Neither is part of the handoff.
   expect: Merge commit references the brief.
   GATE: The owner or the designated lander, after step 8, through the protected-branch flow.

## Verification
- success: tools/handoff_lint.py exits 0 on the brief; the agent's identity is blocked by the server from merging or pushing the default branch; the reviewer's own re-run of every acceptance check matches the expected results before anything lands.
- fail: Linter: 'Permissions must explicitly withhold: merge' (or push / deploy) → The brief is silent on landing, and silence gets read as permission. → Add the 'Not allowed' lines from the template.
- fail: Linter: 'Base must pin a full 40-character commit SHA' → Base is a branch name; the agent and reviewer may test different code. → Step 1.
- fail: Agent pushed to the default branch anyway → Server enforcement missing, or the agent ran with admin credentials that bypass protection by default (S1). → Revert via a PR, rotate to a non-admin token, enable 'Do not allow bypassing'.
- fail: Client deny rule didn't stop a push → Pattern rules don't match rewritten commands such as 'git -C . push' (S2). → Rely on server-side protection; treat client rules as advisory.
- fail: Agent reports green, your re-run is red → Different SHA, environment drift, or a flaky or non-deterministic check. → Compare SHAs first, then environments; don't land.
- rollback: The handoff itself changes nothing. Branch protection edits can be reverted in repo settings. Remove the agent worktree with 'git worktree remove' only after its branch is pushed or bundled.
- tested scope: Tested: the linter against the template and good/bad fixtures (tests/run_tests.py, all passing on 2026-11-15). Not tested in this edition: a live agent run, or branch protection on a live repository.

## Sources
- S1 [About protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches) (GitHub Docs, primary, fetched 2026-11-15): Required reviews and status checks before merging; by default protections don't apply to admins unless 'Do not allow bypassing' is set; protected branches on private repos need a paid plan.
- S2 [Configure permissions (Claude Code)](https://code.claude.com/docs/en/permissions) (Anthropic, primary, fetched 2026-11-15): Rules evaluate deny → ask → allow. A deny rule like Bash(git push *) does not match 'git -C . push' or the same program by path or inside sh -c.
- S3 [git-worktree documentation](https://git-scm.com/docs/git-worktree) (Git project, primary, fetched 2026-11-15, manual unchanged since 2.56.0 (2026-09-28)): One linked worktree per agent so parallel work doesn't share a checkout.

## Uncertainty
- The linter is a regex heuristic. It catches missing structure and obvious grants ('feel free to merge'), not clever wording.
- Client-side permission syntax differs across agent tools and changes often; S2 is one example, not a standard.

License: CC BY 4.0 for text; template and linter MIT. Permissions: Dry-run by default; landing and deploy are always owner-gated.
