import os
from typing import Any, Dict, Union
from pages.base_page import BasePage
from pages.element import Css, Element, FrameSection, Placeholder, Role, TestId
from pages.page_factory import register_page

FIXTURE_HTML_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "fixtures", "dummy_site", "cart.html")
)


@register_page("Add to Cart", "Cart")
class AddToCartPage(BasePage):
    url_path: str = f"file://{FIXTURE_HTML_PATH}"

    elements: Dict[str, Union[str, Dict[str, Any], Element]] = {
        "btn_add_to_cart": Role("button", name="Add to cart"),
        "lnk_first_product": Role("link", name="Product", nth=0),
        "chk_terms": "#terms",
        "btn_pay": {"selector": "#pay", "frames": ["#checkout"]},

        # Iframe elements demonstrating FrameSection grouping
        **FrameSection(["#checkout"], {
            "fld_card_number": Placeholder("Card number", frames=["iframe[title='Card']"]),
            "fld_otp": TestId("otp", frames=["iframe[name='3ds']"]),
        }),
        "lbl_order_row": Css("tr", has_text="{value}", frames=["#orders"]),
    }
