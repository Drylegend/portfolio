"""
workflow_manager.py — Pipeline step sequencing and retry control.

Layer responsibilities:
    CLI            → all user I/O
    WorkflowManager → step sequencing, skip control, retry limits
    Orchestrator   → agent calls and inter-agent routing

Rules:
    - WorkflowManager receives structured data from CLI and Orchestrator.
    - It does not call agents or services directly — only the Orchestrator.
    - It calls CLI for all display and confirmation needs.
    - The 14-step sequence is defined here and only here.
"""


class WorkflowManager:
    """
    Sequences the 14-step portfolio update pipeline.

    Step sequence:
        0.  Config validation (done at Container boot)
        1.  Memory Agent: load portfolio state
        2.  Image Agent: scan + classify new images
        3.  CLI: user selects project + provides description
        4.  Content Agent: extract structured metadata
        5.  Reflection Agent: quality review loop
        6.  Validation Agent: pre-patch checks
        7.  Recovery Service: create backup
        8.  Portfolio Plugin: patch files
        9.  Validation Agent: post-patch checks
        10. Testing Agent (Playwright): smoke test
        11. Deployment Service: git add + show diff + confirm
        12. Memory Agent: update all databases
        13. Recovery Service: archive backup
        14. Telemetry: finalise run log
    """

    def __init__(self, orchestrator, cli, container):
        self._orch = orchestrator
        self._cli  = cli
        self._c    = container

    def run(self) -> bool:
        """
        Execute the full pipeline.

        Returns:
            True if the workflow completed successfully, False otherwise.
        """
        run_id = self._c.telemetry.start_run()
        self._cli.show_header(
            provider=self._c.config.provider,
            model=self._c.config.model,
        )

        try:
            # ── Step 1: Load Memory ────────────────────────────────────────
            self._cli.step(1, 14, "Loading portfolio memory")
            state = self._orch.load_memory()
            self._cli.show_memory_status(state)

            # ── Step 2: Scan Images ────────────────────────────────────────
            self._cli.step(2, 14, "Scanning assets/ for new images")
            scan_result = self._orch.scan_images(state["known_keys"])

            if not scan_result.new_groups:
                self._cli.no_new_images(scan_result.duplicates)
                self._c.telemetry.finish_run("cancelled", "No new images found.")
                return False

            # ── Handle multiple project groups sequentially ────────────────
            for group in scan_result.new_groups:
                success = self._process_project(group, state)
                if not success:
                    self._c.telemetry.finish_run("failed")
                    return False
                # Reload state for next group
                state = self._orch.load_memory()

            self._c.telemetry.finish_run("success")
            self._cli.show_summary(self._c.telemetry.summary())
            return True

        except KeyboardInterrupt:
            self._cli.cancelled()
            self._c.telemetry.finish_run("cancelled", "User interrupted.")
            return False
        except Exception as exc:
            self._c.logger.error(f"Unexpected error: {exc}")
            self._c.telemetry.finish_run("failed", str(exc))
            raise

    def _process_project(self, group, state: dict) -> bool:
        """Process a single project group through the full pipeline."""

        # ── Confirm image classification ──────────────────────────────────
        confirmed_group = self._cli.confirm_image_group(group)
        if confirmed_group is None:
            self._cli.skipped(group.detected_key)
            return True  # skip this group, continue with next

        # Process images (resize/compress)
        self._cli.step(3, 14, f"Processing images for '{confirmed_group.detected_key}'")
        image_records = self._orch._c.image_agent.process_images(confirmed_group)
        # Attach image records for DB insertion later
        confirmed_group._image_records = image_records

        # ── Get project description from user ─────────────────────────────
        self._cli.step(4, 14, "Extracting project metadata")
        description = self._cli.get_project_description(confirmed_group)
        if not description:
            return False

        # ── Content Agent ─────────────────────────────────────────────────
        try:
            metadata = self._orch.extract_content(
                description,
                confirmed_group.detected_key,
                confirmed_group,
            )
            # Carry image records forward
            metadata._image_records = image_records
        except Exception as exc:
            self._c.logger.error(f"Content extraction failed: {exc}")
            return False

        # ── Reflection loop ────────────────────────────────────────────────
        self._cli.step(5, 14, "Reviewing metadata quality")
        try:
            metadata = self._orch.run_reflection_loop(
                metadata,
                state["projects"],
                revision_callback=self._cli.get_revision_description,
            )
        except RuntimeError as exc:
            self._c.logger.error(str(exc))
            # Offer manual edit as last resort
            if not self._cli.offer_manual_edit(metadata):
                return False

        # Show extracted metadata, allow user to confirm/edit
        metadata = self._cli.confirm_metadata(metadata)
        if metadata is None:
            return False

        # ── Pre-patch Validation ───────────────────────────────────────────
        self._cli.step(6, 14, "Running pre-patch validation")
        pre_report = self._orch.pre_validate(metadata)
        if not pre_report.passed:
            self._cli.show_validation_errors(pre_report)
            return False

        # ── Backup ────────────────────────────────────────────────────────
        self._cli.step(7, 14, "Creating file backup")
        self._orch.create_backup()

        # ── Patch Files ────────────────────────────────────────────────────
        self._cli.step(8, 14, "Patching portfolio files")
        self._orch.execute_plugin(metadata)

        # ── Post-patch Validation ──────────────────────────────────────────
        self._cli.step(9, 14, "Running post-patch validation")
        post_report = self._orch.post_validate(metadata.key)
        if not post_report.passed:
            self._cli.show_validation_errors(post_report)
            self._cli.rollback_notice()
            return False

        # ── Smoke Test ─────────────────────────────────────────────────────
        self._cli.step(10, 14, "Running smoke test")
        if not self._orch.run_smoke_test():
            self._cli.smoke_test_failed()
            return False

        # ── Deployment ─────────────────────────────────────────────────────
        self._cli.step(11, 14, "Preparing deployment")
        staged_files = self._build_staged_files(metadata)
        deploy_info = self._orch.deploy(metadata, staged_files)

        # Show diff and ask for confirmation
        confirmed = self._cli.confirm_deployment(
            diff=deploy_info["diff"],
            commit_message=deploy_info["commit_message"],
            url=self._c.config.github_pages_url,
        )
        if not confirmed:
            self._cli.deployment_skipped()
            return False

        deploy_result = self._orch.confirm_and_push(deploy_info["commit_message"])
        if not deploy_result.success:
            self._cli.deployment_failed(deploy_result.error)
            return False

        self._cli.deployment_success(deploy_result.url)

        # ── Update Memory (LAST) ───────────────────────────────────────────
        self._cli.step(12, 14, "Updating portfolio database")
        self._orch.update_memory(metadata, deploy_result.commit_hash)

        # ── Archive Backup ─────────────────────────────────────────────────
        self._cli.step(13, 14, "Archiving backup")
        self._orch.archive_backup(deploy_result.commit_hash)

        return True

    def _build_staged_files(self, metadata) -> list[str]:
        """Build the list of files to stage for deployment."""
        files = ["index.html", "projects.json"]
        # Add image files (relative to portfolio root)
        all_images = metadata.images if metadata.images else []
        for img in all_images:
            files.append(img)
        return files
