"""Local-only GUI acceptance smoke for SUS Companion branding."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _bounds(widget):
    return (
        widget.winfo_rootx(),
        widget.winfo_rooty(),
        widget.winfo_width(),
        widget.winfo_height(),
    )


def _inside(widget, parent):
    x, y, width, height = _bounds(widget)
    px, py, pwidth, pheight = _bounds(parent)
    return (
        x >= px
        and y >= py
        and x + width <= px + pwidth
        and y + height <= py + pheight
    )


def main():
    with tempfile.TemporaryDirectory() as directory:
        os.environ["XDG_CONFIG_HOME"] = directory
        import customtkinter as ctk

        from app.core.branding_assets import BrandingAssetResolver
        from app.gui.about_window import AboutWindow
        from app.gui.branding_images import BrandingImages
        from app.gui.main_window import SusADBWindow
        from app.gui.splash_screen import SplashScreen
        from app.gui.gothic_header import GothicHeader
        from app.core.startup_tips import load_startup_tips

        app = SusADBWindow()
        app._deferred_started = True
        assert getattr(app, "_sus_companion_icon_image", None) is not None
        assert app.gothic_header.artwork_image is not None
        assert app.gothic_header.artwork.cget("image") is app.gothic_header.artwork_image
        assert app.about_window is None
        assert "sus-companion-about.png" not in app.branding._pil_cache
        app.navigate_workspace("Console")
        app.gothic_header.artwork._canvas.event_generate("<Button-1>", x=2, y=2)
        app.update_idletasks()
        assert app.workspace.get() == "Home"

        for width, height in ((600, 360), (720, 430)):
            splash = SplashScreen(
                app,
                app.theme,
                load_startup_tips(),
                branding=app.branding,
                width=width,
                height=height,
            )
            splash.update_idletasks()
            assert getattr(splash, "_sus_companion_icon_image", None) is not None
            splash.close()

        main_measurements = []
        for width, height in ((1200, 760), (1400, 860), (1600, 900)):
            app.geometry(f"{width}x{height}+0+0")
            app.update_idletasks()
            header = app.gothic_header
            assert header.winfo_height() <= 90
            assert _inside(header.artwork, header)
            assert _inside(header.title, header)
            assert _inside(header.mode, header)
            assert _inside(header.help_button, header)
            main_measurements.append(
                {
                    "window": (width, height),
                    "header_height": header.winfo_height(),
                    "artwork": _bounds(header.artwork),
                    "title": _bounds(header.title),
                    "mode": _bounds(header.mode),
                    "help": _bounds(header.help_button),
                }
            )

        about = app.open_about()
        assert app.open_about() is about
        assert about.artwork_image is not None
        assert "1.0.0-rc.2" in about.version_label.cget("text")
        about_measurements = []
        for width, height in ((720, 560), (900, 650), (1100, 760)):
            about.geometry(f"{width}x{height}+0+0")
            about.update_idletasks()
            assert _inside(about.close_button, about)
            assert about.artwork_label.winfo_width() == 230
            assert about.artwork_label.winfo_height() == 343
            assert about.winfo_width() == width and about.winfo_height() == height
            assert about.content._parent_canvas.xview() == (0.0, 1.0)
            initial_artwork = _bounds(about.artwork_label)
            about.content._parent_canvas.yview_moveto(1.0)
            about.update_idletasks()
            footer_top = about.close_button.winfo_rooty()
            assert about.attribution_label.winfo_rooty() < footer_top
            about_measurements.append(
                {
                    "window": (width, height),
                    "artwork_initial": initial_artwork,
                    "name": _bounds(about.name_label),
                    "mission": _bounds(about.mission_label),
                    "attribution": _bounds(about.attribution_label),
                    "close": _bounds(about.close_button),
                }
            )
        about.close()
        assert app.about_window is None

        missing_root = Path(directory) / "missing branding"
        missing_root.mkdir()
        missing_branding = BrandingImages(BrandingAssetResolver(missing_root))
        fallback = AboutWindow(
            app,
            app.theme,
            missing_branding,
            width=720,
            height=560,
        )
        fallback.update_idletasks()
        assert fallback.artwork_image is None
        assert "SUS COMPANION" in fallback.artwork_label.cget("text")
        fallback.close()
        fallback_header = GothicHeader(
            app,
            app.theme,
            branding=missing_branding,
        )
        fallback_header.grid()
        app.update_idletasks()
        assert fallback_header.artwork_image is None
        assert "SUS COMPANION" in fallback_header.title.cget("text")
        fallback_header.destroy()

        scaled = []
        for scale in (1.0, 1.25, 1.5):
            ctk.set_widget_scaling(scale)
            app.geometry("1200x760+0+0")
            app.update_idletasks()
            about = app.open_about()
            about.geometry("720x560+0+0")
            about.update_idletasks()
            assert _inside(app.gothic_header.help_button, app.gothic_header)
            assert app.gothic_header.winfo_height() <= 110
            assert _inside(about.close_button, about)
            assert about.content._scrollbar.cget("button_color") == app.theme["gold_dark"]
            scaled.append(
                (
                    scale,
                    app.gothic_header.winfo_height(),
                    about.content._scrollbar.winfo_width(),
                )
            )
            about.close()
        ctk.set_widget_scaling(1.0)

        assert not app._background_workers
        app.shutdown()
        print(
            "branding-smoke=PASS "
            f"main={main_measurements} about={about_measurements} "
            f"scaling={scaled} splash=600x360,720x430 "
            "singleton-fallback-icon-shutdown=PASS"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
