# Mouse Clicker

A small cross-platform Python GUI that automates mouse clicking. Useful for
grinding clicks in games, testing UIs, or any task that needs repeated
left-clicks at a fixed position.

![screenshot](screenshot.png)

## Features

- **Set Mouse Position** — starts a 5-second countdown so you can position the
  mouse where you want; the X / Y are then captured into editable fields.
- **Save Position** — persists the X, Y and click speed to
  `mouseclicker_config.json` (auto-reloaded on next launch).
- **Click speed** — accepts `0.1` – `10` clicks per second
  (`0.1` = 1 click every 10 s, `5` = 5 clicks per second).
- **Start** — a second 5-second countdown (cancellable with **Stop**) then
  moves the mouse to the saved position and clicks the primary mouse button in
  an infinite loop at the configured rate.
- **Auto safety stop** — the loop stops automatically if the mouse is moved
  more than **50 px** from the target position.
- **Stop** — cancels either the start countdown or the click loop.
- **Always on top** — keeps the window visible while you interact with other
  apps.

## Installation

Requires Python 3.8+.

```bash
pip install -r requirements.txt
```

## Usage

**Windows 11 / 10** — double-click `mouseclicker.pyw`, or:

```cmd
pythonw mouseclicker.pyw
```

The `.pyw` launcher uses `pythonw.exe`, so no console window pops up.
The plain `mouseclicker.py` still works if you prefer running from a terminal:

```cmd
python mouseclicker.py
```

**macOS / Linux**

```bash
python mouseclicker.py
# or
./mouseclicker.py
```

### Typical workflow

1. Click **Set Mouse Position (5s)** and move the mouse to where you want to
   click within 5 seconds.
2. Adjust the **Click Speed** if needed.
3. Click **▶ Start** — you have another 5 seconds to abort with **■ Stop**.
4. To abort manually while clicking, just move the mouse more than 50 px away
   from the target (or press **■ Stop**).

The X / Y fields are editable, so you can also paste a position directly
without using the capture button.

## Config file

`mouseclicker_config.json` is written next to the script:

```json
{
  "x": 640,
  "y": 360,
  "cps": 2.0
}
```

## Platform notes

- **Windows 11 / 10** — works out of the box. The script enables per-monitor
  DPI awareness (`SetProcessDpiAwareness(2)`) and sets an
  `AppUserModelID` so the GUI renders crisply at 125%/150% display scaling
  and groups correctly under one taskbar entry. The modern `vista` ttk theme
  is selected automatically. Double-click `mouseclicker.pyw` to launch
  without a console window.
- **macOS** — you may need to grant Accessibility / Input Monitoring
  permissions to your terminal / Python for mouse control to work.
- **Linux** — requires an X11 session (Wayland is not supported by `pyautogui`).

## License

MIT
