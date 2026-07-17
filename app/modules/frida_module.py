import subprocess


class FridaModule:

    def run(self, *args):

        result = subprocess.run(
            ["frida", *args],
            capture_output=True,
            text=True
        )

        output = result.stdout.strip()

        if result.stderr:
            output += "\n" + result.stderr.strip()

        return output

    def version(self):
        return self.run("--version")

    def list_processes(self):
        return self.run("-U", "-ai")

    def attach(self, package):
        return self.run("-U", "-n", package)

    def spawn(self, package):
        return self.run("-U", "-f", package)