#!/usr/bin/env python3
"""
Mouse Clicker - A simple GUI auto-clicker.

Features:
  * "Set Mouse Position" with a 5-second countdown so you can move the mouse
    where you want it before the position is captured.
  * X/Y coordinates are editable in the GUI.
  * "Save Position" persists X, Y, click-speed and the delay settings to a
    JSON config file that is reloaded automatically on startup.
  * Click speed: 0.1 - 10 clicks per second (0.1 = 1 click every 10 s).
  * Delay feature: optionally insert a configurable pause between every
    click, and (separately) optionally repeat that pause once every N
    seconds. Both sub-features are independent of each other and of the
    normal CPS rate.
  * "Start" runs another 5-second countdown (cancellable) then clicks the
    primary mouse button in an infinite loop at the saved position.
  * The loop auto-stops if the mouse is moved more than 50 px from the target.
    The auto-stop also fires during the delay / repeat pauses.
  * "Stop" halts both the start countdown and the click loop.
  * "Always on top" checkbox keeps the window above other windows.
  * The 5-second countdown is shown inside the main GUI window (no popup).
"""

import json
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

# --- Windows 11 compatibility setup ---
# These calls MUST run before tk.Tk() is instantiated so that Tk creates
# its window at the correct (per-monitor) DPI and shows up under the right
# AppUserModelID in the taskbar.
if sys.platform == "win32":
    try:
        import ctypes  # noqa: E402  (intentional: only needed on Windows)

        # Per-monitor DPI awareness v2 (Windows 10 1703+ / Windows 11) -
        # required so the GUI renders crisply at 125%/150% scaling.
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except (AttributeError, OSError):
                # Windows 8.0 fallback
                ctypes.windll.user32.SetProcessDPIAware()

        # AppUserModelID so the app groups/pins correctly in the Win11 taskbar
        # even though it is launched as a plain script (no manifest).
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "carlhako.mouseclicker.1"
            )
        except (AttributeError, OSError):
            pass
    except Exception:
        # Never let platform setup crash the GUI
        pass

try:
    import pyautogui

    pyautogui.FAILSAFE = False  # we have our own stop mechanism
    pyautogui.PAUSE = 0  # we drive timing ourselves via time.sleep()
except ImportError:
    pyautogui = None

CONFIG_FILE = "mouseclicker_config.json"
COUNTDOWN_SECONDS = 5
STOP_DISTANCE = 50  # pixels - mouse movement threshold
POLL_INTERVAL = 0.02  # responsiveness slice for stop checking


