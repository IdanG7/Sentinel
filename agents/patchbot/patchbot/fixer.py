"""Code Fixer - Uses Claude AI to generate fixes for failures."""

import logging
from typing import Dict, List, Optional

from anthropic import AsyncAnthropic
from pydantic import BaseModel

from .analyzer import FailureInfo
from .config import PatchBotConfig

logger = logging.getLogger(__name__)


class CodeFix(BaseModel):
    """Generated code fix."""

    file_path: str
    original_content: str
    fixed_content: str
    explanation: str
    confidence: float


class FixResult(BaseModel):
    """Complete fix result."""

    fixes: List[CodeFix]
    summary: str
    confidence: float


class CodeFixer:
    """
    Uses Claude AI to generate code fixes for failures.

    Workflow:
    1. Analyze failure information
    2. Read affected files
    3. Generate fix using Claude
    4. Validate fix
    5. Return fixed code
    """

    def __init__(self, config: PatchBotConfig):
        """Initialize Code Fixer."""
        self.config = config
        self.client = AsyncAnthropic(api_key=config.anthropic_api_key)

    async def generate_fix(
        self,
        failure: FailureInfo,
        file_contents: Dict[str, str],
    ) -> FixResult:
        """
        Generate fix for failure.

        Args:
            failure: Analyzed failure information
            file_contents: Dict of file_path -> content

        Returns:
            FixResult with proposed fixes
        """
        logger.info(f"Generating fix for {failure.failure_type} failure")

        # Build context for Claude
        prompt = self._build_prompt(failure, file_contents)

        # Call Claude
        response = await self.client.messages.create(
            model=self.config.claude_model,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )

        # Parse response
        fix_result = self._parse_response(response.content[0].text, file_contents)

        logger.info(
            f"Generated {len(fix_result.fixes)} fixes (confidence: {fix_result.confidence:.2f})"
        )

        return fix_result

    def _build_prompt(
        self, failure: FailureInfo, file_contents: Dict[str, str]
    ) -> str:
        """Build prompt for Claude."""
        prompt = f"""You are an expert software engineer helping to fix a CI/CD failure.

**Failure Type**: {failure.failure_type}
**Error Message**: {failure.error_message}

"""

        if failure.stack_trace:
            prompt += f"""**Stack Trace**:
```
{failure.stack_trace[:1000]}
```

"""

        if failure.error_lines:
            prompt += "**Error Locations**:\n"
            for file_path, lines in failure.error_lines.items():
                prompt += f"- {file_path}: lines {', '.join(map(str, lines))}\n"
            prompt += "\n"

        prompt += "**Affected Files**:\n\n"

        for file_path in failure.failed_files[:5]:  # Limit to 5 files
            content = file_contents.get(file_path, "")
            if content:
                # Show relevant portion around error lines
                lines_to_show = self._get_relevant_lines(
                    content, failure.error_lines.get(file_path, [])
                )

                prompt += f"**File: {file_path}**\n```\n{lines_to_show}\n```\n\n"

        prompt += """**Task**:
Analyze the error and provide a fix. For each file that needs changes:

1. Explain what's wrong
2. Provide the complete fixed version of the file
3. Explain why this fix should work

Format your response as:

### Fix for [file_path]

**Problem**: [explanation]

**Solution**: [explanation]

**Fixed Code**:
```
[complete fixed file content]
```

**Confidence**: [0.0-1.0]

Provide fixes only for files that actually need changes. Be conservative - only fix what's necessary."""

        return prompt

    def _get_relevant_lines(
        self, content: str, error_lines: List[int], context: int = 10
    ) -> str:
        """Get relevant lines from file content."""
        lines = content.split("\n")

        if not error_lines:
            # Show first 50 lines if no specific error lines
            return "\n".join(lines[:50])

        # Get lines around errors with context
        relevant_lines = set()
        for error_line in error_lines:
            start = max(0, error_line - context - 1)  # -1 for 0-indexing
            end = min(len(lines), error_line + context)
            for i in range(start, end):
                relevant_lines.add(i)

        # Sort and format
        sorted_lines = sorted(relevant_lines)
        result = []

        for i, line_num in enumerate(sorted_lines):
            # Add separator for gaps
            if i > 0 and line_num - sorted_lines[i - 1] > 1:
                result.append("    ...")

            result.append(f"{line_num + 1:4d} | {lines[line_num]}")

        return "\n".join(result)

    def _parse_response(
        self, response: str, original_contents: Dict[str, str]
    ) -> FixResult:
        """Parse Claude's response into structured fixes."""
        fixes = []
        confidence_scores = []

        # Extract fixes using regex
        import re

        # Pattern to find fix blocks
        fix_pattern = r"### Fix for (.+?)\n.*?\*\*Fixed Code\*\*:\s*```[^\n]*\n(.*?)```.*?\*\*Confidence\*\*:\s*([\d.]+)"

        for match in re.finditer(fix_pattern, response, re.DOTALL):
            file_path = match.group(1).strip()
            fixed_content = match.group(2).strip()
            confidence = float(match.group(3))

            # Extract explanation
            problem_match = re.search(
                r"\*\*Problem\*\*:\s*(.+?)(?:\*\*|$)", response[match.start() : match.end()], re.DOTALL
            )
            solution_match = re.search(
                r"\*\*Solution\*\*:\s*(.+?)(?:\*\*|$)", response[match.start() : match.end()], re.DOTALL
            )

            problem = problem_match.group(1).strip() if problem_match else ""
            solution = solution_match.group(1).strip() if solution_match else ""
            explanation = f"{problem}\n\n{solution}"

            # Get original content
            original_content = original_contents.get(file_path, "")

            fixes.append(
                CodeFix(
                    file_path=file_path,
                    original_content=original_content,
                    fixed_content=fixed_content,
                    explanation=explanation,
                    confidence=confidence,
                )
            )

            confidence_scores.append(confidence)

        # Extract summary
        summary_match = re.search(r"### Summary\s*(.+?)(?:###|$)", response, re.DOTALL)
        summary = summary_match.group(1).strip() if summary_match else "Fix generated"

        # Calculate overall confidence
        overall_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.5

        return FixResult(
            fixes=fixes,
            summary=summary,
            confidence=overall_confidence,
        )
