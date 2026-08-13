from utils.actionUtils import ActionUtils


class EditWeekDaysPage:

    # ---------------------- LOCATORS ----------------------
    #SIGNIN_LINK = 'role=link[name="Sign In"]'
    #SIGNIN_LINK = "role=link[name='Sign In']"
    #SIGNIN_LINK_TEXT= "text=Sign In"

    #SIGNIN_LINK = 'role=link[name="Sign In"]'
    #SIGNIN_LINK = '[class="btn sign-in"]'
    #SIGNIN_LINK = "//a[text()='Sign In']"
    SIGNIN_LINK = "//a[normalize-space()='Sign In']"
    USERNAME_INPUT = 'role=textbox[name="Email or username"]'
    CONTINUE_BTN = 'role=button[name="Continue"]'
    PASSWORD_INPUT = 'role=textbox[name="Password"]'
    SIGNIN_BTN = 'role=button[name="Sign In"]'
    CLOSE_BTN_POP = '//*[@title="close"]'

    MY_ACCOUNT_MENU = 'label=My Account'
    MANAGE_CANCEL_LINK_TEXT = "text=Manage / Cancel Subscription(s)"

    MANAGE_DELIVERY_PRIMARY_BTN = 'role=button[name="Manage Delivery Primary"]'
    MANAGE_PRIMARY = "[aria-label='Manage Delivery Primary']"
    MANAGE_WEEKEND = "[aria-label='Manage Delivery Weekend']"

    DELIVERY_EDIT_LINK = "text=Edit"
    DELIVERY_CANCEL_LINK = "text=Cancel"
    DELIVERY_CLOSE_BTN = "text=Close"
    DELIVERY_CLOSE = "text=Close"
    SIGNOUT = "text=Sign Out"

    #------------------------#


    DATE_PICKER = '#date-picker75'

    ADD_NEW_ADDRESS_BTN = 'role=listitem >> text=Add New Address >> role=img'

    STREET_INPUT = 'role=textbox[name="Street Address/P.O. Box/APO"]'
    CITY_INPUT = 'role=textbox[name="City"]'
    STATE_DROPDOWN = 'role=link[name="Select"]'
    ZIP_INPUT = 'role=textbox[name="Zip Code"]'
    SAVE_ADDRESS_BTN = 'role=button[name="Save Address"]'

    SCHEDULE_BTN = 'role=button[name="Schedule"][exact=true]'
    DELETE_LINK = 'role=link[name="Delete"]'
    DELETE_CONFIRM_BTN = 'role=button[name="Yes, Delete This Address"]'
    UPDATE_BTN = 'role=button[name="Update"]'
    SIGN_OUT_LINK = 'role=link[name="Sign Out"]'

    # ------------------------------------------------------

    def __init__(self, page, reporter=None, config=None):
        self.page = page
        self.reporter = reporter
        self.action = ActionUtils(page, reporter)

        if config:
            cfg = config  # ConfigManager

            environment = cfg.environments.stage  # <--- always stage

            # Assign environment values
            self.base_url = environment.base_url
            self.username = environment.username
            self.password = environment.password

        else:
            # Fallback defaults (optional)
            self.base_url = "https://customercenter-newlz.s.dev.wsj.com/public"
            self.username = "nue12302023062216@yopmail.com"
            self.password = "password1"

    # ------------------------------------------------------
    # PAGE ACTIONS
    # ------------------------------------------------------

    def navigate_to_site(self):
        self.action.step_navigate_to_url(
            step_name="Navigate to WSJ Customer Center",
            url=self.base_url,
            wait_for_element=self.SIGNIN_LINK
        )
        self.action.step_click("Click Sign In", self.SIGNIN_LINK, wait_for_element=self.USERNAME_INPUT)

    def login(self, username=None, password=None):
        username = username or self.username
        password = password or self.password

        self.action.step_type("Enter Username", self.USERNAME_INPUT, username)
        self.action.step_click("Click Continue", self.CONTINUE_BTN)

        self.action.step_type("Enter Password", self.PASSWORD_INPUT, password)
        self.action.step_click("Click Sign In", self.SIGNIN_BTN)
        #self.action.step_click("Close Popup", self.CLOSE_BTN_POP, wait_for_element=self.CLOSE_BTN_POP)


    # ---------------- ADDRESS & DELIVERY FLOW ----------------

    def open_manage_delivery_primary(self):

        self.action.step_click(
            step_name="CLick on Manage and Cancel Subscription link",
            locator=self.MANAGE_CANCEL_LINK_TEXT, wait_for_element=self.CLOSE_BTN_POP
        )
        self.action.step_click("Close Popup", self.CLOSE_BTN_POP)
        self.action.step_click("Open Manage Delivery Primary", self.MANAGE_PRIMARY)
        self.action.step_click("click on edit delivery link", self.DELIVERY_EDIT_LINK)
        self.action.step_click("close delivery button", self.DELIVERY_CLOSE_BTN)
        self.action.step_click("close delivery popup", self.DELIVERY_CLOSE)
        self.action.step_click("Click onn Signout", self.SIGNOUT)
        self.action.step_pause(3.5, "Wait for action to complete", screenshot=True)

    def select_dates(self):
        self.action.step_click("Open Date Picker", self.DATE_PICKER)

        # Example: Select first selectable date (modify as needed)
        self.action.step_click("Select Start Date", 'role=button[name^="Choose"]')
        self.action.step_click("Select End Date", 'role=button[name^="Choose"]')

    def add_new_address(self, street, city, state, zip_code):
        self.action.step_click("Click Add New Address", self.ADD_NEW_ADDRESS_BTN)

        self.action.step_type("Enter Street Address", self.STREET_INPUT, street)
        self.action.step_type("Enter City", self.CITY_INPUT, city)

        # Select State
        self.action.step_click("Open State Dropdown", self.STATE_DROPDOWN)
        self.action.step_click(f"Select State - {state}", f"text={state}")

        self.action.step_type("Enter Zip Code", self.ZIP_INPUT, zip_code)
        self.action.step_click("Save Address", self.SAVE_ADDRESS_BTN)

    def schedule_delivery(self):
        self.action.step_click("Click Schedule", self.SCHEDULE_BTN)

    def delete_address(self):
        self.action.step_click("Click Delete Link", self.DELETE_LINK)
        self.action.step_click("Confirm Delete", self.DELETE_CONFIRM_BTN)
        self.action.step_click("Click Update", self.UPDATE_BTN)

    def sign_out(self):
        self.action.step_click("Sign Out", self.SIGN_OUT_LINK)

