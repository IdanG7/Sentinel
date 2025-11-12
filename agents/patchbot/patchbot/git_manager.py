"""Git Manager - Handles git operations and PR creation."""

import logging
import os
import shutil
from pathlib import Path
from typing import Optional

import git
from github import Github
from github.PullRequest import PullRequest

from .config import PatchBotConfig
from .fixer import FixResult

logger = logging.getLogger(__name__)


class GitManager:
    """
    Manages git operations and GitHub PR creation.

    Workflow:
    1. Clone repository
    2. Create branch
    3. Apply fixes
    4. Commit changes
    5. Push branch
    6. Create pull request
    """

    def __init__(self, config: PatchBotConfig):
        """Initialize Git Manager."""
        self.config = config
        self.github = Github(config.github_token) if config.github_token else None

    def clone_repository(self, repo_url: str, branch: str = "main") -> Path:
        """
        Clone repository to workspace.

        Args:
            repo_url: Repository URL
            branch: Branch to clone

        Returns:
            Path to cloned repository
        """
        # Extract repo name
        repo_name = repo_url.split("/")[-1].replace(".git", "")
        repo_path = Path(self.config.workspace_dir) / repo_name

        # Clean up existing
        if repo_path.exists():
            shutil.rmtree(repo_path)

        # Ensure workspace directory exists
        repo_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Cloning {repo_url} to {repo_path}")

        # Clone
        git.Repo.clone_from(
            repo_url,
            repo_path,
            branch=branch,
            depth=1,  # Shallow clone
        )

        logger.info(f"✓ Repository cloned to {repo_path}")

        return repo_path

    def create_fix_branch(self, repo_path: Path, failure_signature: str) -> str:
        """
        Create a new branch for the fix.

        Args:
            repo_path: Path to repository
            failure_signature: Unique failure identifier

        Returns:
            Branch name
        """
        repo = git.Repo(repo_path)

        # Generate branch name
        # Clean signature for branch name
        clean_sig = failure_signature.replace(":", "-").replace("|", "-")[:50]
        branch_name = f"patchbot/fix-{clean_sig}"

        logger.info(f"Creating branch: {branch_name}")

        # Create and checkout branch
        repo.git.checkout("-b", branch_name)

        return branch_name

    def apply_fixes(self, repo_path: Path, fix_result: FixResult) -> int:
        """
        Apply fixes to repository files.

        Args:
            repo_path: Path to repository
            fix_result: Fixes to apply

        Returns:
            Number of files modified
        """
        modified_count = 0

        for fix in fix_result.fixes:
            file_path = repo_path / fix.file_path

            if not file_path.exists():
                logger.warning(f"File not found: {fix.file_path}")
                continue

            logger.info(f"Applying fix to {fix.file_path}")

            # Write fixed content
            file_path.write_text(fix.fixed_content)
            modified_count += 1

        logger.info(f"✓ Applied {modified_count} fixes")

        return modified_count

    def commit_changes(
        self, repo_path: Path, fix_result: FixResult, failure_type: str
    ) -> str:
        """
        Commit changes to git.

        Args:
            repo_path: Path to repository
            fix_result: Fix result with summary
            failure_type: Type of failure

        Returns:
            Commit SHA
        """
        repo = git.Repo(repo_path)

        # Configure git user
        with repo.config_writer() as config:
            config.set_value("user", "name", self.config.git_author_name)
            config.set_value("user", "email", self.config.git_author_email)

        # Stage changes
        repo.git.add(A=True)

        # Create commit message
        commit_msg = f"""fix({failure_type}): {fix_result.summary}

{fix_result.summary}

Files modified:
{chr(10).join(f'- {fix.file_path}' for fix in fix_result.fixes)}

Fix confidence: {fix_result.confidence:.2f}

🤖 Automated fix by PatchBot
"""

        # Commit
        commit = repo.index.commit(commit_msg)

        logger.info(f"✓ Changes committed: {commit.hexsha[:8]}")

        return commit.hexsha

    def push_branch(self, repo_path: Path, branch_name: str) -> None:
        """
        Push branch to remote.

        Args:
            repo_path: Path to repository
            branch_name: Branch to push
        """
        repo = git.Repo(repo_path)

        logger.info(f"Pushing branch: {branch_name}")

        # Push to origin
        origin = repo.remote("origin")
        origin.push(branch_name)

        logger.info(f"✓ Branch pushed: {branch_name}")

    def create_pull_request(
        self,
        repository: str,
        branch_name: str,
        base_branch: str,
        fix_result: FixResult,
        failure_type: str,
        build_url: Optional[str] = None,
    ) -> Optional[PullRequest]:
        """
        Create GitHub pull request.

        Args:
            repository: Repository name (org/repo)
            branch_name: Head branch with fixes
            base_branch: Base branch to merge into
            fix_result: Fix result with details
            failure_type: Type of failure
            build_url: Optional CI/CD build URL

        Returns:
            GitHub PullRequest object or None
        """
        if not self.github:
            logger.warning("GitHub client not configured, skipping PR creation")
            return None

        logger.info(f"Creating pull request for {repository}")

        try:
            # Get repository
            repo = self.github.get_repo(repository)

            # Create PR title
            title = f"🤖 Fix {failure_type} failure: {fix_result.summary[:80]}"

            # Create PR body
            body = f"""## 🤖 Automated Fix by PatchBot

**Failure Type**: {failure_type}
**Fix Confidence**: {fix_result.confidence:.1%}

### Summary

{fix_result.summary}

### Changes

"""

            for fix in fix_result.fixes:
                body += f"""
#### `{fix.file_path}`

{fix.explanation}

"""

            if build_url:
                body += f"\n**Original Build**: {build_url}\n"

            body += """
---

This pull request was automatically generated by PatchBot, an AI agent for autonomous CI/CD failure resolution.

**Please review carefully before merging.**
"""

            # Create PR
            pr = repo.create_pull(
                title=title,
                body=body,
                head=branch_name,
                base=base_branch,
            )

            # Add labels
            if self.config.pr_labels:
                pr.add_to_labels(*self.config.pr_labels)

            logger.info(f"✓ Pull request created: {pr.html_url}")

            return pr

        except Exception as e:
            logger.error(f"Failed to create pull request: {e}")
            return None

    def cleanup_workspace(self, repo_path: Path) -> None:
        """
        Clean up workspace.

        Args:
            repo_path: Path to repository
        """
        if self.config.cleanup_workspace and repo_path.exists():
            logger.info(f"Cleaning up workspace: {repo_path}")
            shutil.rmtree(repo_path)

    def read_files(self, repo_path: Path, file_paths: list[str]) -> dict[str, str]:
        """
        Read file contents from repository.

        Args:
            repo_path: Path to repository
            file_paths: List of file paths to read

        Returns:
            Dict of file_path -> content
        """
        contents = {}

        for file_path in file_paths:
            full_path = repo_path / file_path

            if full_path.exists() and full_path.is_file():
                try:
                    contents[file_path] = full_path.read_text()
                except Exception as e:
                    logger.warning(f"Failed to read {file_path}: {e}")

        return contents
