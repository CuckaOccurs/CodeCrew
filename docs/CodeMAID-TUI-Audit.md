# CodeMAID TUI Audit — Resize & Layout Fixes
**Date:** 2026-04-19
**File:** `codemaid/cli/main.py`

---

## The Core Problem

The TUI uses `\033[s` / `\033[u` (ANSI save/restore cursor) to anchor the footer at the bottom. It draws correctly on first run, but **has no handler for `SIGWINCH`** — the signal the kernel sends when the terminal is resized. So when you resize, nothing happens. The next draw (triggered by typing or thinking) will use the new width for the separator lines and status bar, but the old content above stays at the old width, and the cursor anchor is now in the wrong place.

---

## Exact Problems in `main.py`

### 1. No SIGWINCH handler (line 212 — startup block)
```python
# MISSING — this never exists
signal.signal(signal.SIGWINCH, _handle_resize)
```
Without this, a terminal resize is completely invisible to the app.

---

### 2. History stores pre-rendered strings, not renderables (line 204)
```python
def _add(text, style=THEME["dim"]): history.append(_render(Text(text, style=style)))
```
And throughout the code:
```python
history.append(_render(Markdown(result)))
history.append(_render(Panel(...)))
history.append(_render(Text.assemble(...)))
```

`_render()` bakes the Rich object into an ANSI string at the **current terminal width** and stores that string. On resize, those strings can't reflow — they're already baked. A full redraw replays them at the wrong width.

---

### 3. `_render()` captures width at call time (config.py line 52)
```python
c = Console(file=buf, force_terminal=True,
            width=width or console.width,   # ← captured right now
            highlight=False, soft_wrap=True)
```
`console.width` is dynamic (calls `shutil.get_terminal_size()` each time), so NEW items after resize render at the correct width. But old items in history are already baked strings — they're stuck at their original width.

---

### 4. Cursor anchor breaks on resize (lines 190, 200–201)
```python
sys.stdout.write("\033[u\033[J")          # restore to saved position, erase below
...
sys.stdout.write("\033[s\n")              # save new anchor after last history item
...
sys.stdout.write(f"\033[u\033[2B\033[{5+len(input_buffer)}G")  # move to input
```
`\033[s` saves an absolute cursor row/column. When the terminal resizes and reflows, that row number is no longer valid. The footer ends up drawn at the wrong position.

---

### 5. Status bar width is correct, but never triggered (lines 174–184)
```python
def _status_bar():
    _, w = _sh.get_terminal_size()   # ← correct, dynamic
    ...
    pad = " " * max(0, w - len(re.sub(r'\033\[[0-9;]*m', '', line1)) - len(agent.provider.model) - 1)
```
The status bar and separator lines (`"─" * _w`) already read the current terminal width at draw time — that part is fine. The only missing piece is that `_draw()` is never *called* after a resize.

---

## The Fix

### Step 1 — Add SIGWINCH handler

Add this **inside** the `main()` function, right before the `while True:` loop (after the `agent` and state setup):

```python
import signal, shutil

def _handle_resize(signum=None, frame=None):
    """Called by kernel on terminal resize (SIGWINCH)."""
    sys.stdout.write("\033[2J\033[H\033[s")   # clear screen, home, save anchor at top
    sys.stdout.flush()
    _drawn_count[0] = 0                        # force full history replay
    _draw()

signal.signal(signal.SIGWINCH, _handle_resize)
```

This clears the screen on resize, resets the anchor to the top-left, and forces `_draw()` to replay all history items. Old items will still be at the old width (see Step 2 for the proper fix), but the footer, separator, and status bar will be correct immediately.

---

### Step 2 — Store renderables alongside strings (proper reflow)

Change history from a list of strings to a list of `(renderable, str)` tuples so items can be re-rendered at the new width on resize.

**In `main()`**, change:
```python
history = [_banner_buf.getvalue()]
```
to:
```python
history = [(None, _banner_buf.getvalue())]   # (renderable, rendered_str)
```

**Change `_add()`** (line 204):
```python
# Before
def _add(text, style=THEME["dim"]): history.append(_render(Text(text, style=style)))

# After
def _add(text, style=THEME["dim"]):
    r = Text(text, style=style)
    history.append((r, _render(r)))
```

**Update every `history.append(_render(...))` call** to store the renderable too:
```python
# Before (line 236)
history.append(_render(Text.assemble(("  ❯ ", f"bold {THEME['blue']}"), user_input)))

# After
r = Text.assemble(("  ❯ ", f"bold {THEME['blue']}"), user_input)
history.append((r, _render(r)))

# Before (line 256)
history.append(_render(Markdown(result)))

# After
r = Markdown(result)
history.append((r, _render(r)))

# In _on_trace (line 145)
# Before
history.append(_render(Panel(f"[dim]{content}[/dim]", title=label, border_style="dim")))

# After
r = Panel(f"[dim]{content}[/dim]", title=label, border_style="dim")
history.append((r, _render(r)))
```

**Update `_draw()`** to use the string part:
```python
# Before (line 191)
for item in new_items: sys.stdout.write(item if item.endswith("\n") else item + "\n")

# After
for (_, rendered) in new_items:
    sys.stdout.write(rendered if rendered.endswith("\n") else rendered + "\n")
```

**Update `_handle_resize()`** to re-render at new width:
```python
def _handle_resize(signum=None, frame=None):
    sys.stdout.write("\033[2J\033[H\033[s")
    sys.stdout.flush()
    # Re-render all stored renderables at new width
    for i, (renderable, _) in enumerate(history):
        if renderable is not None:
            history[i] = (renderable, _render(renderable))
        # banner (renderable=None) stays as-is — it's just text
    _drawn_count[0] = 0
    _draw()

signal.signal(signal.SIGWINCH, _handle_resize)
```

---

### Step 3 — Fix startup anchor

Change line 212:
```python
# Before
sys.stdout.write("\n\n\033[s"); _draw(); tty.setcbreak(fd)

# After
sys.stdout.write("\033[2J\033[H\033[s"); _draw(); tty.setcbreak(fd)
```

Clear the screen fully at startup so the anchor is at a known position (top-left), not floating somewhere mid-scroll.

---

## Summary of Changes

| File | Line | Change |
|------|------|--------|
| `cli/main.py` | 212 | Replace `\n\n\033[s` with `\033[2J\033[H\033[s` (clean startup) |
| `cli/main.py` | ~213 | Add `signal.signal(signal.SIGWINCH, _handle_resize)` |
| `cli/main.py` | ~213 | Add `_handle_resize()` function |
| `cli/main.py` | 127 | Change `history` to store `(renderable, str)` tuples |
| `cli/main.py` | 145 | Update `_on_trace` to store tuple |
| `cli/main.py` | 191 | Update `_draw()` to unpack tuples |
| `cli/main.py` | 204 | Update `_add()` to store tuple |
| `cli/main.py` | 236 | Update user input append to store tuple |
| `cli/main.py` | 256 | Update result append to store tuple |

---

## What This Fixes

- Terminal resize immediately redraws the full UI at the new width
- Separator lines, status bar, and input area always fill the full terminal width
- History content reflows to the new width (Step 2 required for this)
- Cursor anchor is stable across resizes

## What This Doesn't Fix

- The banner (`_banner_buf.getvalue()`) is a pre-rendered string with no stored renderable — it won't reflow. Acceptable since it only shows once at startup.
- Very rapid resize events will trigger multiple full redraws — fine in practice, could add a debounce if needed.
