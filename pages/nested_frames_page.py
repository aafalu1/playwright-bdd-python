import os
from pages.base_page import BasePage
from pages.element import Css, FrameSection, Placeholder, Role, TestId
from pages.page_factory import register_page

FIXTURE_HTML_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "fixtures", "dummy_site", "index.html")
)


@register_page("Nested Frames", "Multi Level Frames")
class NestedFramesPage(BasePage):
    """Page Object modeling multi-level nested iframe interactions."""

    url_path = f"file://{FIXTURE_HTML_PATH}"

    elements = {
        # Level 0 (Top Host Page)
        "lbl_title": Css("#main-title"),
        "fld_customer": Placeholder("Your Name"),
        "btn_view_policy": Role("button", name="View Policy"),

        # Level 1 (Parent Iframe)
        "fld_card_number": Placeholder("Enter 16-digit card", frames=["#parent-frame"]),
        "btn_validate_card": Role("button", name="Validate Card", frames=["#parent-frame"]),

        # Level 2 & Level 3 grouped via FrameSection
        **FrameSection(["#parent-frame", "#child-frame"], {
            # Level 2 (Child Frame)
            "fld_bank_reference": Placeholder("Bank Reference ID"),
            "btn_initiate_challenge": Role("button", name="Initiate Challenge"),

            # Level 3 (Deeply nested inside Level 2)
            "fld_otp": TestId("otp-code", frames=["#nested-frame"]),
            "btn_confirm_payment": Role("button", name="Confirm Payment", frames=["#nested-frame"]),
            "lbl_verification_status": Css("#status-msg", frames=["#nested-frame"]),
        }),
    }
