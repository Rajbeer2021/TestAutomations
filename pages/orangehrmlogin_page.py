import time
from utils.actionUtils import ActionUtils

class OrangeHRMLoginPage:

    USERNAME_INPUT = 'xpath=//input[@name="username"]'
    PASSWORD_INPUT = 'input[name="password"]'
    LOGIN_BTN = 'button[type="submit"]'
    PROFILE_PIC = 'role=banner >> role=img[name="profile picture"]'
    #LOGOUT_MENUITEM = 'role=menuitem[name="Logout__SS"]'
    LOGOUT_MENUITEM = "//a[text()='Logout']"

    

    # USERNAME_INPUT = 'input[name="username"]'
    # PASSWORD_INPUT = 'input[name="password"]'
    # LOGIN_BTN = 'button[type="submit"]'
    # PROFILE_PIC = 'img[alt="profile picture"]'
    # LOGOUT_MENUITEM = 'a:has-text("Logout")'

    # USERNAME_INPUT = 'name=username'
    # PASSWORD_INPUT = 'name=password'
    # LOGIN_BTN  = 'button[type="submit"]'
    # PROFILE_PIC = 'img[alt="profile picture"]'
    # #LOGOUT_MENUITEM = 'name=Logout'
    # LOGOUT_MENUITEM = 'text=Logout' #this isusing attributes

    # USERNAME_INPUT = 'input[name="username"]'
    # PASSWORD_INPUT = 'input[name="password"]'
    # LOGIN_BTN = 'button[type="submit"]'
    # PROFILE_PIC = 'img[alt="profile picture"]'
    # LOGOUT_MENUITEM = 'role=menuitem[name="Logout"]' #this is using css

    def __init__(self, page, reporter=None, config=None):

        self.page = page
        self.reporter = reporter
        self.config = config
        self.action = ActionUtils(page, reporter)

        # Read values from YAML config
        if self.config:
            self.LOGIN_URL = getattr(self.config.env, "base_url", "")
            self.username = getattr(self.config.env, "username", "")
            self.password = getattr(self.config.env, "password", "")
        else:
            # Fallback defaults
            self.LOGIN_URL = "https://opensource-demo.orangehrmlive.com/web/index.php/auth/login"
            self.username = "Admin"
            self.password = "admin123"

    def navigate_to_login_page(self):
        self.action.step_navigate_to_url(
            step_name="Navigate to login page",
            url=self.LOGIN_URL,
            wait_for_element=self.USERNAME_INPUT
        )
        self.action.assertElementVisible(
            self.USERNAME_INPUT,
            step_name="Assert1 - Verify login page is visible"
        )

    def login_user(self, username=None, password=None):
        """
        Login user with credentials from YAML or overrides.
        """
        self.page.wait_for_load_state("domcontentloaded")
        username = username or self.username
        password = password or self.password

        self.action.step_type(
            step_name="Enter Username",
            locator=self.USERNAME_INPUT,
            textvalue=username
        )
        self.action.assertElementVisible(
            self.USERNAME_INPUT,
            step_name="Assert2 - Verify Username field visible"
        )

        self.action.step_type(
            step_name="Enter Password",
            locator=self.PASSWORD_INPUT,
            textvalue=password
        )
        self.action.assertElementVisible(
            self.PASSWORD_INPUT,
            step_name="Assert3 - Verify Password field visible"
        )

        self.action.step_click(
            step_name="Click on Login button",
            locator=self.LOGIN_BTN,
            wait_for_element=self.PROFILE_PIC
        )
        time.sleep(2)
        self.action.assertElementVisible(
            self.PROFILE_PIC,
            step_name="Assert4 - Verify Profile Picture visible after login",
        )

    def logout_user(self):
        self.action.step_click(
            step_name="Click Profile Picture",
            locator=self.PROFILE_PIC,
            wait_for_element=self.LOGOUT_MENUITEM
        )
        self.action.assertElementVisible(
            self.LOGOUT_MENUITEM,
            step_name="Assert5 - Verify Logout Menu Visible",
        )
        self.action.step_click(
            step_name="Click Logout",
            locator=self.LOGOUT_MENUITEM,
            wait_for_element=self.USERNAME_INPUT
        )

        self.action.assertElementVisible(
            self.USERNAME_INPUT,
            step_name="Assert6 - Verify Logout Menu Visible",
        )
        # Force fail after this step
        #assert False, "Forcing test failure intentionally"
