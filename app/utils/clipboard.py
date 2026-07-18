class ClipboardManager:
    """Clipboard helper."""

    @staticmethod
    def copy(widget):
        try:
            text = widget.get("sel.first", "sel.last")
        except Exception:
            try:
                text = widget.get("1.0", "end").strip()
            except Exception:
                return False

        widget.clipboard_clear()
        widget.clipboard_append(text)
        widget.update()

        return True

    @staticmethod
    def paste(entry):
        try:
            text = entry.clipboard_get()
            entry.insert("insert", text)
            return True
        except Exception:
            return False