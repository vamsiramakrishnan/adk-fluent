"""Pytest conftest that collects cookbook scripts as runnable test items.

Each .py file (except conftest.py itself) is executed as a test.
Top-level assertions in the file serve as the test body.
"""

import importlib.util
import pytest


def pytest_collect_file(parent, file_path):
    if file_path.suffix == ".py" and file_path.name != "conftest.py":
        return ScriptFile.from_parent(parent, path=file_path)


class ScriptFile(pytest.File):
    def collect(self):
        yield ScriptItem.from_parent(self, name=self.path.stem)


class ScriptItem(pytest.Item):
    def runtest(self):
        spec = importlib.util.spec_from_file_location(self.name, self.path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

    def repr_failure(self, excinfo):
        return f"{self.path.name} failed:\n{excinfo.getrepr(style='short')}"

    def reportinfo(self):
        return self.path, 0, f"cookbook: {self.name}"
