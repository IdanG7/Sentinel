"""Tests for CI/CD parsers."""

import pytest

from app.services.parser import FailureParser, GitHubParser, GitLabParser


class TestFailureParser:
    """Tests for base FailureParser."""

    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return FailureParser()

    def test_classify_lint_failure(self, parser):
        """Test classification of linting failures."""
        logs = "Running eslint... Error: x is not defined"
        error = "ESLint: x is not defined"

        failure_type = parser.classify_failure_type(logs, error)
        assert failure_type == "lint"

    def test_classify_test_failure(self, parser):
        """Test classification of test failures."""
        logs = "Running pytest... FAILED test_example.py::test_foo"
        error = "AssertionError: expected 1, got 2"

        failure_type = parser.classify_failure_type(logs, error)
        assert failure_type == "test"

    def test_classify_build_failure(self, parser):
        """Test classification of build failures."""
        logs = "webpack build failed with errors"
        error = "Build failed: compilation error"

        failure_type = parser.classify_failure_type(logs, error)
        assert failure_type == "build"

    def test_classify_type_check_failure(self, parser):
        """Test classification of type check failures."""
        logs = "Running mypy... error: Incompatible types"
        error = "Type error in foo.py"

        failure_type = parser.classify_failure_type(logs, error)
        assert failure_type == "type_check"

    def test_extract_error_message(self, parser):
        """Test error message extraction."""
        logs = """
        Step 1: Building...
        Step 2: Running tests...
        Error: Test failed in test_example.py
        Process completed with exit code 1
        """

        error = parser.extract_error_message(logs)
        assert "Error:" in error or "Test failed" in error


class TestGitHubParser:
    """Tests for GitHub parser."""

    @pytest.fixture
    def parser(self):
        """Create GitHub parser instance."""
        return GitHubParser()

    @pytest.mark.asyncio
    async def test_parse_workflow_run(self, parser):
        """Test parsing GitHub workflow_run event."""
        payload = {
            "workflow_run": {
                "id": 123456,
                "name": "CI",
                "head_branch": "main",
                "head_sha": "abc123",
                "html_url": "https://github.com/org/repo/actions/runs/123456",
                "updated_at": "2024-01-01T12:00:00Z",
                "run_number": 42,
            },
            "repository": {
                "full_name": "org/repo",
                "clone_url": "https://github.com/org/repo.git",
            },
        }

        context = await parser.parse_workflow_run(payload)

        assert context["repository"] == "org/repo"
        assert context["branch"] == "main"
        assert context["commit_sha"] == "abc123"
        assert context["ci_provider"] == "github"
        assert context["workflow_name"] == "CI"
        assert "failure_type" in context


class TestGitLabParser:
    """Tests for GitLab parser."""

    @pytest.fixture
    def parser(self):
        """Create GitLab parser instance."""
        return GitLabParser()

    @pytest.mark.asyncio
    async def test_parse_pipeline(self, parser):
        """Test parsing GitLab pipeline event."""
        payload = {
            "object_attributes": {
                "id": 123456,
                "ref": "main",
                "sha": "abc123",
                "status": "failed",
                "finished_at": "2024-01-01T12:00:00Z",
            },
            "project": {
                "path_with_namespace": "org/repo",
                "git_http_url": "https://gitlab.com/org/repo.git",
                "web_url": "https://gitlab.com/org/repo",
            },
        }

        context = await parser.parse_pipeline(payload)

        assert context["repository"] == "org/repo"
        assert context["branch"] == "main"
        assert context["commit_sha"] == "abc123"
        assert context["ci_provider"] == "gitlab"
        assert "failure_type" in context
