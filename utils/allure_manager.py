import allure

class AllureManager:
    @staticmethod
    def set_hierarchy(parent="WSJ CustomerCenter Automation", suite=None, sub_suite=None):
        """
        Apply Allure suite hierarchy dynamically for each test class or module.
        """
        allure.dynamic.parent_suite(parent)
        if suite:
            allure.dynamic.suite(suite)
        if sub_suite:
            allure.dynamic.sub_suite(sub_suite)

    @staticmethod
    def set_test_details(test_name, feature=None, story=None, severity="normal"):
        """
        Attach readable name and optional metadata (feature/story/severity).
        """
        allure.dynamic.title(test_name)
        if feature:
            allure.dynamic.feature(feature)
        if story:
            allure.dynamic.story(story)
        allure.dynamic.severity(severity)
