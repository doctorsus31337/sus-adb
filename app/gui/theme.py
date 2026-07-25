"""
SUS Companion Medieval Gothic Blackhat Theme
"""

THEME = {
    # Core colors
    "bg": "#090909",
    "panel": "#131313",
    "panel_alt": "#1B1B1B",
    "border": "#2D2D2D",

    # Primary colors
    "gold": "#D6B55A",
    "gold_dark": "#8B6B1D",
    "red": "#6E0F0F",
    "red_hover": "#9B1717",

    "button": "#821313",
    "button_hover": "#aa1c1c",
    "panel_border": "#363636",
    "title": "#d6b55a",
    "subtitle": "#9f8f67",

    # Text
    "text": "#EFE2B0",
    "muted": "#9D9272",

    # Terminal
    "terminal_bg": "#050505",
    "terminal_text": "#D8D1BB",

    # Status
    "success": "#56B870",
    "error": "#B83C3C",

    # Fonts
    "title_font": ("Times New Roman", 42, "bold"),
    "header_font": ("Times New Roman", 20, "bold"),
    "button_font": ("Segoe UI", 15, "bold"),
    "terminal_font": ("Consolas", 15)
}


def get_theme():
    return THEME
