"""Cached, failure-safe GUI loading for SUS Companion branding."""

from __future__ import annotations

import tkinter as tk

from PIL import Image, UnidentifiedImageError

from app.core.branding_assets import APP_ICON_PNG, BrandingAssetResolver


class BrandingImages:
    def __init__(self, resolver=None):
        self.resolver = resolver or BrandingAssetResolver()
        self._pil_cache = {}
        self._ctk_cache = {}
        self._window_icon = None

    def pil_image(self, filename):
        if filename in self._pil_cache:
            return self._pil_cache[filename]
        path = self.resolver.resolve(filename)
        if path is None:
            self._pil_cache[filename] = None
            return None
        try:
            with Image.open(path) as source:
                source.load()
                image = source.convert("RGBA")
        except (OSError, ValueError, UnidentifiedImageError):
            image = None
        self._pil_cache[filename] = image
        return image

    def ctk_image(self, filename, size):
        import customtkinter as ctk
        key = (filename, tuple(size))
        if key not in self._ctk_cache:
            image = self.pil_image(filename)
            self._ctk_cache[key] = (
                ctk.CTkImage(light_image=image, dark_image=image, size=size)
                if image is not None
                else None
            )
        return self._ctk_cache[key]

    def apply_window_icon(self, window, *, default=False):
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
