from typing import Any, Dict, Union
from pages.base_page import BasePage
from pages.element import Element, Label, Placeholder, Role
from pages.page_factory import register_page


@register_page("Home", "Home Page")
class HomePage(BasePage):
    url_path: str = "/"

    elements: Dict[str, Union[str, Dict[str, Any], Element]] = {
        "fld_username": Label("Username"),
        "fld_password": Placeholder("Password"),
        "btn_submit": Role("button", name="Submit"),
        "drp_country": Label("Country"),
        "lnk_forgot_password": Role("link", name="Forgot password", exact=True),
    }
