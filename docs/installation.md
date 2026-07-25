# Installation

Supported Python: 3.11–3.13. Create a virtual environment and install `requirements.txt`. Linux requires a working Tk installation; Windows uses the standard CPython Tk distribution. ADB is required for device work. All other external tools are optional and are not bundled or installed automatically.

Source invocation remains `python main.py`. Packaged builds prefer the `sus-companion` executable and retain a lightweight `sus-adb` compatibility launcher. Existing Linux `~/.config/sus-adb` and Windows `%APPDATA%\SUS-ADB` storage are deliberately reused so configuration, logs, plugin trust, and workspace references do not disappear during the product-name transition.
