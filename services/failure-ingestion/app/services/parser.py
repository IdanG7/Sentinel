"""Parsers for CI/CD webhook payloads."""

import logging
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class FailureParser(ABC):
    """Base class for CI/CD failure parsers."""

    @abstractmethod
    async def parse(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Parse CI/CD webhook payload into standardized failure context."""
        pass

    def classify_failure_type(self, logs: str, error_message: str) -> str:
        """
        Classify failure type based on logs and error messages.

        Returns:
            Failure type: test, build, lint, type_check, compile, etc.
        """
        # Patterns for different failure types
        patterns = {
            "lint": [
                r"eslint",
                r"pylint",
                r"rubocop",
                r"flake8",
                r"golangci-lint",
                r"ruff check",
            ],
            "format": [
                r"prettier",
                r"black",
                r"gofmt",
                r"rustfmt",
            ],
            "type_check": [
                r"mypy",
                r"typescript",
                r"type error",
                r"tsc",
            ],
            "test": [
                r"pytest",
                r"jest",
                r"mocha",
                r"rspec",
                r"go test",
                r"test.*failed",
                r"assertion",
            ],
            "build": [
                r"build failed",
                r"compilation error",
                r"webpack",
                r"cargo build",
                r"go build",
            ],
            "dependency": [
                r"npm install",
                r"pip install",
                r"cargo install",
                r"dependency",
                r"modulenotfounderror",
            ],
        }

        # Check patterns
        combined_text = f"{logs.lower()} {error_message.lower()}"

        for failure_type, type_patterns in patterns.items():
            for pattern in type_patterns:
                if re.search(pattern, combined_text, re.IGNORECASE):
                    return failure_type

        return "unknown"

    def extract_error_message(self, logs: str) -> str:
        """
        Extract primary error message from logs.

        Args:
            logs: Full CI/CD logs

        Returns:
            Primary error message
        """
        # Common error patterns
        error_patterns = [
            r"Error: (.+)",
            r"ERROR: (.+)",
            r"FAILED (.+)",
            r"Exception: (.+)",
            r"\[error\] (.+)",
        ]

        for pattern in error_patterns:
            match = re.search(pattern, logs, re.MULTILINE | re.IGNORECASE)
            if match:
                return match.group(1).strip()[:500]  # Limit length

        # Fallback: take last non-empty line
        lines = [line.strip() for line in logs.split("\n") if line.strip()]
        if lines:
            return lines[-1][:500]

        return "Unknown error"


class GitHubParser(FailureParser):
    """Parser for GitHub Actions webhooks."""

    async def parse_workflow_run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Parse GitHub workflow_run event."""
        workflow_run = payload.get("workflow_run", {})
        repository = payload.get("repository", {})

        # Extract basic info
        repo_full_name = repository.get("full_name")
        branch = workflow_run.get("head_branch")
        build_url = workflow_run.get("html_url")

        # Fetch logs (in real implementation, would make API call)
        # For now, use placeholder
        logs = "GitHub Actions logs would be fetched here via API"
        error_message = self.extract_error_message(logs)

        # Classify failure
        failure_type = self.classify_failure_type(logs, error_message)

        context = {
            "repository": repo_full_name,
            "repository_url": repository.get("clone_url"),
            "branch": branch,
            "commit_sha": workflow_run.get("head_sha"),
            "build_url": build_url,
            "workflow_name": workflow_run.get("name"),
            "run_id": workflow_run.get("id"),
            "run_number": workflow_run.get("run_number"),
            "failure_type": failure_type,
            "error": error_message,
            "logs": logs[:5000],  # Limit log size
            "timestamp": workflow_run.get("updated_at"),
            "ci_provider": "github",
        }

        logger.info(f"Parsed GitHub failure: {repo_full_name} - {failure_type}")

        return context


class GitLabParser(FailureParser):
    """Parser for GitLab CI webhooks."""

    async def parse_pipeline(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Parse GitLab pipeline event."""
        object_attributes = payload.get("object_attributes", {})
        project = payload.get("project", {})

        # Extract basic info
        repo_path = project.get("path_with_namespace")
        branch = object_attributes.get("ref")
        build_url = project.get("web_url") + f"/-/pipelines/{object_attributes.get('id')}"

        # Fetch logs (in real implementation, would make API call)
        logs = "GitLab CI logs would be fetched here via API"
        error_message = self.extract_error_message(logs)

        # Classify failure
        failure_type = self.classify_failure_type(logs, error_message)

        context = {
            "repository": repo_path,
            "repository_url": project.get("git_http_url"),
            "branch": branch,
            "commit_sha": object_attributes.get("sha"),
            "build_url": build_url,
            "pipeline_id": object_attributes.get("id"),
            "failure_type": failure_type,
            "error": error_message,
            "logs": logs[:5000],  # Limit log size
            "timestamp": object_attributes.get("finished_at"),
            "ci_provider": "gitlab",
        }

        logger.info(f"Parsed GitLab failure: {repo_path} - {failure_type}")

        return context
