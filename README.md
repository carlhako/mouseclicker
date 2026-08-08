# Mouse Clicker

A small cross-platform Python GUI that automates mouse clicking. Useful for
grinding clicks in games, testing UIs, or any task that needs repeated
left-clicks at a fixed position.

```
┌────────────────────────────────────┐
│ [✓] Always on top                  │
├────────────────────────────────────┤
│ Mouse Position                     │
│   X: [640]  Y: [360]               │
│   [ Set Mouse Position (5s) ]      │
│   [ Save Position ]                │
├────────────────────────────────────┤
│ Click Speed                        │
│   Clicks per second (0.1 – 10):    │
│   [2.0]                            │
├────────────────────────────────────┤
│ Delay                              │
│   [ ] Enable delay between clicks  │
│   Delay (seconds): [1.0]           │
│   [ ] Repeat delay periodically    │
│   Repeat every (seconds): [5]      │
├────────────────────────────────────┤
│   [▶  Start]      [■  Stop]        │
├────────────────────────────────────┤
│ Ready.                             │
└────────────────────────────────────┘
```

## Quick start

### Windows 11 / 10

```cmd
git clone https://github.com/carlhako/mouseclicker.git
cd mouseclicker
pip install -r requirements.txt
pythonw mouseclicker.pyw
```

Double-clicking `mouseclicker.pyw` from Explorer also works — no console
window pops up.

### macOS

```bash
git clone https://github.com/carlhako/mouseclicker.git
cd mouseclicker
pip install -r requirements.txt
python mouseclicker.py
```

> First time only: open **System Settings → Privacy & Security →
> Accessibility** and enable your Terminal (or Python) so it can control the
> mouse. Without this, `pyautogui.click()` is silently ignored.

### Linux (X11)

```bash
git clone https://github.com/carlhako/mouseclicker.git
cd mouseclicker
pip install -r requirements.txt
python mouseclicker.py
```

If `tkinter` is missing:

```bash
# Debian / Ubuntu
sudo apt install python3-tk

# Fedora
sudo dnf install python3-tkinter

# Arch
sudo pacman -S tk
```

Wayland is **not** supported — log into an X11 session first.

---

## Features

- **Set Mouse Position** — starts a 5-second countdown so you can position
  the mouse where you want; the X / Y are then captured into editable fields.
- **Save Position** — persists X, Y and click speed to
  `mouseclicker_config.json` (auto-reloaded on next launch).
- **Click speed** — accepts `0.1` – `10` clicks per second (`0.1` = 1 click
  every 10 s, `5` = 5 clicks per second).
- **Delay** — optional. When **Enable delay between clicks** is checked, an
  extra pause of *Delay (seconds)* is inserted between every click (on top
  of the 1/cps interval). So at 2 cps with a 1 s delay, the effective
  cadence is one click every 1.5 s.
- **Repeat delay** — optional, layered on top of Delay. When **Repeat delay
  periodically** is checked, the clicking pauses for the configured delay
  once every *Repeat every (seconds)*. With *Delay* = 1 s and *Repeat every*
  = 5 s, the loop clicks normally for 5 s, then pauses 1 s, then repeats.
- **Start** — a second 5-second countdown (cancellable with **Stop**) then
  moves the mouse to the saved position and clicks the primary mouse button
  in an infinite loop at the configured rate.
- **Auto safety stop** — the loop stops automatically if the mouse is moved
  more than **50 px** from the target position.
- **Stop** — cancels either the start countdown or the click loop.
- **Always on top** — keeps the window visible while you interact with
  other apps.

## Requirements