class MouseClicker:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Mouse Clicker")
        self.root.geometry("380x560")
        self.root.minsize(380, 480)
        self.root.resizable(True, True)

        # --- state ---
        self.click_x = tk.IntVar(value=0)
        self.click_y = tk.IntVar(value=0)
        self.cps = tk.DoubleVar(value=1.0)
        self.always_on_top = tk.BooleanVar(value=False)
        self.click_count_var = tk.StringVar(value="Clicks: 0")

        # --- delay feature ---
        # delay_enabled: when True, an extra pause of `delay_value` seconds
        #   is added between every click (on top of the 1/cps interval).
        # repeat_enabled: when True, every `repeat_value` seconds the
        #   clicking pauses for `delay_value` seconds.
        self.delay_enabled = tk.BooleanVar(value=False)
        self.delay_value = tk.DoubleVar(value=1.0)
        self.repeat_enabled = tk.BooleanVar(value=False)
        self.repeat_value = tk.DoubleVar(value=5.0)

        self.busy = False  # True while counting down or clicking
        self.running = False  # True only while actively clicking
        self.stop_requested = False

        self._build_ui()
        self._apply_platform_theme()
        self._load_config()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _apply_platform_theme(self) -> None:
        """Use the native, modern theme on each platform."""
        style = ttk.Style(self.root)
        if sys.platform == "win32":
            # 'vista' is the flat Windows theme that ships with Win10/11.
            if "vista" in style.theme_names():
                style.theme_use("vista")
        elif sys.platform == "darwin":
            if "aqua" in style.theme_names():
                style.theme_use("aqua")
        else:
            # Linux: prefer a clean theme if available
            for name in ("clam", "alt", "default"):
                if name in style.theme_names():
                    style.theme_use(name)
                    break

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        # Always on top
        top = ttk.Frame(self.root, padding=(10, 8, 10, 0))
        top.pack(fill="x")
        ttk.Checkbutton(
            top,
            text="Always on top",
            variable=self.always_on_top,
            command=self._toggle_always_on_top,
        ).pack(anchor="w")

        # Position section
        pos = ttk.LabelFrame(self.root, text="Mouse Position", padding=10)
        pos.pack(fill="x", padx=10, pady=8)
        pos.columnconfigure(1, weight=1)
        pos.columnconfigure(3, weight=1)

        ttk.Label(pos, text="X:").grid(row=0, column=0, sticky="w", padx=(0, 4))
        ttk.Entry(pos, textvariable=self.click_x, width=10).grid(
            row=0, column=1, sticky="w"
        )
        ttk.Label(pos, text="Y:").grid(row=0, column=2, sticky="w", padx=(10, 4))
        ttk.Entry(pos, textvariable=self.click_y, width=10).grid(
            row=0, column=3, sticky="w"
        )

        ttk.Button(
            pos, text="Set Mouse Position (5s)", command=self._start_set_position
        ).grid(row=1, column=0, columnspan=4, sticky="ew", pady=(8, 4))
        ttk.Button(pos, text="Save Position", command=self._save_position).grid(
            row=2, column=0, columnspan=4, sticky="ew"
        )

        # Speed section
        speed = ttk.LabelFrame(self.root, text="Click Speed", padding=10)
        speed.pack(fill="x", padx=10, pady=(0, 8))
        ttk.Label(speed, text="Clicks per second (0.1 – 10):").pack(anchor="w")
        vcmd = (self.root.register(self._validate_cps_input), "%P")
        ttk.Entry(
            speed,
            textvariable=self.cps,
            width=10,
            validate="key",
            validatecommand=vcmd,
        ).pack(anchor="w", pady=(4, 0))

        # Divider between Click Speed and the Delay feature
        ttk.Separator(self.root, orient="horizontal").pack(
            fill="x", padx=10, pady=(0, 8)
        )

        # Delay section
        delay_frame = ttk.LabelFrame(self.root, text="Delay", padding=10)
        delay_frame.pack(fill="x", padx=10, pady=(0, 8))
        ttk.Checkbutton(
            delay_frame,
            text="Enable delay between clicks",
            variable=self.delay_enabled,
        ).pack(anchor="w")

        delay_row = ttk.Frame(delay_frame)
        delay_row.pack(fill="x", anchor="w", pady=(4, 0))
        ttk.Label(delay_row, text="Delay (seconds):").pack(side="left")
        delay_vcmd = (self.root.register(self._validate_delay_input), "%P")
        ttk.Entry(
            delay_row,
            textvariable=self.delay_value,
            width=10,
            validate="key",
            validatecommand=delay_vcmd,
        ).pack(side="left", padx=(6, 0))

        ttk.Checkbutton(
            delay_frame,
            text="Repeat delay periodically",
            variable=self.repeat_enabled,
        ).pack(anchor="w", pady=(8, 0))

        repeat_row = ttk.Frame(delay_frame)
        repeat_row.pack(fill="x", anchor="w", pady=(4, 0))
        ttk.Label(repeat_row, text="Repeat every (seconds):").pack(side="left")
        repeat_vcmd = (
            self.root.register(self._validate_repeat_input),
            "%P",
        )
        ttk.Entry(
            repeat_row,
            textvariable=self.repeat_value,
            width=10,
            validate="key",
            validatecommand=repeat_vcmd,
        ).pack(side="left", padx=(6, 0))

        # Statistics section (shows live click count while running)
        stats = ttk.LabelFrame(self.root, text="Statistics", padding=10)
        stats.pack(fill="x", padx=10, pady=(0, 8))
        ttk.Label(
            stats,
            textvariable=self.click_count_var,
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor="w")

        # --- Countdown panel ---
        # Built here but only packed into the layout while a countdown is
        # actually running. Plain tk (not ttk) so we can guarantee the
        # yellow background renders on every theme.
        self._countdown_frame = tk.Frame(
            self.root, bg="#fff3cd", bd=1, relief="solid"
        )
        self._countdown_msg = tk.StringVar(value="")
        tk.Label(
            self._countdown_frame,
            textvariable=self._countdown_msg,
            bg="#fff3cd",
            fg="#000000",
            font=("Segoe UI", 10),
            padx=6,
            pady=2,
        ).pack(fill="x")
        self._countdown_num = tk.StringVar(value=str(COUNTDOWN_SECONDS))
        tk.Label(
            self._countdown_frame,
            textvariable=self._countdown_num,
            bg="#fff3cd",
            fg="#cc6600",
            font=("Segoe UI", 44, "bold"),
            padx=6,
        ).pack(fill="x")

        # Controls (kept as a reference so we can pack the countdown
        # panel *before* this row when the countdown starts).
        ctrl = ttk.Frame(self.root, padding=(10, 0, 10, 0))
        self._ctrl_frame = ctrl
        ctrl.pack(fill="x")
        self.start_btn = ttk.Button(
            ctrl, text="▶  Start", command=self._start_clicking, width=12
        )
        self.start_btn.pack(side="left", padx=(0, 6))
        self.stop_btn = ttk.Button(
            ctrl,
            text="■  Stop",
            command=self._request_stop,
            state="disabled",
            width=12,
        )
        self.stop_btn.pack(side="left")

        # Status bar
        self.status_var = tk.StringVar(value="Ready.")
        bar = ttk.Frame(self.root, padding=(10, 8, 10, 8))
        bar.pack(fill="x", side="bottom")
        ttk.Label(
            bar,
            textvariable=self.status_var,
            relief="sunken",
            padding=6,
            anchor="w",
        ).pack(fill="x")

    # ------------------------------------------------- Always on top
    def _toggle_always_on_top(self) -> None:
        self.root.attributes("-topmost", self.always_on_top.get())

    # ------------------------------------------------- Set position
    def _start_set_position(self) -> None:
        if self.busy:
            return
        if pyautogui is None:
            messagebox.showerror(
                "Missing dependency",
                "pyautogui is not installed.\n\nRun:\n    pip install pyautogui",
            )
            return
        self.busy = True
        self.stop_requested = False
        self._update_buttons()
        threading.Thread(target=self._set_position_countdown, daemon=True).start()

    def _set_position_countdown(self) -> None:
        try:
            self.root.after(0, lambda: self._show_countdown_ui("Move mouse to target"))
            time.sleep(0.15)  # let the countdown panel appear
            for i in range(COUNTDOWN_SECONDS, 0, -1):
                if self.stop_requested:
                    self.root.after(0, self._hide_countdown_ui)
                    self._set_status("Position capture cancelled.")
                    return
                self.root.after(0, lambda n=i: self._update_countdown_ui(n))
                self._set_status(f"Move mouse to position… capturing in {i}s")
                time.sleep(1)
            self.root.after(0, self._hide_countdown_ui)
            x, y = pyautogui.position()
            self.click_x.set(x)
            self.click_y.set(y)
            self._set_status(f"Position captured: ({x}, {y})")
        except Exception as e:
            self.root.after(0, self._hide_countdown_ui)
            self._set_status(f"Error: {e}")
        finally:
            self.busy = False
            self.root.after(0, self._update_buttons)

    # ------------------------------------------------- Save / load
    def _save_position(self) -> None:
        try:
            x = int(self.click_x.get())
            y = int(self.click_y.get())
        except (ValueError, tk.TclError):
            messagebox.showerror("Invalid input", "X and Y must be integers.")
            return
        cps = self._get_cps()
        if cps is None:
            messagebox.showerror(
                "Invalid input", "Click speed must be a number between 0.1 and 10."
            )
            return
        # Persist delay settings too. If the user hasn't enabled them
        # or hasn't entered a valid value yet, we still save the last
        # typed value so their state is restored on next launch.
        delay = self._get_delay_value()
        if delay is None:
            delay = float(self.delay_value.get()) if self.delay_value.get() else 0.0
        repeat = self._get_repeat_value()
        if repeat is None:
            repeat = float(self.repeat_value.get()) if self.repeat_value.get() else 5.0
        config = {
            "x": x,
            "y": y,
            "cps": cps,
            "delay_enabled": bool(self.delay_enabled.get()),
            "delay": delay,
            "repeat_enabled": bool(self.repeat_enabled.get()),
            "repeat": repeat,
        }
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(config, f, indent=2)
            self._set_status(f"Saved position ({x}, {y}) → {CONFIG_FILE}")
        except OSError as e:
            messagebox.showerror("Save failed", str(e))

    def _load_config(self) -> None:
        if not os.path.exists(CONFIG_FILE):
            return
        try:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
            self.click_x.set(int(config.get("x", 0)))
            self.click_y.set(int(config.get("y", 0)))
            cps = float(config.get("cps", 1.0))
            cps = max(0.1, min(10.0, cps))
            self.cps.set(cps)
            # Delay settings are optional in the config so that old
            # config files (written before the Delay feature existed)
            # still load cleanly.
            self.delay_enabled.set(bool(config.get("delay_enabled", False)))
            delay = float(config.get("delay", 1.0))
            delay = max(0.0, min(3600.0, delay))
            self.delay_value.set(delay)
            self.repeat_enabled.set(bool(config.get("repeat_enabled", False)))
            repeat = float(config.get("repeat", 5.0))
            repeat = max(0.1, min(3600.0, repeat))
            self.repeat_value.set(repeat)
            self._set_status(f"Loaded config from {CONFIG_FILE}")
        except (OSError, ValueError, json.JSONDecodeError) as e:
            self._set_status(f"Could not load config: {e}")

    # ------------------------------------------------- Validation
    def _validate_cps_input(self, proposed: str) -> bool:
        # Be permissive while the user is still typing. tkinter's
        # validate="key" fires on every keystroke, so strict checks
        # (e.g. requiring the value to already be in [0.1, 10]) block
        # the user from ever entering values like "0.5" — typing "0"
        # gets rejected, and then they can't continue.
        if proposed == "":
            return True
        # A lone "." is a valid prefix (the user is about to type ".5").
        if proposed == ".":
            return True
        # Only digits and at most one decimal point.
        if any(c not in "0123456789." for c in proposed):
            return False
        if proposed.count(".") > 1:
            return False
        try:
            v = float(proposed)
        except ValueError:
            return False
        # Permit any partial value in [0, 10] so the user can type
        # things like "0", "0.", "0.5" while they are still typing.
        # The final value must still be in [0.1, 10]; that check
        # happens in _get_cps() when Start is pressed.
        return 0.0 <= v <= 10.0

    def _get_cps(self):
        try:
            v = float(self.cps.get())
        except (ValueError, tk.TclError):
            return None
        if not (0.1 <= v <= 10.0):
            return None
        return v

    # --- delay validation / getters ---
    # Permissive key-stroke validator: allow the user to type partial
    # values like "0", "0.", "1.5" without being blocked. The final
    # value is checked in _get_delay_value() when Start is pressed.
    # Allowed range while typing: 0 - 3600 (0 = no extra delay).
    def _validate_delay_input(self, proposed: str) -> bool:
        if proposed == "" or proposed == ".":
            return True
        if any(c not in "0123456789." for c in proposed):
            return False
        if proposed.count(".") > 1:
            return False
        try:
            v = float(proposed)
        except ValueError:
            return False
        return 0.0 <= v <= 3600.0

    def _get_delay_value(self):
        try:
            v = float(self.delay_value.get())
        except (ValueError, tk.TclError):
            return None
        if not (0.0 <= v <= 3600.0):
            return None
        return v

    # --- repeat validation / getters ---
    # Permissive key-stroke validator (see _validate_cps_input for the
    # rationale). Allowed range while typing: 0.1 - 3600 seconds. We
    # require at least 0.1 so the periodic pause can never become a
    # busy-loop if the user types 0.
    def _validate_repeat_input(self, proposed: str) -> bool:
        if proposed == "" or proposed == ".":
            return True
        if any(c not in "0123456789." for c in proposed):
            return False
        if proposed.count(".") > 1:
            return False
        try:
            v = float(proposed)
        except ValueError:
            return False
        return 0.0 <= v <= 3600.0

    def _get_repeat_value(self):
        try:
            v = float(self.repeat_value.get())
        except (ValueError, tk.TclError):
            return None
        if not (0.1 <= v <= 3600.0):
            return None
        return v

    # ------------------------------------------------- Click loop
    def _start_clicking(self) -> None:
        if self.busy:
            return
        if pyautogui is None:
            messagebox.showerror(
                "Missing dependency",
                "pyautogui is not installed.\n\nRun:\n    pip install pyautogui",
            )
            return
        cps = self._get_cps()
        if cps is None:
            messagebox.showerror(
                "Invalid click speed",
                "Click speed must be a number between 0.1 and 10.",
            )
            return
        try:
            x = int(self.click_x.get())
            y = int(self.click_y.get())
        except (ValueError, tk.TclError):
            messagebox.showerror("Invalid position", "X and Y must be integers.")
            return

        # Validate the delay inputs only if the corresponding feature
        # is enabled. The repeat checkbox consumes the same *delay*
        # value, so we need to validate it whenever either feature is
        # on — even if "Enable delay between clicks" is off but
        # "Repeat delay periodically" is on.
        delay = 0.0
        if self.delay_enabled.get() or self.repeat_enabled.get():
            delay = self._get_delay_value()
            if delay is None:
                messagebox.showerror(
                    "Invalid delay",
                    "Delay must be a number between 0 and 3600 seconds.",
                )
                return
        repeat = 0.0
        if self.repeat_enabled.get():
            repeat = self._get_repeat_value()
            if repeat is None:
                messagebox.showerror(
                    "Invalid repeat interval",
                    "Repeat interval must be a number between 0.1 and 3600 "
                    "seconds.",
                )
                return

        self.busy = True
        self.stop_requested = False
        self.click_count_var.set("Clicks: 0")
        self._update_buttons()
        threading.Thread(
            target=self._countdown_then_click,
            args=(x, y, cps, delay, repeat),
            daemon=True,
        ).start()

    def _countdown_then_click(
        self,
        x: int,
        y: int,
        cps: float,
        delay: float = 0.0,
        repeat: float = 0.0,
    ) -> None:
        try:
            # --- 5 s start countdown ---
            self.root.after(
                0,
                lambda: self._show_countdown_ui(
                    "Get ready — press Stop to cancel"
                ),
            )
            time.sleep(0.15)  # let the countdown panel appear
            for i in range(COUNTDOWN_SECONDS, 0, -1):
                if self.stop_requested:
                    self.root.after(0, self._hide_countdown_ui)
                    self._set_status("Start cancelled.")
                    return
                self.root.after(0, lambda n=i: self._update_countdown_ui(n))
                self._set_status(f"Starting in {i}s — press Stop to cancel")
                time.sleep(1)
            if self.stop_requested:
                self.root.after(0, self._hide_countdown_ui)
                self._set_status("Start cancelled.")
                return
            self.root.after(0, self._hide_countdown_ui)

            # --- infinite click loop ---
            self.running = True
            interval = 1.0 / cps
            click_count = 0
            # Snapshot the live "is the delay feature active?" booleans
            # once at the start of the run so the loop doesn't have to
            # re-read Tk variables on every iteration (and so a user
            # toggling the checkbox mid-run doesn't change behavior
            # mid-click in a confusing way).
            delay_on = bool(self.delay_enabled.get())
            repeat_on = bool(self.repeat_enabled.get())
            # The repeat pause is measured from the start of the run
            # (or from the end of the last periodic pause). This makes
            # the timing predictable: "every N seconds, pause once".
            last_repeat_time = time.time()
            self._set_status(
                f"Clicking at ({x}, {y}) @ {cps} cps — "
                f"move mouse >{STOP_DISTANCE}px to stop"
            )

            # Move the cursor to the target with a brief animation so
            # the user can visibly see the mouse jump to the position
            # before clicking starts.
            try:
                pyautogui.moveTo(x, y, duration=0.3)
            except Exception as move_err:
                self._set_status(f"Move error: {move_err}")
                return

            while not self.stop_requested:
                # Move + click FIRST so the cursor is parked on the
                # target before any distance check below. If we
                # checked distance first, the cursor would still be
                # wherever the user last left it (e.g. on the Stop
                # button) and the loop would auto-stop on iteration 1.
                # Splitting moveTo() and click() (instead of just
                # click(x, y)) makes it explicit that the cursor is
                # moved to the target on every iteration.
                try:
                    pyautogui.moveTo(x, y)
                    pyautogui.click()
                    click_count += 1
                    # Update the on-screen counter on the main thread.
                    # The default-argument trick freezes the current
                    # click_count into the lambda — without it, every
                    # queued callback would see the loop's final value.
                    self.root.after(
                        0,
                        lambda c=click_count: self.click_count_var.set(
                            f"Clicks: {c}"
                        ),
                    )
                except Exception as click_err:
                    self._set_status(f"Click error: {click_err}")
                    return

                # Sleep for the normal CPS interval. _interruptible_sleep
                # returns False if the user clicked Stop OR if the
                # mouse drifted too far from the target.
                if not self._interruptible_sleep(interval, x, y, click_count):
                    return

                # Extra pause between every click when the delay
                # feature is on. delay==0 (the feature being on but
                # the value being 0) is treated as a no-op.
                if delay_on and delay > 0 and not self.stop_requested:
                    if not self._interruptible_sleep(delay, x, y, click_count):
                        return

                # Periodic longer pause: every `repeat` seconds, the
                # clicking pauses for `delay` seconds. Measured from
                # the start of the run / end of the last periodic
                # pause, so the timing is "once every N seconds"
                # rather than "N seconds after the last click".
                if repeat_on and repeat > 0 and delay > 0 and not self.stop_requested:
                    if time.time() - last_repeat_time >= repeat:
                        self._set_status(
                            f"Pausing for {delay:g}s (repeat)…"
                        )
                        if not self._interruptible_sleep(
                            delay, x, y, click_count
                        ):
                            return
                        last_repeat_time = time.time()
        except Exception as e:
            self.root.after(0, self._hide_countdown_ui)
            self._set_status(f"Error: {e}")
        finally:
            self.running = False
            self.busy = False
            self.root.after(0, self._update_buttons)

    # ------------------------------------------------- Stop
    def _request_stop(self) -> None:
        if not self.busy:
            return
        self.stop_requested = True
        self._set_status("Stopping…")

    # ------------------------------------------------- Interruptible sleep
    def _interruptible_sleep(
        self, total: float, x: int, y: int, click_count: int
    ) -> bool:
        """Sleep for `total` seconds in small slices.

        On every slice, polls the current mouse position and trips the
        stop condition if the cursor has moved more than STOP_DISTANCE
        pixels from the target — the same auto-stop the main click
        loop uses. This means delay / repeat pauses are also
        cancellable by the user moving the mouse away.

        Returns True if the full sleep completed, False if it was cut
        short (either by Stop being pressed, or by the auto-stop).
        Either way the helper updates the status bar and sets
        `self.stop_requested = True` when it returns False.
        """
        slept = 0.0
        while slept < total and not self.stop_requested:
            slice_t = min(POLL_INTERVAL, total - slept)
            time.sleep(slice_t)
            slept += slice_t
            try:
                cx, cy = pyautogui.position()
                dist = ((cx - x) ** 2 + (cy - y) ** 2) ** 0.5
                if dist > STOP_DISTANCE:
                    self._set_status(
                        f"Stopped — mouse moved {dist:.0f} px "
                        f"from target ({click_count} clicks)"
                    )
                    self.stop_requested = True
                    return False
            except Exception:
                # Position polling is best-effort; never let it kill
                # the click loop on its own.
                pass
        return not self.stop_requested

    # ------------------------------------------------- Helpers
    def _update_buttons(self) -> None:
        if self.busy:
            # Hide the start button entirely so the user can't
            # accidentally re-trigger it. Show only the stop button,
            # expanded to fill the row with prominent text so it's
            # obvious how to cancel.
            self.start_btn.pack_forget()
            self.stop_btn.pack(side="left", fill="x", expand=True)
            self.stop_btn.config(state="normal", text="■  STOP — Cancel clicking")
        else:
            # Restore both buttons in their normal positions.
            self.start_btn.pack(side="left", padx=(0, 6))
            self.start_btn.config(state="normal", text="▶  Start")
            self.stop_btn.pack(side="left")
            self.stop_btn.config(state="disabled", text="■  Stop")

    def _set_status(self, msg: str) -> None:
        self.root.after(0, lambda: self.status_var.set(msg))

    # ------------------------------------------------- In-GUI countdown
    def _show_countdown_ui(self, message: str) -> None:
        """Show the in-GUI countdown panel. Must run on the Tk thread."""
        self._countdown_msg.set(message)
        self._countdown_num.set(str(COUNTDOWN_SECONDS))
        if not self._countdown_frame.winfo_ismapped():
            # Insert above the Start/Stop buttons so it pushes them down
            # and is right where the user is looking.
            self._countdown_frame.pack(
                fill="x", padx=10, pady=(0, 6), before=self._ctrl_frame
            )
            self.root.update_idletasks()

    def _update_countdown_ui(self, n: int) -> None:
        """Update the big countdown number. Main thread only."""
        self._countdown_num.set(str(n))

    def _hide_countdown_ui(self) -> None:
        """Hide the countdown panel. Main thread only."""
        if self._countdown_frame.winfo_ismapped():
            self._countdown_frame.pack_forget()
            self.root.update_idletasks()

    def _on_close(self) -> None:
        if self.busy:
            if not messagebox.askokcancel(
                "Quit", "Clicker is running. Quit anyway?"
            ):
                return
        self.stop_requested = True
        self._save_position()
        self.root.destroy()


def main() -> None:
    if pyautogui is None:
        # Minimal error window so the user can see what's wrong
        root = tk.Tk()
        root.title("Mouse Clicker")
        ttk.Label(
            root,
            text="pyautogui is not installed.\n\nRun:    pip install pyautogui",
            padding=20,
            justify="center",
        ).pack()
        ttk.Button(root, text="OK", command=root.destroy).pack(pady=(0, 12))
        root.mainloop()
        return

    root = tk.Tk()
    MouseClicker(root)
    root.mainloop()


if __name__ == "__main__":
    main()
