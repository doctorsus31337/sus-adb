from app.gui.theme import get_theme


class ThemeManager:

    def __init__(self):

        self.theme = get_theme()

    def color(self, key):

        return self.theme.get(key, "#ffffff")