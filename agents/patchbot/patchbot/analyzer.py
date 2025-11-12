"""Failure Analyzer - Analyzes CI/CD failure logs and extracts key information."""

import logging
import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class FailureInfo(BaseModel):
    """Extracted failure information."""

    failure_type: str  # test, build, lint, deploy, etc.
    error_message: str
    stack_trace: Optional[str] = None
    failed_files: List[str] = []
    error_lines: Dict[str, List[int]] = {}  # file -> line numbers
    failure_signature: str
    confidence: float  # 0.0 to 1.0


class FailureAnalyzer:
    """
    Analyzes CI/CD failure logs to extract actionable information.

    Supports:
    - Test failures (pytest, unittest, jest, etc.)
    - Build failures (compile errors, dependency issues)
    - Linting errors (ruff, eslint, etc.)
    - Type errors (mypy, typescript)
    """

    # Patterns for different failure types
    PATTERNS = {
        "pytest": [
            r"(?P<file>[^\s]+\.py)::(?P<test>\w+) FAILED",
            r"(?P<file>[^\s]+\.py):(?P<line>\d+): (?P<error>.*)",
            r"AssertionError: (?P<message>.*)",
        ],
        "unittest": [
            r"FAIL: (?P<test>\w+) \((?P<module>[^\)]+)\)",
            r'File "(?P<file>[^"]+)", line (?P<line>\d+)',
            r"AssertionError: (?P<message>.*)",
        ],
        "ruff": [
            r"(?P<file>[^\s:]+):(?P<line>\d+):(?P<col>\d+): (?P<code>\w+) (?P<message>.*)",
        ],
        "mypy": [
            r"(?P<file>[^\s:]+):(?P<line>\d+): error: (?P<message>.*)",
        ],
        "build": [
            r"error: (?P<message>.*)",
            r"(?P<file>[^\s:]+):(?P<line>\d+):(?P<col>\d+): error: (?P<message>.*)",
        ],
        "compile": [
            r"(?P<file>[^\s:]+):(?P<line>\d+):(?P<col>\d+): error: (?P<message>.*)",
            r"compilation failed: (?P<message>.*)",
        ],
    }

    def analyze(self, context: Dict[str, Any]) -> FailureInfo:
        """
        Analyze failure context and extract key information.

        Args:
            context: Task context with logs, error messages, etc.

        Returns:
            FailureInfo with extracted details
        """
        failure_type = context.get("failure_type", "unknown")
        error_log = context.get("error_log", "")
        build_log = context.get("build_log", "")
        repository = context.get("repository", "")

        logger.info(f"Analyzing {failure_type} failure for {repository}")

        # Combine logs
        full_log = f"{error_log}\n{build_log}"

        # Extract error message
        error_message = self._extract_error_message(full_log, failure_type)

        # Extract stack trace
        stack_trace = self._extract_stack_trace(full_log)

        # Extract failed files
        failed_files = self._extract_files(full_log, failure_type)

        # Extract error lines
        error_lines = self._extract_error_lines(full_log, failure_type)

        # Generate failure signature
        failure_signature = self._generate_signature(
            failure_type, error_message, failed_files
        )

        # Calculate confidence
        confidence = self._calculate_confidence(
            error_message, failed_files, error_lines
        )

        return FailureInfo(
            failure_type=failure_type,
            error_message=error_message,
            stack_trace=stack_trace,
            failed_files=failed_files,
            error_lines=error_lines,
            failure_signature=failure_signature,
            confidence=confidence,
        )

    def _extract_error_message(self, log: str, failure_type: str) -> str:
        """Extract main error message from log."""
        # Try type-specific patterns
        patterns = self.PATTERNS.get(failure_type, [])

        for pattern in patterns:
            match = re.search(pattern, log, re.MULTILINE)
            if match and "message" in match.groupdict():
                return match.group("message").strip()

        # Fallback: Look for common error indicators
        error_lines = []
        for line in log.split("\n"):
            lower = line.lower()
            if any(
                keyword in lower
                for keyword in ["error:", "failed:", "exception:", "traceback"]
            ):
                error_lines.append(line.strip())

        if error_lines:
            return error_lines[0][:500]  # Limit length

        return "Unknown error"

    def _extract_stack_trace(self, log: str) -> Optional[str]:
        """Extract stack trace from log."""
        # Look for traceback section
        lines = log.split("\n")
        trace_lines = []
        in_trace = False

        for line in lines:
            if "Traceback" in line or "Stack trace" in line:
                in_trace = True

            if in_trace:
                trace_lines.append(line)

                # End of trace
                if line.strip() and not line.startswith(" ") and len(trace_lines) > 1:
                    break

        if trace_lines:
            return "\n".join(trace_lines[:50])  # Limit to 50 lines

        return None

    def _extract_files(self, log: str, failure_type: str) -> List[str]:
        """Extract file paths mentioned in errors."""
        files = set()

        # Type-specific patterns
        patterns = self.PATTERNS.get(failure_type, [])

        for pattern in patterns:
            for match in re.finditer(pattern, log, re.MULTILINE):
                if "file" in match.groupdict():
                    file_path = match.group("file")
                    # Clean up path
                    file_path = file_path.strip('"\'')
                    if file_path and not file_path.startswith("/"):
                        files.add(file_path)

        # Generic file pattern
        file_pattern = r"([a-zA-Z0-9_\-/]+\.(py|js|ts|go|java|cpp|rs))"
        for match in re.finditer(file_pattern, log):
            file_path = match.group(1)
            files.add(file_path)

        return sorted(list(files))[:10]  # Limit to 10 files

    def _extract_error_lines(
        self, log: str, failure_type: str
    ) -> Dict[str, List[int]]:
        """Extract line numbers where errors occurred."""
        error_lines = {}

        patterns = self.PATTERNS.get(failure_type, [])

        for pattern in patterns:
            for match in re.finditer(pattern, log, re.MULTILINE):
                groups = match.groupdict()
                if "file" in groups and "line" in groups:
                    file_path = groups["file"].strip('"\'')
                    line_num = int(groups["line"])

                    if file_path not in error_lines:
                        error_lines[file_path] = []

                    error_lines[file_path].append(line_num)

        # Deduplicate and sort
        for file_path in error_lines:
            error_lines[file_path] = sorted(list(set(error_lines[file_path])))

        return error_lines

    def _generate_signature(
        self, failure_type: str, error_message: str, files: List[str]
    ) -> str:
        """Generate unique failure signature."""
        # Normalize error message (remove dynamic parts)
        normalized = re.sub(r"\d+", "N", error_message)  # Replace numbers
        normalized = re.sub(r"0x[0-9a-fA-F]+", "0xHEX", normalized)  # Replace hex
        normalized = re.sub(r"/[^\s]+", "PATH", normalized)  # Replace paths

        # Create signature
        file_part = "|".join(sorted(files)[:3]) if files else "unknown"
        signature = f"{failure_type}:{file_part}:{normalized[:100]}"

        return signature

    def _calculate_confidence(
        self,
        error_message: str,
        files: List[str],
        error_lines: Dict[str, List[int]],
    ) -> float:
        """Calculate confidence score for fix success."""
        confidence = 0.5  # Base confidence

        # Increase confidence if we have specific information
        if error_message and error_message != "Unknown error":
            confidence += 0.2

        if files:
            confidence += 0.1

        if error_lines:
            confidence += 0.2

        return min(confidence, 1.0)
