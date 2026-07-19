# Testing

Run `python -m unittest discover -s tests -v`, compilation, then `python scripts/run_release_checks.py`. GUI smoke uses Xvfb on Linux. Automated tests must not contact real devices, tools, networks, or processes.
