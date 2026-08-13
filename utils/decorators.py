import allure

def case_title(title: str):
    def decorator(func):
        func._test_title = title  # for custom reporter
        func = allure.title(title)(func)  # set Allure title
        return func
    return decorator
