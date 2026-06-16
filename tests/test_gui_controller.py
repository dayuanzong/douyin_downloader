import unittest

from douyin_downloader.gui.controller import MainWindowController


class ImmediateRoot:
    def after(self, _delay, callback, *args):
        callback(*args)


class BrowserAuthButtons:
    def __init__(self):
        self.states = []

    def configure(self, *, state):
        self.states.append(state)


class MinimalView:
    def __init__(self):
        self.import_browser_button = BrowserAuthButtons()
        self.login_browser_button = BrowserAuthButtons()


class FailingBrowserAuthService:
    def import_cookie_text(self, log_callback=None):
        raise RuntimeError("auto import failed")


class MainWindowControllerTest(unittest.TestCase):
    def test_browser_import_error_callback_keeps_exception_object(self):
        controller = MainWindowController.__new__(MainWindowController)
        controller.root = ImmediateRoot()
        controller.view = MinimalView()
        controller.browser_auth_service = FailingBrowserAuthService()
        controller.handled_error = None

        def handle_error(exc):
            controller.handled_error = exc

        controller._handle_browser_import_error = handle_error

        controller._run_browser_import(force_login=False)

        self.assertIsInstance(controller.handled_error, RuntimeError)
        self.assertEqual(str(controller.handled_error), "auto import failed")
        self.assertEqual(controller.view.import_browser_button.states, ["normal"])
        self.assertEqual(controller.view.login_browser_button.states, ["normal"])


if __name__ == "__main__":
    unittest.main()
