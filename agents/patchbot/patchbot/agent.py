"""PatchBot Agent - Main agent implementation."""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from agent_sdk import AgentCapabilities, AgentClient, AgentConfig, AgentTask, TaskResult

from .analyzer import FailureAnalyzer
from .config import PatchBotConfig, get_config
from .fixer import CodeFixer
from .git_manager import GitManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


class PatchBot:
    """
    PatchBot - Autonomous CI/CD Failure Resolution Agent.

    Automatically:
    1. Receives CI/CD failure tasks
    2. Analyzes logs and errors
    3. Generates fixes using AI
    4. Creates PRs with fixes
    5. Tracks fix outcomes
    """

    def __init__(self, config: PatchBotConfig):
        """Initialize PatchBot."""
        self.config = config
        self.analyzer = FailureAnalyzer()
        self.fixer = CodeFixer(config)
        self.git_manager = GitManager(config)

        # Define capabilities
        self.capabilities = AgentCapabilities(
            supported_tasks=["ci_failure_fix"],
            max_concurrent_tasks=3,
            supported_failure_types=[
                "test",
                "build",
                "lint",
                "type_check",
                "compile",
            ],
            timeout_seconds=1800,  # 30 minutes
        )

        # Create agent client
        self.client = AgentClient(
            agent_name="patchbot",
            version="1.0.0",
            capabilities=self.capabilities,
            controller_url=config.controller_url,
            config=AgentConfig(
                description="Autonomous CI/CD failure resolution agent",
                metadata={
                    "auto_merge_threshold": config.auto_merge_confidence_threshold,
                    "create_prs": config.open_pr,
                },
                poll_interval=10,
                heartbeat_interval=30,
            ),
        )

    async def handle_failure_fix(self, task: AgentTask) -> TaskResult:
        """
        Handle CI/CD failure fix task.

        Args:
            task: Task with failure context

        Returns:
            TaskResult with fix outcome
        """
        start_time = datetime.utcnow()
        context = task.context

        logger.info(f"🔧 Processing failure fix task: {task.id}")
        logger.info(f"Repository: {context.get('repository')}")
        logger.info(f"Failure type: {context.get('failure_type')}")

        try:
            # Step 1: Analyze failure
            logger.info("Step 1/6: Analyzing failure...")
            await self.client.update_task_progress(task.id, 0.1)

            failure_info = self.analyzer.analyze(context)

            logger.info(f"Failure signature: {failure_info.failure_signature}")
            logger.info(f"Failed files: {', '.join(failure_info.failed_files)}")

            # Step 2: Clone repository
            logger.info("Step 2/6: Cloning repository...")
            await self.client.update_task_progress(task.id, 0.2)

            repo_url = context.get("repository_url")
            base_branch = context.get("branch", "main")

            if not repo_url:
                raise ValueError("repository_url not provided in context")

            repo_path = self.git_manager.clone_repository(repo_url, base_branch)

            # Step 3: Read affected files
            logger.info("Step 3/6: Reading affected files...")
            await self.client.update_task_progress(task.id, 0.3)

            file_contents = self.git_manager.read_files(
                repo_path, failure_info.failed_files
            )

            if not file_contents:
                raise ValueError("No file contents could be read")

            # Step 4: Generate fix
            logger.info("Step 4/6: Generating fix with AI...")
            await self.client.update_task_progress(task.id, 0.4)

            fix_result = await self.fixer.generate_fix(failure_info, file_contents)

            logger.info(f"Generated {len(fix_result.fixes)} fixes")
            logger.info(f"Fix confidence: {fix_result.confidence:.2f}")

            # Step 5: Apply fixes and create branch
            logger.info("Step 5/6: Applying fixes...")
            await self.client.update_task_progress(task.id, 0.6)

            if self.config.create_branch:
                branch_name = self.git_manager.create_fix_branch(
                    repo_path, failure_info.failure_signature
                )
            else:
                branch_name = base_branch

            modified_count = self.git_manager.apply_fixes(repo_path, fix_result)

            if modified_count == 0:
                raise ValueError("No files were modified")

            # Commit changes
            commit_sha = self.git_manager.commit_changes(
                repo_path, fix_result, failure_info.failure_type
            )

            # Push branch
            if self.config.create_branch:
                self.git_manager.push_branch(repo_path, branch_name)

            # Step 6: Create pull request
            logger.info("Step 6/6: Creating pull request...")
            await self.client.update_task_progress(task.id, 0.8)

            pr = None
            if self.config.open_pr:
                repository = context.get("repository")
                build_url = context.get("build_url")

                pr = self.git_manager.create_pull_request(
                    repository=repository,
                    branch_name=branch_name,
                    base_branch=base_branch,
                    fix_result=fix_result,
                    failure_type=failure_info.failure_type,
                    build_url=build_url,
                )

            # Cleanup
            self.git_manager.cleanup_workspace(repo_path)

            # Calculate duration
            duration_seconds = (datetime.utcnow() - start_time).total_seconds()

            # Build result
            result_data = {
                "failure_signature": failure_info.failure_signature,
                "failure_type": failure_info.failure_type,
                "files_modified": modified_count,
                "fix_confidence": fix_result.confidence,
                "commit_sha": commit_sha,
                "branch_name": branch_name,
                "pr_url": pr.html_url if pr else None,
                "pr_number": pr.number if pr else None,
                "duration_seconds": int(duration_seconds),
            }

            artifacts = [
                {
                    "type": "pull_request" if pr else "commit",
                    "url": pr.html_url if pr else None,
                    "reference": str(pr.number) if pr else commit_sha[:8],
                }
            ]

            metrics = {
                "fix_confidence": fix_result.confidence,
                "files_analyzed": len(file_contents),
                "files_modified": modified_count,
                "fixes_generated": len(fix_result.fixes),
                "duration_seconds": int(duration_seconds),
            }

            logger.info(f"✅ Fix completed successfully!")
            logger.info(f"PR: {pr.html_url if pr else 'N/A'}")
            logger.info(f"Confidence: {fix_result.confidence:.1%}")

            return TaskResult(
                success=True,
                data=result_data,
                artifacts=artifacts,
                metrics=metrics,
            )

        except Exception as e:
            logger.error(f"❌ Fix failed: {e}", exc_info=True)

            # Try to cleanup
            try:
                if "repo_path" in locals():
                    self.git_manager.cleanup_workspace(repo_path)
            except:
                pass

            return TaskResult(
                success=False,
                error_message=str(e),
                metrics={
                    "duration_seconds": int(
                        (datetime.utcnow() - start_time).total_seconds()
                    ),
                },
            )

    async def run(self):
        """Start PatchBot agent."""
        logger.info("🤖 Starting PatchBot v1.0.0")
        logger.info(f"Controller: {self.config.controller_url}")
        logger.info(f"Capabilities: {self.capabilities.supported_tasks}")

        # Validate configuration
        if not self.config.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY not configured")

        if not self.config.github_token:
            logger.warning("GITHUB_TOKEN not configured - PR creation will be disabled")

        # Register task handler
        self.client.register_task_handler("ci_failure_fix", self.handle_failure_fix)

        # Run agent
        async with self.client:
            await self.client.run()


async def main():
    """Main entry point."""
    config = get_config()
    bot = PatchBot(config)

    try:
        await bot.run()
    except KeyboardInterrupt:
        logger.info("Received interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
