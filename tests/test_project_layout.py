from pathlib import Path
import unittest


class ProjectLayoutTest(unittest.TestCase):
    def test_only_new_thin_python_scripts_remain(self):
        script_names = {path.name for path in Path("scripts").glob("*.py")}
        self.assertEqual(script_names, {"serve.py", "build.py", "deploy.py", "normalize.py"})

    def test_no_powershell_scripts_remain(self):
        self.assertEqual(list(Path("scripts").glob("*.ps1")), [])


if __name__ == "__main__":
    unittest.main()
