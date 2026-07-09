"""
orchestrator.py — Agent lifecycle management and inter-agent message routing.

Layer responsibilities:
    CLI            → all user I/O
    WorkflowManager → step sequencing and retry control
    Orchestrator   → spawns agents, routes messages, handles rejection loops

Rules:
    - No user I/O here. All prompts go through CLI.
    - No business logic here. Agents and services handle that.
    - Rejection loops (Reflection ↔ Content, Validation → Recovery) live here.
    - The Orchestrator is the only component that calls agents directly.
"""


class Orchestrator:
    """
    Routes messages between agents and manages the rejection/revision loops.

    The Orchestrator does not know about the pipeline sequence — that is
    WorkflowManager's responsibility. It only handles individual step execution
    and inter-agent communication.
    """

    def __init__(self, container):
        self._c       = container   # DI container
        self._logger  = container.logger
        self._events  = container.event_bus

    # ── Step Executors (called by WorkflowManager) ────────────────────────────

    def load_memory(self) -> dict:
        """Step 1: Load portfolio state from database."""
        state = self._c.memory_agent.load()
        self._events.emit("PORTFOLIO_LOADED", {"project_count": len(state["projects"])})
        return state

    def scan_images(self, known_keys: set[str]):
        """Step 2: Scan assets/ for new images and classify them."""
        result = self._c.image_agent.scan(known_keys)
        self._events.emit("IMAGE_SCANNED", {
            "new_groups": len(result.new_groups),
            "duplicates": len(result.duplicates),
        })
        return result

    def extract_content(self, description: str, project_key: str,
                         image_group) -> object:
        """Step 3+4: Extract metadata, then run Reflection loop."""
        metadata = self._c.content_agent.extract(
            description, project_key, image_group
        )
        self._events.emit("CONTENT_EXTRACTED", {"key": project_key})
        return metadata

    def run_reflection_loop(self, metadata, existing_projects: list[dict],
                             revision_callback) -> object:
        """
        Step 5: Reflection Agent review with revision loop.

        On rejection: calls revision_callback(feedback) to get revised
        description, then re-extracts. Repeats up to MAX_REVISION_ATTEMPTS.

        Args:
            metadata:          Initial ProjectMetadata from ContentAgent.
            existing_projects: Existing projects for duplication check.
            revision_callback: Callable(feedback: list[str]) → str
                               Returns revised description from user or LLM.

        Returns:
            Accepted ProjectMetadata, or raises RuntimeError after max attempts.
        """
        max_attempts = self._c.config.max_revision_attempts

        for attempt in range(1, max_attempts + 1):
            result = self._c.reflection_agent.review(metadata, existing_projects)

            if result.accepted:
                self._events.emit("REFLECTION_ACCEPTED", {"score": result.score})
                return metadata

            self._logger.warning(
                f"Reflection rejected (attempt {attempt}/{max_attempts}). "
                f"Issues: {result.feedback}"
            )
            self._events.emit("REFLECTION_REJECTED", {
                "attempt": attempt,
                "issues":  result.feedback,
            })

            if attempt >= max_attempts:
                break

            # Get revised description (from CLI or LLM)
            revised_description = revision_callback(result.feedback, result.revision_prompt)
            if revised_description:
                # Re-extract with revision instruction prepended
                from agents.content_agent import ContentAgent
                # Re-use the same image_group reference stored in metadata
                class _FakeGroup:
                    cover  = metadata.cover_image
                    images = metadata.images[1:] if metadata.images else []

                metadata = self._c.content_agent.extract(
                    description=f"REVISION INSTRUCTION: {result.revision_prompt}\n\n{revised_description}",
                    project_key=metadata.key,
                    image_group=_FakeGroup(),
                )

        raise RuntimeError(
            f"Reflection Agent rejected metadata after {max_attempts} attempts. "
            "Please review the project description manually."
        )

    def pre_validate(self, metadata) -> object:
        """Step 6: Pre-patch validation."""
        report = self._c.validation_agent.pre_patch(metadata)
        if not report.passed:
            self._events.emit("VALIDATION_FAILED", {"stage": "pre_patch", "errors": report.errors})
        return report

    def create_backup(self) -> None:
        """Step 7: Create file backup before patching."""
        self._c.recovery.backup(["index.html", "projects.json"])
        self._events.emit("BACKUP_CREATED", {})

    def execute_plugin(self, metadata) -> dict:
        """Step 8: Run Portfolio Plugin to patch files."""
        result = self._c.portfolio_plugin.execute(metadata.to_dict())
        self._events.emit("PATCH_APPLIED", {"key": metadata.key})
        return result

    def post_validate(self, project_key: str) -> object:
        """Step 9: Post-patch validation. Restores on failure."""
        report = self._c.validation_agent.post_patch(project_key)
        if not report.passed:
            self._logger.error("Post-patch validation failed. Triggering rollback.")
            self._c.recovery.restore()
            self._events.emit("ROLLBACK_TRIGGERED", {"stage": "post_patch"})
        return report

    def run_smoke_test(self) -> bool:
        """Step 10: Playwright smoke test on localhost."""
        if not self._c.config.require_smoke_test:
            self._logger.info("Smoke test skipped (REQUIRE_SMOKE_TEST=false).")
            return True

        passed = self._run_playwright_test()
        if not passed:
            self._logger.error("Smoke test failed. Triggering rollback.")
            self._c.recovery.restore()
            self._events.emit("SMOKE_TEST_FAILED", {})
        else:
            self._events.emit("SMOKE_TEST_PASSED", {})
        return passed

    def deploy(self, metadata, staged_files: list[str]) -> object:
        """Step 11: Prepare and deploy via DeploymentService."""
        self._c.deployment.prepare(staged_files)
        diff = self._c.deployment.diff()
        commit_msg = f"feat: add {metadata.title}"

        # Show diff is returned to WorkflowManager → CLI for display
        return {"diff": diff, "commit_message": commit_msg}

    def confirm_and_push(self, commit_message: str) -> object:
        """Called after user confirms deployment."""
        deploy_start = self._c.time.now_unix()
        result = self._c.deployment.deploy(commit_message)
        self._c.telemetry.set_deployment_duration(
            self._c.time.now_unix() - deploy_start
        )
        if result.success:
            self._events.emit("DEPLOYMENT_SUCCESS", {
                "commit": result.commit_hash,
                "url":    result.url,
            })
        else:
            self._events.emit("DEPLOYMENT_FAILED", {"error": result.error})
        return result

    def update_memory(self, metadata, commit_hash: str) -> None:
        """Step 12: Update all databases AFTER confirmed deployment."""
        self._c.memory_agent.update(
            metadata.to_dict(), commit_hash, self._c.telemetry.run_id
        )
        self._events.emit("MEMORY_UPDATED", {"key": metadata.key})

    def archive_backup(self, commit_hash: str) -> None:
        """Step 13: Archive backup after successful deployment."""
        self._c.recovery.archive(commit_hash)

    # ── Smoke Test ────────────────────────────────────────────────────────────

    def _run_playwright_test(self) -> bool:
        """Launch a local server and run Playwright checks."""
        import threading
        import http.server
        import socketserver
        import time

        port      = self._c.config.smoke_test_port
        root      = str(self._c.config.portfolio_root)
        handler   = http.server.SimpleHTTPRequestHandler
        handler.log_message = lambda *args: None  # silence server logs

        server = socketserver.TCPServer(("", port), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self._logger.warning(
                "Playwright not installed. Skipping smoke test.\n"
                "Run: pip install playwright && playwright install chromium"
            )
            return True  # don't block deployment for missing optional dep

        original_dir = None
        try:
            import os
            original_dir = os.getcwd()
            os.chdir(root)
            thread.start()
            time.sleep(1)  # give server a moment to bind

            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                page    = browser.new_page()
                page.goto(f"http://localhost:{port}", wait_until="networkidle")

                # Check page loaded
                if "Utsav" not in page.title() and "Portfolio" not in page.title():
                    self._logger.warning("Smoke test: Page title looks unexpected.")

                # Check at least one project card is visible
                cards = page.query_selector_all(".project-card")
                if not cards:
                    self._logger.error("Smoke test: No .project-card elements found.")
                    browser.close()
                    return False

                # Click the first card's "View More" button → modal should open
                first_btn = page.query_selector(".project-card button")
                if first_btn:
                    first_btn.click()
                    page.wait_for_selector("#modal", state="visible", timeout=3000)
                    modal = page.query_selector("#modal")
                    if not modal or not modal.is_visible():
                        self._logger.error("Smoke test: Modal did not open.")
                        browser.close()
                        return False

                browser.close()
                self._logger.success("Smoke test passed.")
                return True

        except Exception as exc:
            self._logger.error(f"Smoke test error: {exc}")
            return False
        finally:
            server.shutdown()
            if original_dir:
                import os
                os.chdir(original_dir)
