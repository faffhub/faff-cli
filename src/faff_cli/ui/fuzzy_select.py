from slugify import slugify

import html

from prompt_toolkit import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.layout import Layout, HSplit, Window, VSplit
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style
from prompt_toolkit.shortcuts import print_formatted_text
from prompt_toolkit.formatted_text import HTML

from typing import Union, Any, Optional, List, Sequence
from dataclasses import dataclass

from pfzy import fzy_scorer

style = Style.from_dict({
    "selector":   "fg:ansigray",
    "match":      "fg:ansimagenta bold",
    "select":     "fg:ansiblue",
    "decoration": "fg:ansigreen",
    "count":      "fg:ansigreen",
})

@dataclass
class FuzzyItem:
    name: str
    value: Any
    decoration: Optional[str] = None
    is_new: bool = False

def is_list_of_strs(items: Sequence[Any]) -> bool:
    return all(isinstance(i, str) for i in items)

def is_list_of_dicts(items: Sequence[Any]) -> bool:
    return all(isinstance(i, dict) and "name" in i and "value" in i for i in items)

def is_list_of_dataclasses(items: Sequence[Any]) -> bool:
    return all(isinstance(i, FuzzyItem) for i in items)

def normalize_to_fuzzyitems(items: Sequence[Any]) -> List[FuzzyItem]:
    if is_list_of_strs(items):
        return [FuzzyItem(name=i, value=i) for i in items]
    elif is_list_of_dicts(items):
        return [FuzzyItem(name=i["name"], value=i.get("value", i["name"]), decoration=i.get("decoration")) for i in items]
    elif is_list_of_dataclasses(items):
        return list(items)
    else:
        raise TypeError("Expected list of str, dicts with name/value, or FuzzyItem instances")

def slugify_preserving_slashes(path: str, **kwargs) -> str:
    segments = path.split("/")
    return "/".join(slugify(seg, **kwargs) for seg in segments)

def fuzzy_select(prompt: str,
                 choices: Sequence[Union[str, FuzzyItem]],
                 create_new: bool = True,
                 max_fraction: float = 0.5,
                 escapable: bool = True,
                 slugify_new: bool = True) -> FuzzyItem | None:

    import shutil
    total = shutil.get_terminal_size().lines
    max_rows = max(3, int(total * max_fraction))

    normalised_choices = normalize_to_fuzzyitems(choices)

    user_input    = ""
    matches       = normalised_choices[:]
    match_indices = {}
    selected_idx  = 0
    offset        = 0

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
            # FIXME: This shouldn't match on the string. 
            # Actually, I think the signature here should be:
            # selected_item, new_string = app.run()
            # and either selected_item or new_string should 
            # actually would it be better if this thing _only_ handled strings?
            event.app.exit(result=val)
        else:
            event.app.exit(result=None)

    @kb.add("escape", eager=True)
    def _(event):
        if escapable:
            event.app.exit(result=None)

    @kb.add("c-c")
    def _(event):
        raise KeyboardInterrupt()

    buf = Buffer()

    def offer_to_create_new() -> bool:
        return (create_new and 
                user_input != "" and
                user_input not in [c.name for c in matches])

    def on_change(_):
        nonlocal user_input, matches, match_indices, selected_idx, offset
        user_input = buf.text
        if not user_input.strip():
            matches = normalised_choices[:]
            match_indices = {}
        else:
            scored = []
            for cand in normalised_choices:
                score, idxs = fzy_scorer(user_input, cand.name)
                if score > 0:
                    scored.append((cand, score, idxs))
            scored.sort(key=lambda x: x[1], reverse=True)
            matches = [c for c,_,_ in scored]
            match_indices = {c.name: idxs for c,_,idxs in scored}
            if offer_to_create_new():
                if slugify_new:
                    # FIXME: World's longest line.
                    matches.append(FuzzyItem(name=f"Create new: {user_input.strip()} (local:{slugify_preserving_slashes(user_input)})", value=f"local:{slugify_preserving_slashes(user_input)}", is_new=True))
                else:
                    matches.append(FuzzyItem(name=f"Create new: {user_input}", value=user_input.strip(), is_new=True))
                    
        selected_idx = 0
        offset = 0

    buf.on_text_changed += on_change

    def get_menu_tokens():
        tokens = []
        visible = matches[offset: offset + max_rows]
        for i, m in enumerate(visible):
            actual_i = offset + i
            is_sel   = (actual_i == selected_idx)

            tokens.append(("class:selector", "❯ " if is_sel else "  "))

            name = m.name
            idxs = match_indices.get(name, [])
            last = 0
            for pos in idxs:
                if pos > last:
                    tag = "class:select" if is_sel else ""
                    tokens.append((tag, name[last:pos]))
                tokens.append(("class:match", name[pos]))
                last = pos + 1
            if last < len(name):
                tag = "class:select" if is_sel else ""
                tokens.append((tag, name[last:]))

            if m.decoration:
                tokens.append(("class:decoration", f" {m.decoration}"))
            tokens.append(('', "\n"))

        return tokens

    prompt_win = Window(height=1, content=FormattedTextControl('? ' + prompt))

    def get_input_width():
        return len(buf.text) + 1  # +1 for caret space

    input_row = VSplit([
        Window(width=2, content=FormattedTextControl("❯ ")),
        Window(
            content=BufferControl(buffer=buf),
            width=lambda: get_input_width(),
            always_hide_cursor=False,
        ),
        Window(width=1),  # spacer
        Window(
            height=1,
            content=FormattedTextControl(lambda: [("class:count", f"{len(matches) - offer_to_create_new() * 1}/{len(normalised_choices)}")]),
            dont_extend_width=True,
        ),
    ])

    menu_win = Window(content=FormattedTextControl(get_menu_tokens),
                      wrap_lines=False,
                      height=Dimension(max=max_rows))

    root = HSplit([prompt_win, input_row, menu_win])
    app: Application = Application(layout=Layout(root),
                                   key_bindings=kb,
                                   style=style,
                                   full_screen=False,
                                   erase_when_done=True)

    app.ttimeoutlen = 0.0001
    app.timeoutlen = 0.0001

    selection = app.run()

    if selection:
        print_formatted_text(
            HTML(f"? {prompt} <ansiblue>{html.escape(selection.name)}</ansiblue>{' <ansimagenta>*NEW*</ansimagenta>' if selection and selection.is_new else ''}")
        )

    return selection