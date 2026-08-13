import pytest
import allure
from utils.decorators import case_title
from tests.base_test import BaseTest
from pages.orangehrmlogin_page import OrangeHRMLoginPage

# -------------------- Suite Metadata --------------------
SuiteName = "test_02_LoginHRM"
TestCaseName01 = "Test_01: Verify user is able to launch url"
TestCaseName02 = "Test_02: Login into HRM"
TestCaseName03 = "Test_03: Logout from HRM"

@allure.suite(SuiteName)
@allure.feature("OrangeHRM - Login & Logout")
@pytest.mark.ui
class TestLoginHRM(BaseTest):
    SUITE_NAME = SuiteName  # ✅ Picked up by BaseTest
    REGISTER_URL = "https://opensource-demo.orangehrmlive.com/web/index.php/auth/login"

    # -------------------- Page Objects Setup --------------------
    @pytest.fixture(autouse=True)
    def setup_page_objects(self):
        self.hrm_login = OrangeHRMLoginPage(page=self.page, reporter=self.reporter)
        self.action = self.hrm_login.action
        #self.asserts = self.action
        yield

    # -------------------- TEST CASES --------------------
    #@pytest.mark.skip(reason="testing")
    @case_title(TestCaseName01)
    def test_navigate_to_orangeHRM(self):
        self.hrm_login.navigate_to_login_page()

    #@pytest.mark.skip(reason="testing")
    @case_title(TestCaseName02)
    def test_Login_into_HRM(self):
        self.hrm_login.login_user(username="Admin", password="admin123")

    #@pytest.mark.skip(reason="testing")
    @case_title(TestCaseName03)
    def test_Logout_from_HRM(self):
         self.hrm_login.logout_user()

