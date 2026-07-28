import ast
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
PYINSTALLER_AVAILABLE = importlib.util.find_spec("PyInstaller") is not None


def toc_names(value):
    names = set()
    if isinstance(value, (tuple, list)):
        if value and isinstance(value[0], str):
            names.add(value[0])
        for item in value:
            names.update(toc_names(item))
    return names


@unittest.skipUnless(
    PYINSTALLER_AVAILABLE,
    "PyInstaller is exercised by the platform packaging workflow",
)
class PackagedPillowRuntimeTests(unittest.TestCase):
    def test_repository_hook_collects_and_executes_pillow_tk_runtime(self):
        from PyInstaller.archive.readers import pkg_archive_contents

        with tempfile.TemporaryDirectory(
            prefix="SUS Companion Pillow Tk package "
        ) as directory:
            temporary = Path(directory)
            source = temporary / "pillow_tk_fixture.py"
            source.write_text(
                "import tkinter\n"
                "from PIL import Image, ImageTk, _tkinter_finder\n"
                "print(Image.__name__, ImageTk.__name__, "
                "_tkinter_finder.__name__)\n",
                encoding="utf-8",
            )
            dist = temporary / "portable dist"
            work = temporary / "analysis work"
            spec = temporary / "generated spec"
            subprocess.run(
                (
                    sys.executable,
                    "-m",
                    "PyInstaller",
                    "--clean",
                    "--noconfirm",
                    "--console",
                    "--name",
                    "pillow-tk-fixture",
                    "--distpath",
                    str(dist),
                    "--workpath",
                    str(work),
                    "--specpath",
                    str(spec),
                    "--additional-hooks-dir",
                    str(ROOT / "packaging/pyinstaller/hooks"),
                    str(source),
                ),
                cwd=temporary,
                check=True,
                capture_output=True,
                text=True,
            )
            analysis = ast.literal_eval(
                (
                    work
                    / "pillow-tk-fixture"
                    / "Analysis-00.toc"
                ).read_text(encoding="utf-8")
            )
            required = {
                "PIL.Image",
                "PIL.ImageTk",
                "PIL._tkinter_finder",
            }
            self.assertTrue(required <= toc_names(analysis))
            executable = (
                dist
                / "pillow-tk-fixture"
                / (
                    "pillow-tk-fixture.exe"
                    if os.name == "nt"
                    else "pillow-tk-fixture"
                )
            )
            inventory = set(pkg_archive_contents(executable))
            self.assertTrue(required <= inventory)
            result = subprocess.run(
                (str(executable),),
                cwd=temporary,
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                result.stdout.strip(),
                "PIL.Image PIL.ImageTk PIL._tkinter_finder",
            )


if __name__ == "__main__":
    unittest.main()
