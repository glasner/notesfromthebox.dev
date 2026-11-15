# Handoff: <short task name>

## Goal
One paragraph: what should be true when this is done, in user-visible terms.

## Base
- Repository: <repo>
- Branch to create: <agent/short-name>
- Base commit: <full 40-character SHA>   (not a branch name; branches move)

## Scope
- In: <files/modules the agent may change>
- Out: <things it must not touch: migrations, CI config, secrets, other packages>

## Acceptance checks
Each check is a command the reviewer will re-run, plus the expected result.
1. `<test command>`, expect exit 0 and "<N passed>"
2. `<lint/typecheck command>`, expect exit 0
3. `<behavioural check, e.g. curl or a script>`, expect "<exact output>"
4. Manual: <what a human looks at>, expect <observable result>

## Permissions
- Allowed: edit files inside Scope, run the checks above, commit to the new branch, push the new branch.
- Not allowed: merge, or open-and-merge, any pull request.
- Not allowed: push to main, master or the default branch, or force-push anything.
- Not allowed: deploy, release, publish, or change production data.
- Not allowed: delete branches, worktrees, tags or files outside Scope.
- No new dependencies without asking.

## Stop conditions
Stop and report instead of continuing if:
- a check fails twice for the same reason,
- the fix needs a file outside Scope,
- anything asks for a credential, a production change, or a destructive command.

## Report back
- Branch name and final commit SHA
- For each acceptance check: the exact command, exit code, last 20 lines of output
- What you did NOT do from the Goal, and why
- Anything you are unsure about
