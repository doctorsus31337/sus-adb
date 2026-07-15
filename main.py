"""
sus-adb
Android Device Companion
"""

from app.gui.main_window import SusADBWindow


def main():

    app = SusADBWindow()

    app.mainloop()


if __name__ == "__main__":
    main()