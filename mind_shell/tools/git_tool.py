"""
nexus/tools/git_tool.py — Git integration tool.

Wraps GitPython to provide AI-friendly Git operations:
  status, diff, log, show, add, commit, branch, checkout, stash
"""

from __future__ import annotations

from pathlib import Path

from mind_shell.tools.base_tool import BaseTool, ToolResult


class GitTool(BaseTool):
    name = "git"
    description = (
        "Interact with the local Git repository. "
        "Read status, diffs, logs, and branches. Create commits and branches."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["status", "diff", "log", "show", "add", "commit",
                         "branch", "checkout", "stash", "blame"],
                "description": "Git operation to perform.",
            },
            "path": {
                "type": "string",
                "description": "Repository path (default: current directory).",
                "default": ".",
            },
            "files": {
                "type": "array",
                "items": {"type": "string"},
                "description": "File paths for add/diff/blame operations.",
            },
            "message": {
                "type": "string",
                "description": "Commit message (required for commit action).",
            },
            "branch": {
                "type": "string",
                "description": "Branch name for branch/checkout operations.",
            },
            "ref": {
                "type": "string",
                "description": "Commit ref/hash for show/log operations.",
            },
            "max_count": {
                "type": "integer",
                "description": "Max commits to show in log (default: 10).",
                "default": 10,
            },
            "staged": {
                "type": "boolean",
                "description": "Show staged diff instead of working tree.",
                "default": False,
            },
        },
        "required": ["action"],
    }

    async def execute(self, tool_input: dict) -> ToolResult:
        try:
            import git as gitpython
        except ImportError:
            return ToolResult(output="", success=False,
                              error="GitPython not installed. Run: pip install gitpython")

        action = tool_input.get("action")
        repo_path = Path(tool_input.get("path", ".")).expanduser()

        try:
            repo = gitpython.Repo(repo_path, search_parent_directories=True)
        except gitpython.InvalidGitRepositoryError:
            return ToolResult(output="", success=False,
                              error=f"Not a Git repository: {repo_path.absolute()}")
        except Exception as e:
            return ToolResult(output="", success=False, error=str(e))

        try:
            if action == "status":
                return self._status(repo)
            elif action == "diff":
                return self._diff(repo, tool_input)
            elif action == "log":
                return self._log(repo, tool_input)
            elif action == "show":
                return self._show(repo, tool_input)
            elif action == "add":
                return self._add(repo, tool_input)
            elif action == "commit":
                return self._commit(repo, tool_input)
            elif action == "branch":
                return self._branch(repo, tool_input)
            elif action == "checkout":
                return self._checkout(repo, tool_input)
            elif action == "stash":
                return self._stash(repo)
            elif action == "blame":
                return self._blame(repo, tool_input)
            else:
                return ToolResult(output="", success=False, error=f"Unknown action: {action}")
        except Exception as e:
            return ToolResult(output="", success=False, error=f"Git error: {e}")

    def _status(self, repo) -> ToolResult:
        lines = [f"# Git Status — {repo.working_dir}\n"]
        lines.append(f"Branch: **{repo.active_branch.name}**")

        if repo.head.is_valid():
            commit = repo.head.commit
            lines.append(f"Last commit: `{commit.hexsha[:8]}` — {commit.summary}")

        staged = repo.index.diff("HEAD") if repo.head.is_valid() else []
        unstaged = repo.index.diff(None)
        untracked = repo.untracked_files

        if staged:
            lines.append(f"\n**Staged ({len(staged)}):**")
            for d in staged:
                lines.append(f"  ✅ {d.change_type} {d.a_path}")
        if unstaged:
            lines.append(f"\n**Modified ({len(unstaged)}):**")
            for d in unstaged:
                lines.append(f"  📝 {d.change_type} {d.a_path}")
        if untracked:
            lines.append(f"\n**Untracked ({len(untracked)}):**")
            for f in untracked[:20]:
                lines.append(f"  ❓ {f}")

        if not staged and not unstaged and not untracked:
            lines.append("\n✨ Working tree clean")

        return ToolResult(output="\n".join(lines))

    def _diff(self, repo, tool_input: dict) -> ToolResult:
        staged = tool_input.get("staged", False)
        files = tool_input.get("files", [])

        if staged:
            diffs = repo.index.diff("HEAD")
        else:
            diffs = repo.index.diff(None)

        if files:
            diffs = [d for d in diffs if d.a_path in files or d.b_path in files]

        if not diffs:
            return ToolResult(output="No changes to show.")

        output_parts = []
        for diff in diffs[:10]:
            output_parts.append(f"## {diff.a_path}")
            if diff.diff:
                diff_text = diff.diff.decode("utf-8", errors="replace")
                output_parts.append(f"```diff\n{diff_text[:3000]}\n```")

        return ToolResult(output="\n\n".join(output_parts))

    def _log(self, repo, tool_input: dict) -> ToolResult:
        max_count = tool_input.get("max_count", 10)
        ref = tool_input.get("ref", "HEAD")

        lines = [f"# Git Log (last {max_count} commits)\n"]
        for commit in list(repo.iter_commits(ref, max_count=max_count)):
            lines.append(
                f"- `{commit.hexsha[:8]}` **{commit.summary}**  "
                f"— {commit.author.name} ({commit.committed_datetime.strftime('%Y-%m-%d')})"
            )

        return ToolResult(output="\n".join(lines))

    def _show(self, repo, tool_input: dict) -> ToolResult:
        ref = tool_input.get("ref", "HEAD")
        commit = repo.commit(ref)
        lines = [
            f"# Commit {commit.hexsha[:8]}",
            f"Author: {commit.author.name} <{commit.author.email}>",
            f"Date: {commit.committed_datetime.strftime('%Y-%m-%d %H:%M:%S')}",
            f"\n{commit.message}",
        ]
        for diff in list(commit.diff(commit.parents[0] if commit.parents else None))[:5]:
            if diff.diff:
                lines.append(f"\n## {diff.a_path}")
                lines.append(f"```diff\n{diff.diff.decode('utf-8', errors='replace')[:2000]}\n```")
        return ToolResult(output="\n".join(lines))

    def _add(self, repo, tool_input: dict) -> ToolResult:
        files = tool_input.get("files", ["."])
        repo.index.add(files)
        return ToolResult(output=f"Staged: {', '.join(files)}")

    def _commit(self, repo, tool_input: dict) -> ToolResult:
        message = tool_input.get("message", "")
        if not message:
            return ToolResult(output="", success=False, error="Commit message is required.")
        repo.index.commit(message)
        return ToolResult(output=f"Committed: {message}")

    def _branch(self, repo, tool_input: dict) -> ToolResult:
        lines = ["# Branches\n"]
        for branch in repo.heads:
            marker = "→" if branch == repo.active_branch else " "
            lines.append(f"{marker} {branch.name}")
        return ToolResult(output="\n".join(lines))

    def _checkout(self, repo, tool_input: dict) -> ToolResult:
        branch = tool_input.get("branch", "")
        if not branch:
            return ToolResult(output="", success=False, error="Branch name is required.")
        repo.heads[branch].checkout()
        return ToolResult(output=f"Checked out: {branch}")

    def _stash(self, repo) -> ToolResult:
        repo.git.stash()
        return ToolResult(output="Changes stashed.")

    def _blame(self, repo, tool_input: dict) -> ToolResult:
        return ToolResult(output="Blame not yet implemented.")
