"""
Pytest configuration and shared fixtures for RepoPilot backend tests.
"""

import pytest


@pytest.fixture
def sample_repo(tmp_path):
    """
    Create a small fake repository structure for testing.

    tmp_path is a pytest built-in fixture that provides a unique
    temporary directory for each test. It's automatically cleaned up.

    This fixture creates:
        sample_repo/
        ├── .git/                  (empty, marks it as a Git repo)
        ├── README.md
        ├── main.py
        ├── utils.py
        ├── src/
        │   ├── app.ts
        │   └── styles.css
        ├── data/
        │   └── image.png          (fake binary file)
        ├── node_modules/
        │   └── lodash/
        │       └── index.js       (should be excluded)
        └── big_file.py            (oversized, should be excluded)
    """
    # Create .git directory to mark this as a Git repo
    (tmp_path / ".git").mkdir()

    # Create source files with some content
    (tmp_path / "README.md").write_text("# Sample Project\n")
    (tmp_path / "main.py").write_text("def main():\n    print('hello')\n")
    (tmp_path / "utils.py").write_text("def add(a, b):\n    return a + b\n")

    # Create subdirectory with more source files
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.ts").write_text("const app = () => {};\n")
    (tmp_path / "src" / "styles.css").write_text("body { margin: 0; }\n")

    # Create a binary file (fake image — just need the extension)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "image.png").write_bytes(b"\x89PNG fake image data")

    # Create an excluded directory (node_modules)
    (tmp_path / "node_modules" / "lodash").mkdir(parents=True)
    (tmp_path / "node_modules" / "lodash" / "index.js").write_text("module.exports = {};\n")

    # Create an oversized file (bigger than 1 MB)
    (tmp_path / "big_file.py").write_text("x = 1\n" * 300_000)

    # Create an excluded file
    (tmp_path / "package-lock.json").write_text('{"name": "test"}')

    return tmp_path
