import re
from typing import Any
import parse
from behave import given, when, then, register_type
from playwright.sync_api import expect

from pages.naming import etype_regex
from utils.logger import logger


@parse.with_pattern(etype_regex())
def parse_etype(text: str) -> str:
    return text.strip().lower()


register_type(Etype=parse_etype)


@given('I am on the "{page_name}" page')
def step_on_page(context: Any, page_name: str) -> None:
    logger.info(f"Setting current page to: '{page_name}'")
    context.current = context.page_factory.get(page_name)


@given('I navigate to the "{page_name}" page')
def step_navigate_to_page(context: Any, page_name: str) -> None:
    logger.info(f"Navigating to page: '{page_name}'")
    context.current = context.page_factory.get(page_name)
    context.current.navigate()


# ---------- basic actions ----------
@when('I click the "{label}" {etype:Etype}')
def step_click(context: Any, label: str, etype: str) -> None:
    logger.info(f"Clicking: {label} ({etype})")
    context.current.element(label, etype).click()


@when('I click the "{label}" {etype:Etype} for "{value}"')
def step_click_dynamic(context: Any, label: str, etype: str, value: str) -> None:
    logger.info(f"Clicking dynamic: {label} ({etype}) with value='{value}'")
    context.current.element(label, etype, value=value).click()


@when('I fill the "{label}" {etype:Etype} with "{value}"')
def step_fill(context: Any, label: str, etype: str, value: str) -> None:
    logger.info(f"Filling: {label} ({etype}) with '{value}'")
    context.current.element(label, etype).fill(value)


@when('I check the "{label}" {etype:Etype}')
def step_check(context: Any, label: str, etype: str) -> None:
    logger.info(f"Checking: {label} ({etype})")
    context.current.element(label, etype).check()


@when('I uncheck the "{label}" {etype:Etype}')
def step_uncheck(context: Any, label: str, etype: str) -> None:
    logger.info(f"Unchecking: {label} ({etype})")
    context.current.element(label, etype).uncheck()


@when('I select "{option}" from the "{label}" {etype:Etype}')
def step_select(context: Any, option: str, label: str, etype: str) -> None:
    logger.info(f"Selecting option '{option}' from: {label} ({etype})")
    context.current.element(label, etype).select_option(label=option)


@when('I read text of the "{label}" {etype:Etype}')
def step_read(context: Any, label: str, etype: str) -> None:
    logger.info(f"Reading text from: {label} ({etype})")
    context.last_text = context.current.element(label, etype).inner_text()


# ---------- single-step click + post-action assertions ----------
@when('After I click the "{label}" {etype:Etype} it is disabled')
def step_after_click_disabled(context: Any, label: str, etype: str) -> None:
    logger.info(f"Clicking {label} ({etype}) and asserting it is disabled")
    el = context.current.element(label, etype)
    el.click()
    expect(el).to_be_disabled()


@when('After I click the "{label}" {etype:Etype} it is enabled')
def step_after_click_enabled(context: Any, label: str, etype: str) -> None:
    logger.info(f"Clicking {label} ({etype}) and asserting it is enabled")
    el = context.current.element(label, etype)
    el.click()
    expect(el).to_be_enabled()


@when('After I click the "{label}" {etype:Etype} it is hidden')
def step_after_click_hidden(context: Any, label: str, etype: str) -> None:
    logger.info(f"Clicking {label} ({etype}) and asserting it is hidden")
    el = context.current.element(label, etype)
    el.click()
    expect(el).to_be_hidden()


@when('After I click the "{label}" {etype:Etype} it redirects to url containing "{url_part}"')
def step_after_click_redirect(context: Any, label: str, etype: str, url_part: str) -> None:
    logger.info(f"Clicking {label} ({etype}) and expecting redirect to url containing '{url_part}'")
    context.current.element(label, etype).click()
    expect(context.page).to_have_url(re.compile(re.escape(url_part)))


@when('After I click the "{label}" {etype:Etype} the "{post_label}" {post_etype:Etype} is visible')
def step_after_click_target_visible(context: Any, label: str, etype: str, post_label: str, post_etype: str) -> None:
    logger.info(f"Clicking {label} ({etype}) and expecting {post_label} ({post_etype}) visible")
    context.current.element(label, etype).click()
    expect(context.current.element(post_label, post_etype)).to_be_visible()


@when('After I click the "{label}" {etype:Etype} the "{post_label}" {post_etype:Etype} for "{value}" is visible')
def step_after_click_dynamic_target_visible(context: Any, label: str, etype: str, post_label: str, post_etype: str, value: str) -> None:
    logger.info(f"Clicking {label} ({etype}) and expecting dynamic {post_label} for '{value}' visible")
    context.current.element(label, etype).click()
    expect(context.current.element(post_label, post_etype, value=value)).to_be_visible()


# ---------- standard assertions ----------
@then('the "{label}" {etype:Etype} should be visible')
def step_visible(context: Any, label: str, etype: str) -> None:
    logger.info(f"Asserting visible: {label} ({etype})")
    expect(context.current.element(label, etype)).to_be_visible()


@then('the "{label}" {etype:Etype} for "{value}" should be visible')
def step_visible_dynamic(context: Any, label: str, etype: str, value: str) -> None:
    logger.info(f"Asserting dynamic visible: {label} ({etype}) with value='{value}'")
    expect(context.current.element(label, etype, value=value)).to_be_visible()


@then('the "{label}" {etype:Etype} should have text "{text}"')
def step_has_text(context: Any, label: str, etype: str, text: str) -> None:
    logger.info(f"Asserting text: {label} ({etype}) has text '{text}'")
    expect(context.current.element(label, etype)).to_have_text(text)


@then('the "{label}" {etype:Etype} should have value "{value}"')
def step_has_value(context: Any, label: str, etype: str, value: str) -> None:
    logger.info(f"Asserting value: {label} ({etype}) has value '{value}'")
    expect(context.current.element(label, etype)).to_have_value(value)


@then('the read text should be "{text}"')
def step_read_text_equals(context: Any, text: str) -> None:
    logger.info(f"Asserting read text matches: '{text}'")
    assert context.last_text == text, f"expected '{text}', got '{context.last_text}'"
