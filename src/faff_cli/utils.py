import os
import subprocess

from pathlib import Path

def edit_file(path: Path) -> bool:
    """
    Open a file in the user's preferred editor and check if it was modified.
    If the file was modified, return True. Otherwise, return False.
    """
    editor = os.getenv("EDITOR", "vim") # Default to vim if $EDITOR is not set

    pre_edit = path.read_text()
    # pre_edit_hash = path.read_text().__hash__()

    # Open the file in the editor
    subprocess.run([editor, str(path)], check=True)

    post_edit = path.read_text()
    # post_edit_hash = path.read_text().__hash__()

    # You'd expect us to use the hash here, but the default edtior
    # vim whacks a newline on the end of the file upon save.
    # Following the principle of least surprise, I want to tell the user
    # when it the file has _semantically_ changed, so I'm going to ignore
    # newline and compare the text.

    return pre_edit.strip() != post_edit.strip()
