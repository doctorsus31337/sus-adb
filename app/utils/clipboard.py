import customtkinter as ctk


class Clipboard:

    @staticmethod
    def copy(widget, text: str) -> bool:
        """
        Copies text to the system clipboard.

        Returns True on success.
        """

        try:
            widget.clipboard_clear()
            widget.clipboard_append(text)
            widget.update()

            return True

        except Exception:
            return False

    @staticmethod
    def paste(widget) -> str:
        """
        Returns the current clipboard contents.
        """

        try:
            return widget.clipboard_get()

        except Exception:
            return ""

    @staticmethod
    def copy_console(widget, console):

        text = console.get("1.0", "end").strip()

        return Clipboard.copy(widget, text)

    @staticmethod
    def copy_selection(widget, console):

        try:
            text = console.selection_get()

        except Exception:
            return False

        return Clipboard.copy(widget, text)

    @staticmethod
    def copy_command(widget, command: str):

        return Clipboard.copy(widget, command)