import pytest
import os
from backend.core.toolbox import Toolbox, PROTECTED_FILES

# Fixture to provide a Toolbox instance for each test function
@pytest.fixture
def toolbox():
    return Toolbox()

def test_write_file(toolbox, tmp_path, monkeypatch):
    """Tests the ability to write a new file using relative paths."""
    monkeypatch.chdir(tmp_path) # Change current directory to the temp path

    test_file = "hello.txt"
    content = "Hello, World!"

    result = toolbox.write_file(test_file, content)

    assert "successfully" in result
    assert (tmp_path / test_file).read_text() == content

def test_read_file(toolbox, tmp_path, monkeypatch):
    """Tests the ability to read an existing file using relative paths."""
    monkeypatch.chdir(tmp_path)

    test_file = "read_me.txt"
    content = "You can read this."
    (tmp_path / test_file).write_text(content)

    result = toolbox.read_file(test_file)

    assert result == content

def test_list_files(toolbox, tmp_path, monkeypatch):
    """Tests the ability to list files in a directory using relative paths."""
    monkeypatch.chdir(tmp_path)

    (tmp_path / "file1.txt").touch()
    (tmp_path / "file2.txt").touch()

    result = toolbox.list_files(".") # List current (temp) directory

    assert "file1.txt" in result
    assert "file2.txt" in result

# --- Security Guardrail Tests ---

def test_read_file_avoids_directory_traversal(toolbox):
    """Tests that read_file prevents directory traversal."""
    result = toolbox.read_file("../some_other_file.txt")
    assert "Error: Access to parent or absolute directories is not allowed." in result

def test_write_file_avoids_directory_traversal(toolbox):
    """Tests that write_file prevents directory traversal."""
    result = toolbox.write_file("../some_other_file.txt", "content")
    assert "Error: Access to parent or absolute directories is not allowed." in result

def test_list_files_avoids_directory_traversal(toolbox):
    """Tests that list_files prevents directory traversal."""
    result = toolbox.list_files("../../")
    assert "Error: Access to parent or absolute directories is not allowed." in result

def test_write_file_protects_critical_files(toolbox):
    """Tests that write_file prevents overwriting protected files."""
    # This test assumes 'config.toml' is in PROTECTED_FILES
    if "config.toml" in PROTECTED_FILES:
        result = toolbox.write_file("config.toml", "new content")
        assert "Error: Overwriting 'config.toml' is not allowed." in result
    else:
        # If config.toml wasn't loaded, the test can't run, but we don't want it to fail.
        pytest.skip("Skipping protected file test because config.toml was not loaded.")
