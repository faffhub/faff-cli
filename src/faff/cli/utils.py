import os
import subprocess

from pathlib import Path

def edit_file(path: Path) -> bool:
    """
    Open a file in the user's preferred editor and check if it was modified.
    If the file was modified, return True. Otherwise, return False.
    """
    editor = os.getenv("EDITOR", "vim") # Default to vim if $EDITOR is not set

    pre_edit_hash = path.read_text().__hash__()
    # Open the file in the editor
    try:
        subprocess.run([editor, str(path)], check=True)
    except FileNotFoundError:
        return

    post_edit_hash = path.read_text().__hash__()

    return pre_edit_hash != post_edit_hash