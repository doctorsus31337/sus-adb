from app.gui.theme import get_theme


_theme = get_theme()


def color(name: str, default: str = "#FFFFFF") -> str:
    return _theme.get(name, default)


def panel():
    return color("panel")


def gold():
    return color("gold")


def background():
    return color("background")


def accent():
    return color("accent")


def button():
    return color("button")


def button_hover():
    return color("button_hover")