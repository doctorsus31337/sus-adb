import unittest

from app.gui.instrumentation_panel import InstrumentationPanel


class Widget:
    def __init__(self):
        self.destroyed = False

    def destroy(self):
        self.destroyed = True


class PanelHarness:
    INSTALLED_RENDER_BATCH_SIZE = 20
    _render_installed_batch = InstrumentationPanel._render_installed_batch
    _cancel_installed_render = InstrumentationPanel._cancel_installed_render

    def __init__(self, total=45, old=0):
        self._installed_render_generation = 3
        self._installed_render_after = None
        self._installed_render_old_widgets = [Widget() for _ in range(old)]
        self._installed_render_pending = tuple(range(total))
        self._installed_render_index = 0
        self.created = []
        self.scheduled = []
        self.cancelled = []
        self.installed_count = self

    def winfo_exists(self):
        return True

    def after(self, _delay, callback, *args):
        token = (callback, args)
        self.scheduled.append(token)
        return token

    def after_cancel(self, token):
        self.cancelled.append(token)

    def configure(self, **kwargs):
        self.status = kwargs["text"]

    def _create_installed_app_row(self, row, app):
        self.created.append((row, app))


class InstalledAppRenderingTests(unittest.TestCase):
    def test_rendering_is_bounded_and_completes_in_batches(self):
        panel = PanelHarness()
        InstrumentationPanel._render_installed_batch(panel, 3, "")
        self.assertEqual(len(panel.created), 20)
        self.assertEqual(panel.status, "Rendering 20 of 45 applications")
        while panel.scheduled:
            callback, args = panel.scheduled.pop(0)
            callback(*args)
        self.assertEqual(len(panel.created), 45)
        self.assertEqual(panel.status, "45 applications")

    def test_stale_callback_does_not_destroy_or_create_widgets(self):
        panel = PanelHarness(total=10, old=10)
        old = tuple(panel._installed_render_old_widgets)
        InstrumentationPanel._render_installed_batch(panel, 2, "")
        self.assertFalse(panel.created)
        self.assertTrue(all(not widget.destroyed for widget in old))

    def test_replacement_cleans_old_rows_in_bounded_batches(self):
        panel = PanelHarness(total=1, old=45)
        old = tuple(panel._installed_render_old_widgets)
        InstrumentationPanel._render_installed_batch(panel, 3, "")
        self.assertEqual(sum(widget.destroyed for widget in old), 20)
        self.assertEqual(len(panel.created), 0)
        self.assertTrue(panel.scheduled)

    def test_cancel_invalidates_and_cancels_scheduled_callback(self):
        panel = PanelHarness()
        token = object()
        panel._installed_render_after = token
        InstrumentationPanel._cancel_installed_render(panel)
        self.assertEqual(panel._installed_render_generation, 4)
        self.assertEqual(panel.cancelled, [token])


if __name__ == "__main__":
    unittest.main()