| | |
|---|---|
| Python | 3.8 or newer |
| OS | Windows 10 / 11, macOS 11+, or Linux with X11 |
| Dependencies | [`pyautogui`](https://pypi.org/project/PyAutoGUI/) (installed via `requirements.txt`) |
| Disk | < 1 MB |

## Installation

```bash
git clone https://github.com/carlhako/mouseclicker.git
cd mouseclicker
pip install -r requirements.txt
```

If you don't want to use `git`, click **Code → Download ZIP** on GitHub,
unzip it, then `pip install -r requirements.txt` from inside the folder.

A virtual environment is recommended:

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## Usage

### Typical workflow

1. Click **Set Mouse Position (5s)** and move the mouse to where you want
   to click within 5 seconds.
2. Adjust the **Click Speed** if needed (0.1 – 10 clicks/sec).
3. Click **▶ Start** — you have another 5 seconds to abort with **■ Stop**.
4. While clicking, you can abort at any time by either:
   - pressing **■ Stop**, or
   - moving the mouse more than 50 px away from the target.

The X / Y fields are editable, so you can also paste a position directly
without using the capture button.

### Controls reference

| Control | What it does |
|---|---|
| `X`, `Y` (entry) | Target screen coordinates. Editable. |
| **Set Mouse Position (5s)** | 5 s countdown, then captures the current cursor position into X/Y. |
| **Save Position** | Writes X, Y and click speed to `mouseclicker_config.json`. |
| Click speed (entry) | Clicks per second; accepts `0.1` – `10`. |
| **Enable delay between clicks** (checkbox) | Adds *Delay* seconds to every click. |
| Delay (entry) | Seconds of extra pause between every click; accepts `0` – `3600`. |
| **Repeat delay periodically** (checkbox) | Once every *Repeat every* seconds, the clicking pauses for *Delay* seconds. |
| Repeat every (entry) | Period (seconds) of the periodic pause; accepts `0.1` – `3600`. |
| **▶ Start** | 5 s cancellable countdown, then clicks in an infinite loop. |
| **■ Stop** | Cancels the start countdown or stops the click loop. |
| Always on top (checkbox) | Keeps the window above other windows. |

### Editing the config file manually

`mouseclicker_config.json` is created next to the script:

```json
{
  "x": 640,
  "y": 360,
  "cps": 2.0,
  "delay_enabled": false,
  "delay": 1.0,
  "repeat_enabled": false,
  "repeat": 5.0
}
```

The `delay_enabled` / `delay` / `repeat_enabled` / `repeat` keys are
optional. Older config files (with only `x` / `y` / `cps`) still load
cleanly — the new fields default to off / `1.0` / off / `5.0`.

You can edit it in any text editor while the app is closed; it will be
reloaded on the next launch.

## Platform notes

- **Windows 11 / 10** — works out of the box. The script enables
  per-monitor DPI awareness (`SetProcessDpiAwareness(2)`) and sets an
  `AppUserModelID` so the GUI renders crisply at 125%/150% display scaling
  and groups correctly under one taskbar entry. The modern `vista` ttk theme
  is selected automatically. Double-click `mouseclicker.pyw` to launch
  without a console window.
- **macOS** — you may need to grant **Accessibility** and / or **Input
  Monitoring** permissions to your terminal / Python for mouse control to
  work. Some apps also need **Automation** permission for the controlling
  app.
- **Linux** — requires an X11 session (Wayland is not supported by
  `pyautogui`). On Wayland, `pyautogui.position()` will throw or return
  stale values; either log out and choose an X11 session, or run inside
  `XWayland` (most Wayland desktops provide this automatically for X11
  apps).

## Troubleshooting

**`ModuleNotFoundError: No module named 'pyautogui'`**
You skipped the install step. Run `pip install -r requirements.txt` from
inside the project folder.

**`ModuleNotFoundError: No module named 'tkinter'` (Linux)**
Your distro's Python is split. Install the `tk` package — see the
Linux section above.

**Clicks land in the wrong place / coordinates look doubled (Windows)**
The app is being launched by a process that does *not* have per-monitor
DPI awareness, and Windows is virtualising coordinates. Use
`mouseclicker.pyw` (or run via `pythonw`) so the DPI-awareness call inside
the script takes effect before Tk creates its window.

**Clicks don't register at all (macOS)**
You haven't granted Accessibility permission to the app that launched
Python. See the macOS section above. After granting it, fully quit and
re-open the terminal / launcher app.

**`pyautogui.FailSafeException`**
Shouldn't happen — `FAILSAFE` is disabled. If you see it, you are running
an older fork of the script; pull the latest version from `main`.

**Antivirus flags `pyautogui` (Windows)**
Some AVs flag mouse / keyboard automation libraries. Add an exception for
the project folder, or run from a venv inside the folder.

**`ctypes.windll.shcore.SetProcessDpiAwareness` fails on very old Windows**
Harmless — the script falls back to `SetProcessDPIAware` (Win 8.0) and
then to no DPI awareness. The GUI may look slightly soft at high display
scaling, but it will still work.

## Running from source vs. packaging

The repo is intentionally a single-script project. If you want a real
`.exe` on Windows, install [`pyinstaller`](https://pyinstaller.org/) and run:

```cmd
pip install pyinstaller
pyinstaller --noconsole --onefile --name MouseClicker mouseclicker.pyw
```

The result will be in `dist\MouseClicker.exe`.

## License

MIT — see [LICENSE](LICENSE).
