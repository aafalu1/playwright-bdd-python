import base64
import logging
import os
import re
from pathlib import Path
from typing import Any, Optional

from playwright.sync_api import sync_playwright, expect

from config.settings import settings
from pages.page_factory import PageFactory
from utils.logger import logger, ScenarioLogCapture

expect.set_options(timeout=float(settings.timeout_ms))

# Optional settings: fall back to safe defaults if they are not defined in config.settings
TRACE_ON_FAILURE: bool = bool(getattr(settings, "trace_on_failure", False))
TRACE_DIR = Path(getattr(settings, "trace_dir", "reports/traces"))

FAILED_STATUSES = ("failed", "error")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _sanitize_name(name: str) -> str:
    """Produce filesystem and report-safe identifiers from scenario and step names."""
    return re.sub(r"[^\w\-]+", "_", name).strip("_")[:120] or "unnamed"


def _is_failed(obj: Any) -> bool:
    """True if a behave step/scenario ended in failed or error status."""
    status = getattr(obj, "status", None)
    name = getattr(status, "name", str(status)).lower()
    return name in FAILED_STATUSES


def _page_alive(context: Any) -> bool:
    page = getattr(context, "page", None)
    try:
        return bool(page) and not page.is_closed()
    except Exception:
        return False


def _load_logo_data_uri(logo_path_or_url: Optional[str]) -> Optional[str]:
    """Load local logo file (SVG, PNG, JPG, WEBP) as base64 Data URI, or return a remote URL as-is."""
    if not logo_path_or_url:
        return None
    if logo_path_or_url.startswith(("http://", "https://", "data:")):
        return logo_path_or_url
    if os.path.isfile(logo_path_or_url):
        ext = os.path.splitext(logo_path_or_url)[1].lower()
        mime_type = {
            ".svg": "image/svg+xml",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }.get(ext, "image/png")
        with open(logo_path_or_url, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
        return f"data:{mime_type};base64,{encoded}"
    return None


LOGO_CSS = """<style>
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


def _configure_html_formatter(context: Any, formatter: Any) -> None:
    """Enrich the report header and logo. Every step is guarded so a formatter version
    difference can never abort the test run."""
    # 1. Runtime environment metadata in the summary header
    try:
        if hasattr(formatter, "additional_info"):
            formatter.additional_info["Environment"] = settings.env.upper()
            formatter.additional_info["Browser"] = settings.browser.capitalize()
            formatter.additional_info["Headless"] = str(settings.headless)
            formatter.additional_info["Base URL"] = settings.base_url
            formatter.additional_info["Timeout"] = f"{settings.timeout_ms}ms"
    except Exception as e:
        logger.warning(f"Could not set report additional_info: {e}")

    # 2. Company logo as base64 so the HTML report stays 100% self-contained
    try:
        logo_source = getattr(settings, "company_logo", None)
        if not logo_source and hasattr(context, "config"):
            logo_source = context.config.userdata.get("behave.formatter.html-pretty.icon")

        logo_uri = _load_logo_data_uri(logo_source)
        if logo_uri:
            if hasattr(formatter, "set_icon"):
                formatter.set_icon(logo_uri)
            if hasattr(formatter, "add_html_head_element"):
                formatter.add_html_head_element(LOGO_CSS)
    except Exception as e:
        logger.warning(f"Could not apply report logo: {e}")


def _init_embed_support(context: Any) -> None:
    """Discover the active formatter, enrich report metadata, and bind context.embed."""
    context.html_formatter = None
    runner = getattr(context, "_runner", None)

    if runner:
        for formatter in getattr(runner, "formatters", []):
            if (
                type(formatter).__name__ == "PrettyHTMLFormatter"
                or getattr(formatter, "name", "") == "html-pretty"
            ):
                context.html_formatter = formatter
                _configure_html_formatter(context, formatter)
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
        """Universal embedding helper: PrettyHTMLFormatter -> legacy formatter -> logger.

        :param mime_type: 'image/png', 'text/plain', 'text/html', 'text/markdown', 'link', 'video/webm'.
        :param data: File path (str/Path), base64 string, or raw text content.
        :param caption: Label shown for the collapsible embed container.
        :param fail_only: If True, PrettyHTMLFormatter only renders this embed when the scenario fails.
        :param download_button: Force show/hide the download button in the HTML report.
        :param filename: Suggested filename when the user clicks download.
        :param compress: 'auto' (gzip if > 48kB), True, or False.
        """
        # 1. behave-html-pretty-formatter
        formatter = getattr(context, "html_formatter", None)
        if formatter:
            full_kwargs = dict(
                mime_type=mime_type,
                data=data,
                caption=caption,
                fail_only=fail_only,
                download_button=download_button,
                filename=filename,
                compress=compress,
            )
            try:
                formatter.embed(**full_kwargs)
                return
            except TypeError:
                # Older formatter versions may not accept the newer keyword arguments.
                try:
                    formatter.embed(mime_type=mime_type, data=data, caption=caption)
                    return
                except Exception as e:
                    logger.debug(f"Minimal PrettyHTMLFormatter embed failed: {e}")
            except Exception as e:
                logger.debug(f"Failed to embed in PrettyHTMLFormatter: {e}")

        # 2. Legacy behave HTML formatter fallback
        if runner:
            for legacy in getattr(runner, "formatters", []):
                if hasattr(legacy, "embedding"):
                    try:
                        payload = data
                        if "image" in mime_type and isinstance(data, str) and os.path.isfile(data):
                            with open(data, "rb") as f:
                                payload = base64.b64encode(f.read()).decode("utf-8")
                        legacy.embedding(mime_type, payload, caption=caption or "Attachment")
                        return
                    except Exception as e:
                        logger.debug(f"Failed to embed in legacy formatter: {e}")

        # 3. Console / logger fallback
        preview = data if isinstance(data, str) and len(data) < 150 else "<binary or large payload>"
        logger.info(f"[EMBED: {caption or mime_type}] {preview}")

    context.embed = embed


def _embed_screenshot(context: Any, caption: str, *, full_page: bool) -> bool:
    """Capture and embed a screenshot. Returns True only if it was embedded successfully."""
    if not _page_alive(context):
        logger.debug("Skipping screenshot: page is not available or already closed.")
        return False
    try:
        png_bytes = context.page.screenshot(full_page=full_page)
        context.embed(
            mime_type="image/png",
            data=base64.b64encode(png_bytes).decode("utf-8"),
            caption=caption,
        )
        return True
    except Exception as e:
        logger.warning(f"Failed to capture/embed screenshot '{caption}': {e}")
        return False


def _embed_scenario_logs(context: Any, caption: str, filename: str) -> bool:
    capture = getattr(context, "scenario_log_capture", None)
    if not (settings.embed_logs and capture):
        return False
    logs = capture.get_logs()
    if not logs.strip():
        return False
    context.embed(mime_type="text/plain", data=logs, caption=caption, filename=filename)
    return True


def _embed_browser_diagnostics(context: Any, safe_scenario: str) -> None:
    """Embed browser console output and uncaught page errors collected so far."""
    if settings.embed_console_logs and getattr(context, "browser_console_logs", None):
        console_data = "\n".join(context.browser_console_logs)
        if console_data.strip():
            context.embed(
                mime_type="text/plain",
                data=console_data,
                caption="Browser Console Output",
                filename=f"{safe_scenario}_console.log",
            )

    if getattr(context, "page_errors", None):
        errors_data = "\n".join(context.page_errors)
        if errors_data.strip():
            context.embed(
                mime_type="text/plain",
                data=errors_data,
                caption="Uncaught Page Errors",
                filename=f"{safe_scenario}_page_errors.log",
            )


# --------------------------------------------------------------------------- #
# Behave hooks
# --------------------------------------------------------------------------- #
def before_all(context: Any) -> None:
    _init_embed_support(context)

    # The scenario log capture hangs off the root logger, so make sure INFO records reach it.
    root = logging.getLogger()
    if root.getEffectiveLevel() > logging.INFO:
        root.setLevel(logging.INFO)

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

    # Track what was embedded separately so fallbacks in after_scenario are accurate
    context.step_failure_seen = False
    context.screenshot_embedded = False
    context.logs_embedded = False
    context.trace_active = False

    # In-memory capture of all Python logging during this scenario
    context.scenario_log_capture = ScenarioLogCapture()
    context.scenario_log_capture.setLevel(logging.INFO)
    logging.getLogger().addHandler(context.scenario_log_capture)

    context.browser_context = context.browser.new_context(
        viewport={"width": settings.viewport_width, "height": settings.viewport_height}
    )

    if TRACE_ON_FAILURE:
        try:
            context.browser_context.tracing.start(screenshots=True, snapshots=True, sources=True)
            context.trace_active = True
        except Exception as e:
            logger.warning(f"Could not start Playwright tracing: {e}")

    context.page = context.browser_context.new_page()

    # Browser console and runtime page errors
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


def after_step(context: Any, step: Any) -> None:
    is_failed = _is_failed(step)
    safe_scenario = _sanitize_name(context.scenario.name if hasattr(context, "scenario") else "scenario")
    safe_step = _sanitize_name(step.name)

    if is_failed:
        context.step_failure_seen = True
        logger.error(f"Step FAILED: '{step.name}' in scenario '{safe_scenario}'")

    # 1. Screenshot: full page on failure, lighter viewport-only shot for passing steps
    if is_failed and settings.screenshot_on_failure:
        if _embed_screenshot(context, f"Failure Screenshot: {step.name}", full_page=True):
            context.screenshot_embedded = True
            logger.info(f"Failure screenshot embedded: '{step.name}'")
    elif not is_failed and settings.screenshot_on_every_step:
        if _embed_screenshot(context, f"Step Screenshot: {step.name}", full_page=False):
            logger.info(f"Step screenshot embedded: '{step.name}'")

    if not is_failed:
        # Keep browser diagnostics scoped to the step that actually fails
        context.browser_console_logs.clear()
        context.page_errors.clear()
        return

    # 2. Execution logs accumulated up to the failure point
    if _embed_scenario_logs(context, f"Execution Logs: {step.name}", f"{safe_scenario}_{safe_step}_logs.txt"):
        context.logs_embedded = True

    # 3 + 4. Browser console output and uncaught page errors
    _embed_browser_diagnostics(context, safe_scenario)


def after_scenario(context: Any, scenario: Any) -> None:
    safe_name = _sanitize_name(scenario.name)
    is_failed = _is_failed(scenario)

    if is_failed:
        logger.error(f"Scenario FAILED: '{scenario.name}'")

        # Fallbacks for failures that happened outside after_step (e.g. in hooks)
        if settings.screenshot_on_failure and not context.screenshot_embedded:
            if _embed_screenshot(context, "Scenario Failure Screenshot", full_page=True):
                context.screenshot_embedded = True

        if not context.logs_embedded:
            if _embed_scenario_logs(
                context, f"Scenario Failure Logs: {scenario.name}", f"{safe_name}_failure.log"
            ):
                context.logs_embedded = True

        if not context.step_failure_seen:
            _embed_browser_diagnostics(context, safe_name)
    else:
        logger.info(f"Scenario PASSED: '{scenario.name}'")

        if settings.embed_logs and not settings.embed_logs_on_failure_only:
            _embed_scenario_logs(context, "Scenario Execution Logs", f"{safe_name}_execution.log")

    # Detach the scenario log handler to avoid leaks across scenarios
    capture = getattr(context, "scenario_log_capture", None)
    if capture:
        try:
            logging.getLogger().removeHandler(capture)
            capture.close()
        except Exception as e:
            logger.debug(f"Error closing scenario log capture: {e}")

    # Stop tracing: keep the trace only for failed scenarios
    browser_context = getattr(context, "browser_context", None)
    if browser_context and getattr(context, "trace_active", False):
        try:
            if is_failed:
                TRACE_DIR.mkdir(parents=True, exist_ok=True)
                trace_path = TRACE_DIR / f"{safe_name}.zip"
                browser_context.tracing.stop(path=str(trace_path))
                logger.info(f"Playwright trace saved: {trace_path}")
                context.embed(
                    mime_type="text/plain",
                    data=f"Trace saved to: {trace_path}\nOpen with: playwright show-trace \"{trace_path}\"",
                    caption="Playwright Trace",
                )
            else:
                browser_context.tracing.stop()  # discard
        except Exception as e:
            logger.debug(f"Failed stopping tracing: {e}")

    # Close browser context
    if browser_context:
        try:
            browser_context.close()
        except Exception as e:
            logger.debug(f"Failed closing browser context: {e}")


def after_all(context: Any) -> None:
    logger.info("Closing browser and stopping Playwright...")
    if getattr(context, "browser", None):
        try:
            context.browser.close()
        except Exception as e:
            logger.debug(f"Failed closing browser: {e}")

    if getattr(context, "pw", None):
        try:
            context.pw.stop()
        except Exception as e:
            logger.debug(f"Failed stopping playwright: {e}")

    logger.info("Test execution completed.")