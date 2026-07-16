---
name: git-commit
description: Stage all changes since the last commit and commit with the given message
disable-model-invocation: true
argument-hint: "<commit message>"
allowed-tools: Bash(git add:*), Bash(git status:*), Bash(git diff:*), Bash(git commit:*)
---

Create a git commit with the exact message provided by the user.

Commit message: $ARGUMENTS

Steps:
1. Run `git status` and `git diff` to confirm which files changed since the last commit.
2. Run `git add -A` to stage all changed files (modified, new, and deleted).
3. Run `git commit -m "$ARGUMENTS"` using the message exactly as given — do not rewrite,
   extend, or reformat it.
4. Show the output of `git log -1 --stat` to confirm the commit.

Do NOT push. Do NOT amend previous commits. If $ARGUMENTS is empty, stop and ask
for a commit message instead of inventing one.

Example usage is:
/commit-git "fix: snapshot exporter label handling"