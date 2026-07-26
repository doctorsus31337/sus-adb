"""Cached, failure-safe GUI loading for SUS Companion branding."""

from __future__ import annotations

import tkinter as tk

from app.core.branding_assets import APP_ICON_PNG, BrandingAssetResolver
from app.core.branding_dependencies import (
    is_missing_pillow_error,
    report_missing_pillow,
)


_UNRESOLVED = object()


class BrandingImages:
    def __init__(self, resolver=None):
        self.resolver = resolver or BrandingAssetResolver()
        self._pil_cache = {}
        self._ctk_cache = {}
        self._window_icon = None
        self._pillow = _UNRESOLVED

    def _pillow_modules(self):
        if self._pillow is _UNRESOLVED:
            try:
                from PIL import Image, UnidentifiedImageError
            except ModuleNotFoundError as error:
                if not is_missing_pillow_error(error):
                    raise
                report_missing_pillow()
                self._pillow = None
            else:
                self._pillow = (Image, UnidentifiedImageError)
        return self._pillow

    def pil_image(self, filename):
        if filename in self._pil_cache:
            return self._pil_cache[filename]
        path = self.resolver.resolve(filename)
        if path is None:
            self._pil_cache[filename] = None
            return None
        pillow = self._pillow_modules()
        if pillow is None:
            self._pil_cache[filename] = None
            return None
        Image, UnidentifiedImageError = pillow
        try:
            with Image.open(path) as source:
                source.load()
                image = source.convert("RGBA")
        except (OSError, ValueError, UnidentifiedImageError):
            image = None
        self._pil_cache[filename] = image
        return image

    def ctk_image(self, filename, size):
        key = (filename, tuple(size))
        if key not in self._ctk_cache:
            image = self.pil_image(filename)
            if image is None:
                self._ctk_cache[key] = None
            else:
                import customtkinter as ctk
                self._ctk_cache[key] = ctk.CTkImage(
                    light_image=image,
                    dark_image=image,
                    size=size,
                )
        return self._ctk_cache[key]

    def apply_window_icon(self, window, *, default=False):
        if self._pillow_modules() is None:
            return False
        if self._window_icon is None:
            path = self.resolver.resolve(APP_ICON_PNG)
            if path is None:
                return False
            try:
                self._window_icon = tk.PhotoImage(master=window, file=str(path))
            except (OSError, tk.TclError):
                return False
        try:
            window.iconphoto(bool(default), self._window_icon)
            window._sus_companion_icon_image = self._window_icon
            return True
        except tk.TclError:
            return False
