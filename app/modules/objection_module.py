import subprocess


class ObjectionModule:

    def run(self, *args):

        result = subprocess.run(
            ["objection", *args],
            capture_output=True,
            text=True
        )

        output = result.stdout.strip()

        if result.stderr:
            output += "\n" + result.stderr.strip()

        return output

    def version(self):
        return self.run("version")

    def explore(self, package):
        return self.run("-g", package, "explore")