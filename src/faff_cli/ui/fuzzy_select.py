from prompt_toolkit import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.layout import Layout, HSplit, Window, VSplit
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style

# Style: blue for selected text, purple bold for matches, gray for arrow
style = Style.from_dict({
    "select":   "ansiblue",
    "match":    "ansimagenta bold",
    "selector": "ansigray",
})

def fuzzy_match(candidate: str, pattern: str) -> bool:
    """Return True if pattern fuzzily matches candidate."""
    return pattern.lower() in "".join([x for x in list(candidate.lower())
                                         if x in list(pattern.lower())])

def highlight_substrings(text: str, pattern: str):
    """
    Given a candidate `text` and a `pattern`, yield (style, fragment) pairs
    where exactly the first match of each successive character in pattern
    is wrapped with 'class:match', and all other text is unstyled.

    Example:
      text = "Solutions Architect"
      pattern = "sa"
      → highlights the 'S' in "Solutions" and the 'a' in "Architect"
    """
    lower_text    = text.lower()
    lower_pattern = pattern.lower()

    # 1) find the indices to highlight
    highlight_idxs = []
    search_start = 0
    for ch in lower_pattern:
        idx = lower_text.find(ch, search_start)
        if idx == -1:
            break
        highlight_idxs.append(idx)
        search_start = idx + 1

    # 2) now emit fragments
    last = 0
    for idx in highlight_idxs:
        if idx > last:
            # unhighlighted run
            yield ("", text[last:idx])
        # the highlighted character
        yield ("class:match", text[idx])
        last = idx + 1

    # 3) any trailing text
    if last < len(text):
        yield ("", text[last:])


def fuzzy_select(prompt_text: str, choices: list[str]):
    """
    Live fuzzy-filter + arrow-nav + enter-to-select + create-new fallback.
    • selected line in blue
    • only first substring match or initials highlighted in purple
    Returns (selection: str, was_created: bool).
    """
    user_input   = ""
    matches      = choices.copy()
    selected_idx = 0

    kb = KeyBindings()
    @kb.add("up")
    def _(event):
        nonlocal selected_idx
        selected_idx = max(0, selected_idx - 1)

    @kb.add("down")
    def _(event):
        nonlocal selected_idx
        selected_idx = min(len(matches) - 1, selected_idx + 1)

    @kb.add("enter")
    def _(event):
        val = matches[selected_idx]
        event.app.exit(result=(val, val not in choices))

    @kb.add("escape")
    @kb.add("c-c")
    def _(event):
        event.app.exit(result=(None, False))

    buf = Buffer()
    def on_change(_):
        nonlocal user_input, matches, selected_idx
        user_input = buf.text
        if not user_input:
            matches = choices.copy()
        else:
            filtered = [c for c in choices if fuzzy_match(c, user_input)]
            if user_input not in filtered:
                filtered.append(f"Create new: {user_input}")
            matches = filtered
        selected_idx = 0

    buf.on_text_changed += on_change

    def get_menu_tokens():
        tokens = []
        for i, m in enumerate(matches):
            is_sel = (i == selected_idx)

            # 1) Arrow prefix: always gray
            tokens.append(("class:selector", "❯ " if is_sel else "  "))

            # 2) Line text
            if m.startswith("Create new: "):
                # The “Create new” line: only blue if selected
                text_style = "class:select" if is_sel else ""
                tokens.append((text_style, m + "\n"))
            else:
                # Normal lines: highlight matched letters purple,
                # then if selected, make the text blue
                for part_style, fragment in highlight_substrings(m, user_input):
                    if is_sel:
                        # combine purple-match with blue-selected
                        style_name = f"{part_style} class:select".strip()
                    else:
                        style_name = part_style
                    tokens.append((style_name, fragment))
                tokens.append(("", "\n"))
        return tokens

    prompt_win = Window(height=1,
                        content=FormattedTextControl('? ' + prompt_text))
    #input_win  = Window(height=1,
    #                    content=BufferControl(buffer=buf))
    
    input_row = VSplit([
        Window(width=2, content=FormattedTextControl("❯ ")),
        Window(height=1, content=BufferControl(buffer=buf)),
    ])


    menu_win   = Window(content=FormattedTextControl(get_menu_tokens),
                        wrap_lines=False)

    root = HSplit([prompt_win, input_row, menu_win])
    layout = Layout(root)

    app = Application(layout=layout,
                      key_bindings=kb,
                      style=style,
                      full_screen=False)
    return app.run()
