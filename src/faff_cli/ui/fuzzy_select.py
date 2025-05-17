from prompt_toolkit import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.layout import Layout, HSplit, Window, VSplit
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style
from prompt_toolkit.shortcuts import print_formatted_text
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.enums import EditingMode

from typing import Union, Tuple

from pfzy import fzy_scorer  # or your own scorer

style = Style.from_dict({
    "selector": "fg:ansigray",
    "match":    "fg:ansimagenta bold",
    "select":   "fg:ansiblue",
})

def fuzzy_select(prompt: str,
                 choices: list[str],
                 create_new: bool = True,
                 max_fraction: float = 0.5,
                 escapable: bool = True) -> Tuple[Union[str, None], bool]:

    # compute max visible rows
    import shutil
    total = shutil.get_terminal_size().lines
    max_rows = max(3, int(total * max_fraction))

    choices_dict = None

    if choices and isinstance(choices[0], dict):
        # If the choices are dicts, we need to extract the string values
        # for fuzzy matching and display.
        choices_dict = {c["name"]: c["value"] for c in choices}
        choices = [c["name"] for c in choices]

    user_input    = ""
    matches       = choices[:]
    match_indices = {}
    selected_idx  = 0
    offset        = 0     # top‐of‐view index

    kb = KeyBindings()
    @kb.add("up")
    def _(event):
        nonlocal selected_idx, offset
        selected_idx = max(0, selected_idx - 1)
        if selected_idx < offset:
            offset = selected_idx

    @kb.add("down")
    def _(event):
        nonlocal selected_idx, offset
        selected_idx = min(len(matches) - 1, selected_idx + 1)
        if selected_idx >= offset + max_rows:
            offset = selected_idx - max_rows + 1

    @kb.add("enter")
    def _(event):
        if selected_idx < len(matches):
            val = matches[selected_idx]
            event.app.exit(result=(val, val not in choices))
        else:
            event.app.exit(result=(None, False))

    @kb.add("escape", eager=True)
    def _(event):
        if escapable:
            event.app.exit(result=(None, False))

    @kb.add("c-c")
    def _(event):
        raise KeyboardInterrupt()

    buf = Buffer()
    def on_change(_):
        nonlocal user_input, matches, match_indices, selected_idx, offset, create_new
        user_input = buf.text
        # reset
        if not user_input.strip():
            matches, match_indices = choices[:], {}
        else:
            scored = []
            for cand in choices:
                score, idxs = fzy_scorer(user_input, cand)
                if score > 0:
                    scored.append((cand, score, idxs))
            scored.sort(key=lambda x: x[1], reverse=True)
            matches       = [c for c,_,_ in scored]
            match_indices = {c: idxs for c,_,idxs in scored}
            if create_new and user_input not in matches:
                matches.append(f"Create new: {user_input}")
        # reset view
        selected_idx = 0
        offset       = 0

    buf.on_text_changed += on_change

    def get_menu_tokens():
        nonlocal create_new

        tokens = []
        visible = matches[offset: offset + max_rows]
        for i, m in enumerate(visible):
            actual_i = offset + i
            is_sel   = (actual_i == selected_idx)

            # 1) Arrow prefix: always grey for non-selected, but green? always selector
            tokens.append(("class:selector", "❯ " if is_sel else "  "))

            # 2) Line text
            if create_new and m.startswith("Create new: "):
                # if it's the "create new" line, tag the whole thing
                text_tag = "class:select" if is_sel else ""
                tokens.append((text_tag, m + "\n"))
            else:
                # normal lines: highlight each matched char in purple,
                # **and** also tag ALL fragments with select if is_sel
                idxs = match_indices.get(m, [])
                last = 0
                for pos in idxs:
                    if pos > last:
                        # pre-match fragment
                        tag = "class:select" if is_sel else ""
                        tokens.append((tag, m[last:pos]))
                    # the matched character
                    tag = "class:match"
                    #if is_sel:
                    #    tag += " class:select"
                    tokens.append((tag, m[pos]))
                    last = pos + 1

                # any trailing text
                if last < len(m):
                    tag = "class:select" if is_sel else ""
                    tokens.append((tag, m[last:]))

                # finally the newline
                tokens.append(("", "\n"))

        return tokens 
 
    prompt_win = Window(height=1,
                        content=FormattedTextControl('? ' + prompt))

    input_row = VSplit([
        Window(width=2, content=FormattedTextControl("❯ ")),
        Window(height=1, content=BufferControl(buffer=buf)),
    ])    

    menu_win   = Window(
        content=FormattedTextControl(get_menu_tokens),
        wrap_lines=False,
        height=Dimension(max=max_rows)
    )

    root = HSplit([prompt_win, input_row, menu_win])
    app  = Application(layout=Layout(root),
                       key_bindings=kb,
                       style=style,
                       full_screen=False,
                       erase_when_done=True)

    # How long (in seconds) to distinguish a bare ESC from an ANSI‐sequence start.
    # By default PromptToolkit uses 0.5 s; Vim’s ttimeoutlen is in milliseconds.
    app.ttimeoutlen = 0.0001   # e.g. 150 ms

    # How long to wait for a multi‐key binding to complete (like “AB” vs “A”).
    # Defaults to 1.0 s; set to None to disable or a smaller float to tighten it.
    app.timeoutlen = None     # e.g. 500 ms

    selection, created = app.run()
    if not create_new:
        created = False

    if selection and not created and choices_dict:
        # If we started with dicts, return the value instead of the name
        selection = {"name": selection,
                     "value": choices_dict[selection]}

        print_formatted_text(
            HTML(f"? {prompt} <ansiblue>{selection.get('name')}</ansiblue>")
        )
    else:

        if created:
            selection = selection[len("Create new: "):]

        print_formatted_text(
            HTML(f"? {prompt} <ansiblue>{selection}</ansiblue>{' <ansimagenta>*NEW*</ansimagenta>' if created else ''}")
        )

    return selection, created