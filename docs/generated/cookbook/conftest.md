# Pytest conftest that collects cookbook scripts as runnable test items.

Each .py file (except conftest.py itself) is executed as a test.
Top-level assertions in the file serve as the test body.

_Source: `conftest.py`_
