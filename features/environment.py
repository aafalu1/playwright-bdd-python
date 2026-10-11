import base64
import logging
from multiprocessing import context
import os
import re
from typing import Any, Optional
from behave.model import Status
from playwright.sync_api import sync_playwright, expect
from config.settings import settings
from pages.page_factory import PageFactory
from utils.logger import logger, ScenarioLogCapture

expect.set_options(timeout=float(settings.timeout_ms))


def _sanitize_name(name: str) -> str:
    """Produce filesystem and report-safe identifiers from scenario and step names."""
    return re.sub(r"[^\w\-]+", "_", name).strip("_")


def _load_logo_data_uri(logo_path_or_url: Optional[str]) -> Optional[str]:
    """Load local logo file (SVG, PNG, JPG) as self-contained base64 Data URI or return remote URL."""
    if not logo_path_or_url:
        return None
    if logo_path_or_url.startswith(("http://", "https://", "data:")):
        return logo_path_or_url
    if os.path.isfile(logo_path_or_url):
        ext = os.path.splitext(logo_path_or_url)[1].lower()
        mime_type = "image/png"
        if ext == ".svg":
            mime_type = "image/svg+xml"
        elif ext in (".jpg", ".jpeg"):
            mime_type = "image/jpeg"
        elif ext == ".webp":
            mime_type = "image/webp"

        with open(logo_path_or_url, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
        return f"data:{mime_type};base64,{encoded}"
    return None


def _init_embed_support(context: Any) -> None:
    """Discover active formatters, set up dynamic report metadata, company logo, and bind context.embed."""
    context.html_formatter = None
    runner = getattr(context, "_runner", None)
    if runner:
        for formatter in getattr(runner, "formatters", []):
            if (
                type(formatter).__name__ == "PrettyHTMLFormatter"
                or getattr(formatter, "name", "") == "html-pretty"
            ):
                context.html_formatter = formatter

                # 1. Dynamically enrich the report summary header with runtime environment metadata
                if hasattr(formatter, "additional_info"):
                    formatter.additional_info["Environment"] = settings.env.upper()
                    formatter.additional_info["Browser"] = settings.browser.capitalize()
                    formatter.additional_info["Headless"] = str(settings.headless)
                    formatter.additional_info["Base URL"] = settings.base_url
                    formatter.additional_info["Timeout"] = f"{settings.timeout_ms}ms"

                # 2. Company Logo: Load as base64 data URI to keep the HTML report 100% self-contained
                logo_source = getattr(settings, "company_logo", None)
                if not logo_source and hasattr(context, "config"):
                    logo_source = context.config.userdata.get("behave.formatter.html-pretty.icon")

                logo_uri = _load_logo_data_uri(logo_source)
                if logo_uri:
                    formatter.set_icon(logo_uri)
                    formatter.add_html_head_element(
                        """<style>
                        .feature-icon {
                            height: 40px;
                            display: inline-flex;
                            align-items: center;
                            margin-right: 12px;
                        }
                        .feature-icon img {
                            height: 40px;
                            max-width: 280px;
                            object-fit: contain;
                            vertical-align: middle;
                        }
                        .global-summary {
                            align-items: center;
                            display: flex;
                        }
                        </style>"""
                    )
                break

    def embed(
        mime_type: str,
        data: Any,
        caption: Optional[str] = None,
        fail_only: bool = False,
        *,
        download_button: Optional[bool] = None,
        filename: Optional[str] = None,
        compress: str = "auto",
    ) -> None:
        """Universal embedding helper supporting PrettyHTMLFormatter, legacy formatters, or logging fallback.

        :param mime_type: MIME type ('image/png', 'text/plain', 'text/html', 'text/markdown', 'link', 'video/webm').
        :param data: File path (str/Path), base64 string, or raw text content.
        :param caption: Label shown for the collapsible embed container.
        :param fail_only: If True, PrettyHTMLFormatter only renders this embed when the scenario fails.
        :param download_button: Force show/hide download button in the HTML report.
        :param filename: Suggested filename when the user clicks download.
        :param compress: 'auto' (gzip if > 48kB), True, or False.
        """
        # 1. Behave HTML Pretty Formatter (recommended)
        if getattr(context, "html_formatter", None):
            try:
                context.html_formatter.embed(
                    mime_type=mime_type,
                    data=data,
                    caption=caption,
                    fail_only=fail_only,
                    download_button=download_button,
                    filename=filename,
                    compress=compress,
                )
                return
            except Exception as e:
                logger.debug(f"Failed to embed in PrettyHTMLFormatter: {e}")

        # 2. Legacy Behave HTML Formatter fallback
        if runner:
            for formatter in getattr(runner, "formatters", []):
                if hasattr(formatter, "embedding"):
                    try:
                        # Legacy formatters typically expect base64 string for images
                        payload = data
                        if (
                            "image" in mime_type
                            and isinstance(data, str)
                            and os.path.isfile(data)
                        ):
                            with open(data, "rb") as f:
                                payload = base64.b64encode(f.read()).decode("utf-8")
                        formatter.embedding(mime_type, payload, caption=caption or "Attachment")
                        return
                    except Exception as e:
                        logger.debug(f"Failed to embed in legacy formatter: {e}")

        # 3. Console / Logger fallback when running without an HTML formatter
        logger.info(f"[EMBED: {caption or mime_type}] {data if isinstance(data, str) and len(data) < 150 else '<binary or large payload>'}")

    context.embed = embed


def before_all(context: Any) -> None:
    _init_embed_support(context)
    logger.info(f"Initializing Playwright for environment: {settings.env.upper()}")
    context.pw = sync_playwright().start()

    browser_launcher = getattr(context.pw, settings.browser)
    context.browser = browser_launcher.launch(
        headless=settings.headless,
        slow_mo=settings.slow_mo_ms,
    )
    logger.info(f"Browser launched: {settings.browser} (headless={settings.headless})")


def before_scenario(context: Any, scenario: Any) -> None:
    logger.info(f"--- Scenario Start: '{scenario.name}' ---")
    context.failure_captured = False

    # Attach in-memory scenario log capturer to capture all python logging during this scenario
    context.scenario_log_capture = ScenarioLogCapture()
    logging.getLogger().addHandler(context.scenario_log_capture)

    context.browser_context = context.browser.new_context(
        viewport={"width": settings.viewport_width, "height": settings.viewport_height}
    )
    
    context.page = context.browser_context.new_page()

    # Capture browser console and runtime page errors
    context.browser_console_logs = []
    context.page_errors = []

    def _on_console(msg: Any) -> None:
        context.browser_console_logs.append(f"[{msg.type.upper()}] {msg.text}")

    def _on_page_error(exc: Any) -> None:
        context.page_errors.append(f"[PAGE ERROR] {exc}")

    context.page.on("console", _on_console)
    context.page.on("pageerror", _on_page_error)

    context.page_factory = PageFactory(context.page, base_url=settings.base_url)
    context.current = None
    context.last_text = None

    # Handle pseudo-steps if enabled in behave.ini
    if getattr(context, "html_formatter", None) and getattr(context.html_formatter, "pseudo_steps", False):
        try:
            context.html_formatter.before_scenario_finish("passed")
        except Exception as e:
            logger.debug(f"Failed pseudo-step finish in before_scenario: {e}")


def after_step(context: Any, step: Any) -> None:
    status_name = getattr(getattr(step, "status", None), "name", str(step.status)).lower()
    is_failed = status_name in ("failed", "error") or Status.has_failed(step.status)

    safe_scenario = _sanitize_name(context.scenario.name if hasattr(context, "scenario") else "scenario")
    safe_step = _sanitize_name(step.name)

    if is_failed:
        context.failure_captured = True
        logger.error(f"Step FAILED: '{step.name}' in scenario '{safe_scenario}'")

    capture_screenshot = settings.screenshot_on_every_step or (
        settings.screenshot_on_failure and is_failed
    )
    if capture_screenshot and hasattr(context, "page") and context.page:
        try:
            png_bytes = context.page.screenshot(full_page=True)
            caption = (
                f"Failure Screenshot: {step.name}"
                if is_failed
                else f"Step Screenshot: {step.name}"
            )
            context.embed(
                mime_type="image/png",
                data=base64.b64encode(png_bytes).decode("utf-8"),
                caption=caption,
            )
            logger.info(f"Step screenshot embedded: '{step.name}'")
        except Exception as e:
            logger.warning(f"Failed to capture/embed step screenshot: {e}")

    if not is_failed:
        return

    # 2. Embed Execution Logs accumulated up to the failure point
    if settings.embed_logs and hasattr(context, "scenario_log_capture"):
        step_logs = context.scenario_log_capture.get_logs()
        if step_logs.strip():
            context.embed(
                mime_type="text/plain",
                data=step_logs,
                caption=f"Execution Logs: {step.name}",
                filename=f"{safe_scenario}_{safe_step}_logs.txt",
            )

    # 3. Embed Browser Console Logs if any occurred
    if settings.embed_console_logs and getattr(context, "browser_console_logs", None):
        console_data = "\n".join(context.browser_console_logs)
        if console_data.strip():
            context.embed(
                mime_type="text/plain",
                data=console_data,
                caption="Browser Console Output",
                filename=f"{safe_scenario}_console.log",
            )

    # 4. Embed Uncaught Browser Page Errors if any occurred
    if getattr(context, "page_errors", None):
        errors_data = "\n".join(context.page_errors)
        if errors_data.strip():
            context.embed(
                mime_type="text/plain",
                data=errors_data,
                caption="Uncaught Page Errors",
                filename=f"{safe_scenario}_page_errors.log",
            )


def after_scenario(context: Any, scenario: Any) -> None:
    safe_name = _sanitize_name(scenario.name)
    status_name = getattr(getattr(scenario, "status", None), "name", str(scenario.status)).lower()
    is_failed = status_name in ("failed", "error") or scenario.status in (Status.failed, Status.error)

    if is_failed:
        logger.error(f"Scenario FAILED: '{scenario.name}'")

        # Fallback screenshot if failure occurred outside after_step (e.g. in hooks)
        if (
            settings.screenshot_on_failure
            and not getattr(context, "failure_captured", False)
            and hasattr(context, "page")
            and context.page
        ):
            try:
                png_bytes = context.page.screenshot(full_page=True)
                context.embed(
                    mime_type="image/png",
                    data=base64.b64encode(png_bytes).decode("utf-8"),
                    caption="Scenario Failure Screenshot",
                )
            except Exception as e:
                logger.warning(f"Failed to capture fallback scenario screenshot: {e}")

        # Fallback log embed if failure occurred outside after_step
        if (
            settings.embed_logs
            and not getattr(context, "failure_captured", False)
            and hasattr(context, "scenario_log_capture")
        ):
            logs = context.scenario_log_capture.get_logs()
            if logs.strip():
                context.embed(
                    mime_type="text/plain",
                    data=logs,
                    caption=f"Scenario Failure Logs: {scenario.name}",
                    filename=f"{safe_name}_failure.log",
                )

    else:
        logger.info(f"Scenario PASSED: '{scenario.name}'")

        # Embed complete execution logs for passed scenarios if configured
        if settings.embed_logs and not settings.embed_logs_on_failure_only:
            if hasattr(context, "scenario_log_capture"):
                logs = context.scenario_log_capture.get_logs()
                if logs.strip():
                    context.embed(
                        mime_type="text/plain",
                        data=logs,
                        caption="Scenario Execution Logs",
                        filename=f"{safe_name}_execution.log",
                    )

    # Detach scenario in-memory logger to prevent memory leaks across scenarios
    if hasattr(context, "scenario_log_capture"):
        try:
            logging.getLogger().removeHandler(context.scenario_log_capture)
            context.scenario_log_capture.close()
        except Exception as e:
            logger.debug(f"Error closing scenario log capture: {e}")

    # Handle pseudo-steps finish if enabled
    if getattr(context, "html_formatter", None) and getattr(context.html_formatter, "pseudo_steps", False):
        try:
            context.html_formatter.after_scenario_finish(status_name)
        except Exception as e:
            logger.debug(f"Failed pseudo-step finish in after_scenario: {e}")

    # Close browser context
    if hasattr(context, "browser_context") and context.browser_context:
        try:
            context.browser_context.close()
        except Exception as e:
            logger.debug(f"Failed closing browser context: {e}")


def after_all(context: Any) -> None:
    logger.info("Closing browser and stopping Playwright...")
    if hasattr(context, "browser") and context.browser:
        try:
            context.browser.close()
        except Exception as e:
            logger.debug(f"Failed closing browser: {e}")

    if hasattr(context, "pw") and context.pw:
        try:
            context.pw.stop()
        except Exception as e:
            logger.debug(f"Failed stopping playwright: {e}")

    logger.info("Test execution completed.")
