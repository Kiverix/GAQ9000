import os
import sys
import time
import platform
import subprocess
import tkinter as tk
from tkinter import font as tkfont

# optional pygame for sounds
try:
    import pygame
    _HAVE_PYGAME = True
except Exception:
    pygame = None
    _HAVE_PYGAME = False

BANNER = r"""
  ________    _____   ________  ________ 
 /  _____/   /  _  \  \_____  \/   __   \
/   \  ___  /  /_\  \  /  / \  \____    /
\    \_\  \/    |    \/   \_/.  \ /    / 
 \______  /\____|__  /\_____\ \_//____/  v0.1
        \/         \/        \__>         

              GAQ9000 — type "help" to get started
"""

TF2_SERVER = "169.150.249.133:22912"

class GAQ9000(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("GAQ9000 Console")
        self.geometry("900x600")
        self.configure(bg="#0a0f0a")
        self.mono = self._pick_mono_font()
        self.fg = "#00ff66"
        self.bg = "#0a0f0a"
        self.dim = "#00aa44"
        self.err = "#ff5555"

        self.text = tk.Text(
            self,
            bg=self.bg, fg=self.fg, insertbackground=self.fg,
            selectbackground="#004422", selectforeground=self.fg,
            wrap="word", padx=10, pady=10, bd=0, highlightthickness=0,
            font=self.mono
        )
        self.text.pack(fill="both", expand=True)

        # status bar
        self.status_var = tk.StringVar(value="")
        self.status = tk.Label(self, textvariable=self.status_var, anchor="w",
                               fg=self.dim, bg=self.bg, font=("Segoe UI", 10))
        self.status.pack(fill="x", side="bottom")

        self.text.tag_configure("dim", foreground=self.dim)
        self.text.tag_configure("error", foreground=self.err)
        self.text.tag_configure("prompt", foreground=self.fg)
        self.text.tag_configure("banner", foreground=self.fg)
        self.text.tag_configure("readonly", foreground=self.fg)

        self.cwd = os.getcwd()
        self.prompt_str = self._make_prompt()
        self.prompt_index = "1.0"
        self.history = []
        self.history_index = None
        self.commands = self._build_commands()

        self.text.bind("<Return>", self._on_enter)
        self.text.bind("<BackSpace>", self._on_backspace)
        self.text.bind("<Delete>", self._on_delete)
        self.text.bind("<Tab>", self._on_tab_complete)
        self.text.bind("<Up>", self._on_history_up)
        self.text.bind("<Down>", self._on_history_down)
        self.text.bind("<Control-l>", self._clear_screen)
        self.text.bind("<Button-1>", self._on_click)
        self.text.bind("<Key>", self._on_key_any)
        self.text.bind("<<Paste>>", self._on_paste)
        self.text.bind("<Control-v>", self._on_paste)

        self.protocol("WM_DELETE_WINDOW", self._on_window_close)

        self.text.mark_set("insert", "end")
        self._write_banner()
        self._write_prompt()
        self.after(50, lambda: self.text.focus_set())

        # audio
        self._audio_ready = False
        self._snd_open = None
        self._snd_close = None
        self._init_audio()
        self._play_open()

    # ------- audio -------
    def _init_audio(self):
        if not _HAVE_PYGAME:
            self._write("[Audio] pygame not installed; sounds disabled.", "dim")
            return
        try:
            pygame.mixer.pre_init(44100, -16, 2, 512)
            pygame.init()
            pygame.mixer.init()
            base_dir = os.path.dirname(os.path.abspath(__file__))
            res_dir = os.path.join(base_dir, "resources")
            open_path = os.path.join(res_dir, "open.wav")
            close_path = os.path.join(res_dir, "close.wav")
            if os.path.isfile(open_path):
                self._snd_open = pygame.mixer.Sound(open_path)
            else:
                self._write("[Audio] resources/open.wav not found.", "dim")
            if os.path.isfile(close_path):
                self._snd_close = pygame.mixer.Sound(close_path)
            else:
                self._write("[Audio] resources/close.wav not found.", "dim")
            self._audio_ready = True
        except Exception as e:
            self._audio_ready = False
            self._write(f"[Audio init error: {e}]", "error")

    def _play_open(self):
        if self._audio_ready and self._snd_open:
            try:
                self._snd_open.play()
            except Exception as e:
                self._write(f"[Audio play error (open): {e}]", "error")

    def _play_close_and_quit(self):
        delay_ms = 200
        if self._audio_ready and self._snd_close:
            try:
                self._snd_close.play()
                length_ms = int(self._snd_close.get_length() * 1000)
                delay_ms = max(delay_ms, length_ms)
            except Exception as e:
                self._write(f"[Audio play error (close): {e}]", "error")
        self.after(delay_ms + 50, self._shutdown)

    def _shutdown(self):
        try:
            if self._audio_ready:
                pygame.mixer.stop()
                pygame.mixer.quit()
                pygame.quit()
        except Exception:
            pass
        self.destroy()

    # ------- UI helpers -------
    def _pick_mono_font(self):
        candidates = ["Consolas", "Lucida Console", "Courier New", "Menlo", "DejaVu Sans Mono"]
        try:
            available = set(tkfont.families())
        except Exception:
            available = set()
        for name in candidates:
            if name in available:
                return tkfont.Font(family=name, size=12)
        return tkfont.Font(family="Courier", size=12)

    def _make_prompt(self):
        return "> "

    def _write(self, s, *tags, end="\n"):
        self.text.configure(state="normal")
        self.text.insert("end", s, tags)
        if end:
            self.text.insert("end", end, tags)
        self.text.tag_add("readonly", "1.0", "end-1c")
        self.text.see("end")
        self.text.configure(state="normal")

    def _write_no_nl(self, s, *tags):
        self._write(s, *tags, end="")

    def _write_banner(self):
        self._write(BANNER.strip("\n") + "\n", "banner")

    def _write_prompt(self):
        self.prompt_str = self._make_prompt()
        self._write_no_nl(self.prompt_str, "prompt")
        self.prompt_index = self.text.index("insert")

    def _get_current_input(self):
        return self.text.get(self.prompt_index, "end-1c")

    def _replace_current_input(self, new_text):
        self.text.delete(self.prompt_index, "end-1c")
        self.text.insert("end", new_text)

    # ------- input boundary -------
    def _cursor_at_or_after_prompt(self):
        return self.text.compare("insert", ">=", self.prompt_index)

    def _on_click(self, event):
        self.text.after(1, self._snap_cursor)
        return "break"

    def _snap_cursor(self):
        if not self._cursor_at_or_after_prompt():
            self.text.mark_set("insert", "end")

    def _on_key_any(self, event):
        if not self._cursor_at_or_after_prompt():
            self.text.mark_set("insert", "end")
        return None

    def _on_backspace(self, event):
        if self.text.compare("insert", "<=", self.prompt_index):
            self.bell()
            return "break"
        return None

    def _on_delete(self, event):
        if not self._cursor_at_or_after_prompt():
            self.bell()
            return "break"
        return None

    def _on_paste(self, event):
        if not self._cursor_at_or_after_prompt():
            self.text.mark_set("insert", "end")
        try:
            clip = self.clipboard_get()
        except Exception:
            clip = ""
        if clip:
            self.text.insert("insert", clip)
        return "break"

    # ------- history -------
    def _on_history_up(self, event):
        if not self.history:
            self.bell()
            return "break"
        if self.history_index is None:
            self.history_index = len(self.history) - 1
        else:
            self.history_index = max(0, self.history_index - 1)
        self._replace_current_input(self.history[self.history_index])
        return "break"

    def _on_history_down(self, event):
        if self.history_index is None:
            self.bell()
            return "break"
        self.history_index += 1
        if self.history_index >= len(self.history):
            self.history_index = None
            self._replace_current_input("")
        else:
            self._replace_current_input(self.history[self.history_index])
        return "break"

    # ------- tab completion -------
    def _on_tab_complete(self, event):
        fragment = self._get_current_input().strip()
        matches = [c for c in self.commands.keys() if c.startswith(fragment)]
        if len(matches) == 1:
            self._replace_current_input(matches[0] + " ")
            return "break"
        elif len(matches) > 1:
            self._write("\n".join(matches))
            self._write_prompt()
            self._replace_current_input(fragment)
            return "break"
        self.bell()
        return "break"

    # ------- command processing -------
    def _on_enter(self, event):
        cmdline = self._get_current_input()
        self._write("")
        self._execute(cmdline)
        self._write_prompt()
        self.history.append(cmdline.strip())
        self.history = self.history[-200:]
        self.history_index = None
        return "break"

    def _execute(self, line):
        if not line.strip():
            return
        parts = self._split_args(line)
        cmd = parts[0].lower()
        args = parts[1:]
        func = self.commands.get(cmd)
        if func:
            try:
                func(args)
            except Exception as e:
                self._write(f"Error: {e}", "error")
        else:
            self._write(f"'{cmd}' is not recognized.", "error")

    def _split_args(self, line):
        out, buf, q = [], [], None
        for ch in line.strip():
            if q:
                if ch == q:
                    q = None
                else:
                    buf.append(ch)
            else:
                if ch in ("'", '"'):
                    q = ch
                elif ch.isspace():
                    if buf:
                        out.append("".join(buf)); buf = []
                else:
                    buf.append(ch)
        if buf:
            out.append("".join(buf))
        if not out:
            out = [""]
        return out

    def _build_commands(self):
        return {
            "help": self.cmd_help,
            "clear": self.cmd_clear,
            "cls": self.cmd_clear,
            "echo": self.cmd_echo,
            "dir": self.cmd_dir,
            "cd": self.cmd_cd,
            "pwd": self.cmd_pwd,
            "time": self.cmd_time,
            "date": self.cmd_date,
            "ver": self.cmd_ver,
            "exit": self.cmd_exit,
            "comunicate": self.cmd_comunicate,
            "cge.connect": self.cmd_cge_connect,
        }

    # ------- commands -------
    def cmd_help(self, args):
        self._write("Available commands:", "dim")
        self._write("  help              Show this help")
        self._write("  clear | cls       Clear the screen")
        self._write("  echo <text>       Print text")
        # self._write("  dir [path]        List directory")
        # self._write("  cd [path]         Change directory")
        # self._write("  pwd               Show current directory")
        self._write("  time              Show current time")
        self._write("  date              Show current date")
        self._write("  ver               Show version info")
        self._write("  comunicate        Play the greeting sequence")
        self._write("  cge.connect       Close TF2 and connect via Steam with +connect")
        self._write("  exit              Close the console")

    def cmd_clear(self, args=None):
        self._clear_screen()

    def _clear_screen(self, event=None):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self._write_banner()
        return "break"

    def cmd_echo(self, args):
        self._write(" ".join(args))

    def cmd_dir(self, args):
        path = self.cwd if not args else self._resolve_path(args[0])
        if not os.path.isdir(path):
            self._write(f"Not a directory: {path}", "error")
            return
        self._write(f" Directory of {path}", "dim")
        try:
            entries = []
            for name in os.listdir(path):
                full = os.path.join(path, name)
                marker = "<DIR>" if os.path.isdir(full) else "     "
                entries.append((marker, name))
            entries.sort(key=lambda t: (t[0] != "<DIR>", t[1].lower()))
            for marker, name in entries:
                self._write(f"{marker:>5}  {name}")
            self._write(f"   {len(entries)} item(s)", "dim")
        except PermissionError:
            self._write("Access denied.", "error")

    def cmd_cd(self, args):
        if not args:
            self._write(self.cwd)
            return
        target = self._resolve_path(args[0])
        if not os.path.isdir(target):
            self._write("Path not found.", "error")
            return
        try:
            os.chdir(target)
            self.cwd = os.getcwd()
        except PermissionError:
            self._write("Access denied.", "error")

    def cmd_pwd(self, args):
        self._write(self.cwd)

    def cmd_time(self, args):
        self._write(time.strftime("%H:%M:%S"))

    def cmd_date(self, args):
        self._write(time.strftime("%Y-%m-%d"))

    def cmd_ver(self, args):
        py = platform.python_version()
        sysn = platform.system()
        rel = platform.release()
        self._write("GAQ9000 Console v0.1")
        self._write(f"{sysn} {rel}  Python {py}")

    def cmd_exit(self, args):
        self._play_close_and_quit()

    def _on_window_close(self):
        self._play_close_and_quit()

    def cmd_comunicate(self, args):
        sequence = [
            ("oh Hi hello :D", 500),
            ("oh Hi hello :D", 2000),
            ("Very very good morning", 500),
            ("Spave", 200),
            ("Very very good morning", 500),
        ]
        def run_sequence(index=0):
            if index < len(sequence):
                text, delay = sequence[index]
                self._write(text)
                self.after(delay, lambda: run_sequence(index + 1))
        run_sequence()

    # ------- TF2 helpers -------
    def _find_steam_executable(self):
        env_paths = [
            os.environ.get("STEAM_EXE"),
            os.environ.get("STEAM_PATH"),
        ]
        candidates = [p for p in env_paths if p]
        programfiles = os.environ.get("PROGRAMFILES", r"C:\Program Files")
        programfiles86 = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
        candidates += [
            os.path.join(programfiles86, "Steam", "steam.exe"),
            os.path.join(programfiles, "Steam", "steam.exe"),
            r"C:\Steam\steam.exe",
        ]
        for p in candidates:
            if p and os.path.isfile(p):
                return p
        return None

    def _show_tf2_not_installed(self):
        self._write("Steam or TF2 not found. Please install Steam and Team Fortress 2.", "error")

    # your requested launcher implementation
    def _launch_tf2_with_connect(self, connect_command: str) -> None:
        try:
            server = connect_command.split(" ")[1]
            if os.name == "nt":
                steam_path = self._find_steam_executable()
                if steam_path:
                    subprocess.Popen([steam_path, "-applaunch", "440", f"+connect {server}"])
                    self.status_var.set(f"Launching TF2 via Steam to {server}...")
                else:
                    self.status_var.set("Steam not found. Please ensure Steam is installed.")
                    self._show_tf2_not_installed()
            else:
                subprocess.Popen(["steam", "-applaunch", "440", f"+connect {server}"])
                self.status_var.set(f"Launching TF2 via Steam to {server}...")
        except Exception as e:
            self.status_var.set(f"Error launching TF2: {str(e)}")
            self._write(f"Error launching TF2: {e}", "error")

    def cmd_cge_connect(self, args):
        if not sys.platform.startswith("win"):
            self._write("cge.connect is supported on Windows only.", "error")
            return
        try:
            subprocess.run(["taskkill", "/IM", "hl2.exe", "/F"], capture_output=True)
        except Exception as e:
            self._write(f"Warning while closing TF2: {e}", "error")
        self._write(f"Connecting to {TF2_SERVER}...", "dim")
        self._launch_tf2_with_connect(f"connect {TF2_SERVER}")

    # ------- fs helpers -------
    def _resolve_path(self, arg):
        arg = os.path.expanduser(os.path.expandvars(arg))
        if not os.path.isabs(arg):
            arg = os.path.join(self.cwd, arg)
        return os.path.abspath(arg)

if __name__ == "__main__":
    app = GAQ9000()
    app.mainloop()
