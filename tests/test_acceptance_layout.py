import re
import unittest
from pathlib import Path

from app.core.responsive_layout import (
    estimated_button_width,
    wrap_widths,
)


ROOT = Path(__file__).parents[1]


class AcceptanceLayoutTests(unittest.TestCase):
    def test_responsive_rows_fit_at_normal_and_scaled_widths(self):
        labels = (
            "Open Instrumentation",
            "Open Script Studio",
            "Open Runtime Explorer",
            "Open Network Workspace",
            "Copy Restoration Guidance",
            "Export Case Summary",
        )
        widths = tuple(estimated_button_width(label, 125) for label in labels)
        for window_width in (1200, 1400):
            for scale in (1.0, 1.25, 1.5):
                available = int((window_width - 330) / scale)
                rows = wrap_widths(available, widths)
                self.assertEqual(
                    tuple(index for row in rows for index in row),
                    tuple(range(len(labels))),
                )
                for row in rows:
                    used = sum(min(available, widths[index]) for index in row)
                    used += 6 * max(0, len(row) - 1)
                    self.assertLessEqual(used, available)

    def test_no_visible_help_text_starts_with_question_mark(self):
        roots = (
            ROOT / "app/gui",
            ROOT / "app/widgets",
            ROOT / "app/plugins",
            ROOT / "plugins/official",
        )
        pattern = re.compile(r"""text\s*=\s*["']\?\s*Help""")
        failures = []
        for root in roots:
            for path in root.rglob("*.py"):
                if pattern.search(path.read_text(encoding="utf-8")):
                    failures.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(failures, [])

    def test_sidebar_is_device_only_and_reference_is_under_tools(self):
        main = (ROOT / "app/gui/main_window.py").read_text(encoding="utf-8")
        menu = (ROOT / "app/gui/menu_bar.py").read_text(encoding="utf-8")
        self.assertNotIn("ActionPanel", main)
        self.assertNotIn('text="⚔ Advanced Command Reference"', main)
        self.assertIn(
            'tools_menu.add_command(label="Advanced Command Reference"', menu
        )
        help_section = menu.split(
            "help_menu = tk.Menu", 1
        )[1].split('menu.add_cascade(label="Help"', 1)[0]
        self.assertNotIn("Advanced Command Reference", help_section)


if __name__ == "__main__":
    unittest.main()
