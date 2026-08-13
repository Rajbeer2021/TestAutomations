import pytest
import allure
from utils.decorators import case_title
from tests.base_test import BaseTest
from pages.orangehrmlogin_page import OrangeHRMLoginPage
from typing import Any

SuiteName = "test_01_LoginHRM"

@allure.suite(SuiteName)
@allure.feature("OrangeHRM - Login & Logout")
@pytest.mark.ui
@pytest.mark.usefixtures("config")
class TestLoginOrangeHRM(BaseTest):
    SUITE_NAME = SuiteName

    @pytest.fixture(autouse=True)
    def setup_page_objects(self, config):

        # Always pick Dev environment
        cfg = config[0] if isinstance(config, tuple) else config
        self.dev_env: Any = cfg.dev

        # Initialize POM after self.page is ready
        self.hrm_login = OrangeHRMLoginPage(
            page=self.page,
            reporter=self.reporter,
            config=cfg
        )
        self.action = self.hrm_login.action
        yield

    @case_title("Test_01: Verify HRM URL launches and login page loads")
    def test_navigate_to_login_page(self):
        self.action.step_navigate_to_url(
            step_name="Navigate to Login Page",
            url=self.dev_env.base_url,  # always Dev
            wait_for_element=self.hrm_login.USERNAME_INPUT
        )
       # print(f"[INFO] ===== Starting Suite: test_01_LoginHRM | Browser: {browser_name} =====")


    @case_title("Test_02: Enter Username")
    def test_enter_username(self):
        self.action.step_type(
            step_name="Enter Username",
            locator=self.hrm_login.USERNAME_INPUT,
            textvalue=self.dev_env.username
        )
        self.action.assertTextEquals(
            locator=self.hrm_login.USERNAME_INPUT,
            expected_text=self.dev_env.username,
            step_name="Assert - Verify Username Entered"
        )

    @case_title("Test_03: Enter Password")
    def test_enter_password(self):
        self.action.step_type(
            step_name="Enter Password",
            locator=self.hrm_login.PASSWORD_INPUT,
            textvalue=self.dev_env.password
        )
        self.action.assertElementVisible(
            locator=self.hrm_login.PASSWORD_INPUT,
            step_name="Assert - Password Input Visible"
        )


    #@pytest.mark.skip(reason="for testing")
    @case_title("Test_04: Click Login and Verify Home Page")
    def test_click_login_button(self):
        self.action.step_click_by_role(
            step_name="Click on Login Button",
            locator=self.hrm_login.LOGIN_BTN,
            wait_for_element=self.hrm_login.PROFILE_PIC

        )
        self.action.assertElementVisible(
            locator=self.hrm_login.PROFILE_PIC,
            step_name="Assert - Home Page Loaded"
        )

    #@pytest.mark.skip(reason="Logout test")
    @case_title("Test_05: Logout from HRM")
    def test_logout_from_HRM(self):
        self.action.step_click(
            step_name="Click Profile Picture",
            locator=self.hrm_login.PROFILE_PIC,
            wait_for_element=self.hrm_login.LOGOUT_MENUITEM
        )
        self.action.assertElementVisible(
            locator=self.hrm_login.LOGOUT_MENUITEM,
            step_name="Assert - Logout Menu Visible"
        )
        self.action.step_click(
            step_name="Click Logout",
            locator=self.hrm_login.LOGOUT_MENUITEM,
            wait_for_element=self.hrm_login.USERNAME_INPUT
        )
        self.action.assertElementVisible(
            locator=self.hrm_login.USERNAME_INPUT,
            step_name="Assert - Username Input Visible After Logout"
        )
