import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import json
import os
import shlex
import subprocess
import time
import urllib.request
import urllib.error
import urllib.parse
import io
import winsound

CONFIG_FILE = "floating_config.json"

DEFAULT_CONFIG = {
    "api_url": "http://127.0.0.1:9880/tts",
    "ref_audio_path": "",
    "prompt_text": "",
    "prompt_lang": "zh",
    "text_lang": "zh",
    "text_split_method": "cut5",
    "batch_size": 1,
    "speed_factor": 1.0,
    "opacity": 0.85,
    "gpt_model": "",
    "sovits_model": "",
    "run_mode": "Local", # Or "Cloud"
    "use_ssh_tunnel": True,
    "ssh_host": "",
    "ssh_port": 22,
    "ssh_user": "",
    "ssh_key_path": "",
    "ssh_local_port": 9880,
    "ssh_remote_host": "127.0.0.1",
    "ssh_remote_port": 9880,
    "ssh_extra_args": ""
}

class FloatingTTSApp:
    def __init__(self, root):
        self.root = root
        self.config = self.load_config()
        self.ssh_process = None
        self.ssh_lock = threading.Lock()
        
        # --- Root Window Setup ---
        self.root.overrideredirect(True)  # No borders
        self.root.attributes("-topmost", True)  # Always on top
        self.root.attributes("-alpha", self.config.get("opacity", 0.85))  # Transparency
        self.root.protocol("WM_DELETE_WINDOW", self.close_app)
        
        # Set background color to look sleek
        self.bg_color = "#2b2b2b"
        self.fg_color = "#ffffff"
        self.root.configure(bg=self.bg_color)
        
        # Drag variables
        self._offsetx = 0
        self._offsety = 0
        
        # --- UI Build ---
        self.build_ui()
        
        # Positioning at start (Bottom Right roughly)
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        window_width = 400
        window_height = 80
        x = screen_width - window_width - 50
        y = screen_height - window_height - 100
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.root.minsize(300, 60)

    def close_app(self):
        self.stop_ssh_tunnel()
        self.root.destroy()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    config = DEFAULT_CONFIG.copy()
                    config.update(data)
                    return config
            except Exception as e:
                print(f"Error loading config: {e}")
        return DEFAULT_CONFIG.copy()

    def save_config(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving config: {e}")

    def build_ui(self):
        # A main frame that acts as our draggable border
        self.main_frame = tk.Frame(self.root, bg=self.bg_color, cursor="fleur", bd=1, relief="ridge")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.main_frame.bind("<Button-1>", self.clickwin)
        self.main_frame.bind("<B1-Motion>", self.dragwin)

        # Drag handle / App Title area
        self.title_label = tk.Label(self.main_frame, text="≡ TTS Overlay", bg=self.bg_color, fg="#888888", font=("Segoe UI", 9, "bold"))
        self.title_label.pack(anchor="w", padx=5, pady=(2, 0))
        self.title_label.bind("<Button-1>", self.clickwin)
        self.title_label.bind("<B1-Motion>", self.dragwin)
        
        # Controls frame
        self.ctrl_frame = tk.Frame(self.main_frame, bg=self.bg_color)
        self.ctrl_frame.pack(fill=tk.X, padx=5, pady=(0, 5))

        # Text input
        self.entry_var = tk.StringVar()
        self.entry = tk.Entry(self.ctrl_frame, textvariable=self.entry_var, font=("Segoe UI", 11), bg="#3b3b3b", fg=self.fg_color, insertbackground=self.fg_color, relief="flat")
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4, padx=(0, 5))
        self.entry.bind("<Return>", lambda e: self.on_send())

        # Status Label inside entry or below? We will put a small text status
        self.status_label = tk.Label(self.main_frame, text="Ready", bg=self.bg_color, fg="#55aa55", font=("Segoe UI", 8))
        self.status_label.place(relx=1.0, rely=0.0, anchor="ne", x=-30, y=2)

        # Send button
        self.send_btn = tk.Button(self.ctrl_frame, text="Send", command=self.on_send, bg="#007bff", fg="white", font=("Segoe UI", 10, "bold"), relief="flat", activebackground="#0056b3", activeforeground="white")
        self.send_btn.pack(side=tk.LEFT, ipadx=5)

        # Settings button
        self.settings_btn = tk.Button(self.ctrl_frame, text="⚙", command=self.open_settings, bg="#555555", fg="white", font=("Segoe UI", 10), relief="flat", activebackground="#333333", activeforeground="white")
        self.settings_btn.pack(side=tk.LEFT, padx=(5, 0))

        # Close button
        self.close_btn = tk.Button(self.main_frame, text="×", command=self.close_app, bg=self.bg_color, fg="white", font=("Segoe UI", 10), relief="flat", activebackground="red", bd=0)
        self.close_btn.place(relx=1.0, rely=0.0, anchor="ne", x=0, y=0, width=24, height=24)

    def _to_int(self, value, default):
        try:
            return int(str(value).strip())
        except Exception:
            return default

    def use_ssh_tunnel(self):
        return self.config.get("run_mode") == "Cloud" and bool(self.config.get("use_ssh_tunnel", True))

    def get_effective_api_url(self):
        if self.use_ssh_tunnel():
            local_port = self._to_int(self.config.get("ssh_local_port", 9880), 9880)
            return f"http://127.0.0.1:{local_port}/tts"
        return self.config.get("api_url", "http://127.0.0.1:9880/tts")

    def get_ssh_command(self):
        ssh_host = self.config.get("ssh_host", "").strip()
        ssh_user = self.config.get("ssh_user", "").strip()
        if not ssh_host or not ssh_user:
            raise ValueError("Cloud mode requires SSH Host and SSH User when SSH tunneling is enabled.")

        local_port = self._to_int(self.config.get("ssh_local_port", 9880), 9880)
        remote_port = self._to_int(self.config.get("ssh_remote_port", 9880), 9880)
        ssh_port = self._to_int(self.config.get("ssh_port", 22), 22)
        remote_host = self.config.get("ssh_remote_host", "127.0.0.1").strip() or "127.0.0.1"
        key_path = self.config.get("ssh_key_path", "").strip()
        extra_args = self.config.get("ssh_extra_args", "").strip()

        cmd = [
            "ssh",
            "-N",
            "-o", "ExitOnForwardFailure=yes",
            "-o", "ServerAliveInterval=30",
            "-o", "ServerAliveCountMax=3",
            "-p", str(ssh_port),
            "-L", f"{local_port}:{remote_host}:{remote_port}"
        ]
        if key_path:
            cmd.extend(["-i", key_path])
        if extra_args:
            cmd.extend(shlex.split(extra_args, posix=False))
        cmd.append(f"{ssh_user}@{ssh_host}")
        return cmd

    def ensure_ssh_tunnel(self):
        if not self.use_ssh_tunnel():
            return

        with self.ssh_lock:
            if self.ssh_process and self.ssh_process.poll() is None:
                return

            cmd = self.get_ssh_command()
            startupinfo = None
            creationflags = 0
            if os.name == "nt":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

            self.root.after(0, self.set_status, "Connecting SSH...", "#ffaa00")
            self.ssh_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                startupinfo=startupinfo,
                creationflags=creationflags
            )
            time.sleep(0.8)
            if self.ssh_process.poll() is not None:
                err = self.ssh_process.stderr.read().decode("utf-8", errors="ignore").strip()
                self.ssh_process = None
                raise RuntimeError(err or "SSH tunnel failed to start.")

    def stop_ssh_tunnel(self):
        with self.ssh_lock:
            if not self.ssh_process:
                return
            if self.ssh_process.poll() is None:
                self.ssh_process.terminate()
                try:
                    self.ssh_process.wait(timeout=2)
                except Exception:
                    self.ssh_process.kill()
            self.ssh_process = None

    def clickwin(self, event):
        self._offsetx = event.x
        self._offsety = event.y

    def dragwin(self, event):
        x = self.root.winfo_pointerx() - self._offsetx
        y = self.root.winfo_pointery() - self._offsety
        self.root.geometry(f"+{x}+{y}")

    def on_send(self):
        text = self.entry_var.get().strip()
        if not text:
            return

        # If any mandatory fields are missing
        if not self.config["ref_audio_path"] or not self.config["prompt_text"]:
            messagebox.showwarning("Incomplete Settings", "Please open settings (⚙) and provide Reference Audio Path and Prompt Text.")
            return

        self.set_status("Synthesizing...", "#ffaa00")
        self.entry.config(state="disabled")
        self.send_btn.config(state="disabled")

        # Run in thread
        threading.Thread(target=self.run_tts, args=(text,), daemon=True).start()

    def set_status(self, text, color):
        self.status_label.config(text=text, fg=color)

    def run_tts(self, text):
        try:
            self.ensure_ssh_tunnel()
            req_data = {
                "text": text,
                "text_lang": self.config["text_lang"],
                "ref_audio_path": self.config["ref_audio_path"],
                "prompt_text": self.config["prompt_text"],
                "prompt_lang": self.config["prompt_lang"],
                "text_split_method": self.config.get("text_split_method", "cut5"),
                "batch_size": self.config.get("batch_size", 1),
                "speed_factor": self.config.get("speed_factor", 1.0),
                "media_type": "wav",
                "streaming_mode": False
            }

            data = json.dumps(req_data).encode("utf-8")
            api_url = self.get_effective_api_url()
            
            req = urllib.request.Request(api_url, data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req) as response:
                if response.status == 200:
                    audio_data = response.read()
                    self.root.after(0, self.on_tts_success)
                    
                    # Play the audio in memory synchronously in this background thread
                    # winsound.SND_MEMORY tells winsound to play from ram
                    try:
                        winsound.PlaySound(audio_data, winsound.SND_MEMORY | winsound.SND_NODEFAULT)
                    except Exception as play_e:
                        print(f"PlaySound Error: {play_e}")
                else:
                    self.root.after(0, self.on_tts_err, f"HTTP {response.status}")
        except urllib.error.URLError as e:
            self.root.after(0, self.on_tts_err, f"Connection Failed (API down?)")
        except Exception as e:
            self.root.after(0, self.on_tts_err, str(e))

    def on_tts_success(self):
        self.entry_var.set("") # Clear entry
        self.entry.config(state="normal")
        self.send_btn.config(state="normal")
        self.set_status("Ready", "#55aa55")
        self.entry.focus_set()

    def on_tts_err(self, err_msg):
        self.entry.config(state="normal")
        self.send_btn.config(state="normal")
        self.set_status("Error", "#ff5555")
        # messagebox.showerror("API Error", f"TTS Request Failed:\n{err_msg}")
        print(f"TTS Request Failed: {err_msg}")

    def open_settings(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("TTS Settings")
        dlg.geometry("500x520")
        dlg.configure(bg=self.bg_color)
        dlg.attributes("-topmost", True)
        dlg.transient(self.root)
        dlg.grab_set()

        style = ttk.Style(dlg)
        style.theme_use("clam")
        style.configure("TLabel", background=self.bg_color, foreground=self.fg_color, font=("Segoe UI", 10))
        style.configure("TCombobox", fieldbackground="#333", background="#555", foreground=self.fg_color)
        
        # Base frame for canvas and scrollbar
        base_frame = tk.Frame(dlg, bg=self.bg_color)
        base_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        canvas = tk.Canvas(base_frame, bg=self.bg_color, highlightthickness=0)
        scrollbar = ttk.Scrollbar(base_frame, orient="vertical", command=canvas.yview)
        
        # The frame that will actually hold our widgets
        frame = tk.Frame(canvas, bg=self.bg_color)
        
        # Configure canvas
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Create a window inside the canvas
        canvas_window = canvas.create_window((0, 0), window=frame, anchor="nw")

        # Update scrollregion when frame changes size
        def on_frame_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        frame.bind("<Configure>", on_frame_configure)
        
        # Update canvas window width to match canvas width
        def on_canvas_configure(event):
            canvas.itemconfig(canvas_window, width=event.width)
        canvas.bind("<Configure>", on_canvas_configure)

        # Mouse wheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        # Bind mousewheel to canvas and its children
        def _bind_to_mousewheel(widget):
            widget.bind_all("<MouseWheel>", _on_mousewheel)
            
        def _unbind_from_mousewheel(event):
            dlg.unbind_all("<MouseWheel>")
            
        dlg.bind("<Enter>", lambda e: _bind_to_mousewheel(dlg))
        dlg.bind("<Leave>", _unbind_from_mousewheel)

        def get_model_lists():
            gpt_models = [""]
            sovits_models = [""]
            
            # Search GPT models
            for folder in ["GPT_weights", "GPT_weights_v2", "GPT_weights_v2Pro", "GPT_weights_v2ProPlus", "GPT_weights_v3", "GPT_weights_v4"]:
                if os.path.isdir(folder):
                    for f in os.listdir(folder):
                        if f.endswith(".ckpt"):
                            gpt_models.append(f"{folder}/{f}")
                            
            # Search SoVITS models 
            for folder in ["SoVITS_weights", "SoVITS_weights_v2", "SoVITS_weights_v2Pro", "SoVITS_weights_v2ProPlus", "SoVITS_weights_v3", "SoVITS_weights_v4"]:
                if os.path.isdir(folder):
                    for f in os.listdir(folder):
                        if f.endswith(".pth"):
                            sovits_models.append(f"{folder}/{f}")
                            
            return gpt_models, sovits_models

        gpt_models, sovits_models = get_model_lists()

        # Row builder for mode selection
        def create_mode_row(parent):
            row = tk.Frame(parent, bg=self.bg_color)
            row.pack(fill=tk.X, pady=5)
            tk.Label(row, text="Run Mode:", bg=self.bg_color, fg=self.fg_color, width=15, anchor="e").pack(side=tk.LEFT, padx=(0, 10))
            
            mode_var = tk.StringVar(value=self.config.get("run_mode", "Local"))
            mode_combo = ttk.Combobox(row, textvariable=mode_var, values=["Local", "Cloud"], font=("Segoe UI", 10), state="readonly")
            mode_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
            
            def handle_mode_change(e):
                self.config["run_mode"] = mode_var.get()
                # Re-render or update UI visibility if needed
                update_ui_state()
            
            mode_combo.bind("<<ComboboxSelected>>", handle_mode_change)
            return mode_var

        def create_check_row(parent, label_text, var_name):
            row = tk.Frame(parent, bg=self.bg_color)
            row.pack(fill=tk.X, pady=5)
            tk.Label(row, text=label_text, bg=self.bg_color, fg=self.fg_color, width=15, anchor="e").pack(side=tk.LEFT, padx=(0, 10))
            var = tk.BooleanVar(value=bool(self.config.get(var_name, False)))
            chk = tk.Checkbutton(
                row,
                variable=var,
                bg=self.bg_color,
                fg=self.fg_color,
                activebackground=self.bg_color,
                selectcolor="#3b3b3b",
                highlightthickness=0,
                command=lambda: update_ui_state()
            )
            chk.pack(side=tk.LEFT, anchor="w")
            return row, var

        # Row builder for combobox or entry based on mode
        def create_dynamic_row(parent, label_text, var_name, values, is_file=False):
            row = tk.Frame(parent, bg=self.bg_color)
            row.pack(fill=tk.X, pady=5)
            tk.Label(row, text=label_text, bg=self.bg_color, fg=self.fg_color, width=15, anchor="e").pack(side=tk.LEFT, padx=(0, 10))
            
            var = tk.StringVar(value=str(self.config.get(var_name, "")))
            
            # Use two widgets: one for Local (Combo/Browse) and one for Cloud (Entry)
            local_frame = tk.Frame(row, bg=self.bg_color)
            cloud_frame = tk.Frame(row, bg=self.bg_color)
            
            # Local widgets
            if values: # Model selection
                combo = ttk.Combobox(local_frame, textvariable=var, values=values, font=("Segoe UI", 10), state="readonly")
                combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
            else: # Path entry with browse
                entry = tk.Entry(local_frame, textvariable=var, font=("Segoe UI", 10), bg="#3b3b3b", fg=self.fg_color, insertbackground=self.fg_color, relief="flat")
                entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)
                def browse():
                    p = filedialog.askopenfilename(title="Select Audio File", filetypes=(("WAV files", "*.wav"), ("All files", "*.*")))
                    if p: var.set(p)
                tk.Button(local_frame, text="...", command=browse, bg="#555555", fg="white", relief="flat").pack(side=tk.LEFT, padx=(5, 0))
                
            # Cloud widget (always manual entry)
            cloud_entry = tk.Entry(cloud_frame, textvariable=var, font=("Segoe UI", 10), bg="#3b3b3b", fg=self.fg_color, insertbackground=self.fg_color, relief="flat")
            cloud_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)
            
            def update_visibility():
                if self.config.get("run_mode") == "Local":
                    cloud_frame.pack_forget()
                    local_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
                else:
                    local_frame.pack_forget()
                    cloud_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
                    
            return var, update_visibility

        def create_standard_row(parent, label_text, var_name, show_in_cloud=True, show_in_local=True, is_file=False, browse_title="Select File"):
            row = tk.Frame(parent, bg=self.bg_color)
            row.pack(fill=tk.X, pady=5)
            tk.Label(row, text=label_text, bg=self.bg_color, fg=self.fg_color, width=15, anchor="e").pack(side=tk.LEFT, padx=(0, 10))
            var = tk.StringVar(value=str(self.config.get(var_name, "")))
            entry = tk.Entry(row, textvariable=var, font=("Segoe UI", 10), bg="#3b3b3b", fg=self.fg_color, insertbackground=self.fg_color, relief="flat")
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)
            if is_file:
                def browse():
                    path = filedialog.askopenfilename(title=browse_title, filetypes=(("All files", "*.*"),))
                    if path:
                        var.set(path)
                tk.Button(row, text="...", command=browse, bg="#555555", fg="white", relief="flat").pack(side=tk.LEFT, padx=(5, 0))

            def update_visibility():
                mode = self._vars["run_mode"].get() if "run_mode" in self._vars else self.config.get("run_mode", "Local")
                should_show = (mode == "Cloud" and show_in_cloud) or (mode == "Local" and show_in_local)
                if should_show and not row.winfo_manager():
                    row.pack(fill=tk.X, pady=5)
                elif not should_show and row.winfo_manager():
                    row.pack_forget()

            return row, var, update_visibility

        def create_ssh_row(parent, label_text, var_name, is_file=False):
            row, var, _ = create_standard_row(parent, label_text, var_name, show_in_cloud=True, show_in_local=False, is_file=is_file, browse_title="Select SSH Key")

            def update_visibility():
                mode = self._vars["run_mode"].get() if "run_mode" in self._vars else self.config.get("run_mode", "Local")
                use_tunnel = self._vars["use_ssh_tunnel"].get() if "use_ssh_tunnel" in self._vars else bool(self.config.get("use_ssh_tunnel", True))
                should_show = mode == "Cloud" and use_tunnel
                if should_show and not row.winfo_manager():
                    row.pack(fill=tk.X, pady=5)
                elif not should_show and row.winfo_manager():
                    row.pack_forget()

            return row, var, update_visibility

        self._vars = {}
        self._update_funcs = []
        
        mode_var = create_mode_row(frame)
        self._vars["run_mode"] = mode_var
        
        api_row = tk.Frame(frame, bg=self.bg_color)
        api_row.pack(fill=tk.X, pady=5)
        tk.Label(api_row, text="API URL:", bg=self.bg_color, fg=self.fg_color, width=15, anchor="e").pack(side=tk.LEFT, padx=(0, 10))
        self._vars["api_url"] = tk.StringVar(value=self.config.get("api_url", "http://127.0.0.1:9880/tts"))
        tk.Entry(api_row, textvariable=self._vars["api_url"], font=("Segoe UI", 10), bg="#3b3b3b", fg=self.fg_color, insertbackground=self.fg_color, relief="flat").pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)
        def update_api_row():
            mode = self._vars["run_mode"].get()
            use_tunnel = self._vars["use_ssh_tunnel"].get() if "use_ssh_tunnel" in self._vars else bool(self.config.get("use_ssh_tunnel", True))
            should_show = mode == "Local" or (mode == "Cloud" and not use_tunnel)
            if should_show and not api_row.winfo_manager():
                api_row.pack(fill=tk.X, pady=5)
            elif not should_show and api_row.winfo_manager():
                api_row.pack_forget()
        self._update_funcs.append(update_api_row)

        ssh_toggle_row, ssh_toggle_var = create_check_row(frame, "Use SSH Tunnel:", "use_ssh_tunnel")
        self._vars["use_ssh_tunnel"] = ssh_toggle_var
        def update_ssh_toggle():
            mode = self._vars["run_mode"].get()
            if mode == "Cloud" and not ssh_toggle_row.winfo_manager():
                ssh_toggle_row.pack(fill=tk.X, pady=5)
            elif mode != "Cloud" and ssh_toggle_row.winfo_manager():
                ssh_toggle_row.pack_forget()
        self._update_funcs.append(update_ssh_toggle)

        v_gpt, u_gpt = create_dynamic_row(frame, "GPT Model:", "gpt_model", gpt_models)
        self._vars["gpt_model"] = v_gpt
        self._update_funcs.append(u_gpt)
        
        v_sov, u_sov = create_dynamic_row(frame, "SoVITS Model:", "sovits_model", sovits_models)
        self._vars["sovits_model"] = v_sov
        self._update_funcs.append(u_sov)
        
        v_ref, u_ref = create_dynamic_row(frame, "Ref Audio Path:", "ref_audio_path", None, is_file=True)
        self._vars["ref_audio_path"] = v_ref
        self._update_funcs.append(u_ref)

        _, self._vars["prompt_text"], u_prompt = create_standard_row(frame, "Prompt Text:", "prompt_text")
        self._update_funcs.append(u_prompt)
        _, self._vars["prompt_lang"], u_prompt_lang = create_standard_row(frame, "Prompt Lang:", "prompt_lang")
        self._update_funcs.append(u_prompt_lang)
        _, self._vars["text_lang"], u_text_lang = create_standard_row(frame, "Target Lang:", "text_lang")
        self._update_funcs.append(u_text_lang)
        _, self._vars["opacity"], u_opacity = create_standard_row(frame, "Window Opacity:", "opacity")
        self._update_funcs.append(u_opacity)
        _, self._vars["speed_factor"], u_speed = create_standard_row(frame, "Speed:", "speed_factor")
        self._update_funcs.append(u_speed)
        _, self._vars["text_split_method"], u_split = create_standard_row(frame, "Split Method:", "text_split_method")
        self._update_funcs.append(u_split)

        _, self._vars["ssh_host"], u_ssh_host = create_ssh_row(frame, "SSH Host:", "ssh_host")
        self._update_funcs.append(u_ssh_host)
        _, self._vars["ssh_port"], u_ssh_port = create_ssh_row(frame, "SSH Port:", "ssh_port")
        self._update_funcs.append(u_ssh_port)
        _, self._vars["ssh_user"], u_ssh_user = create_ssh_row(frame, "SSH User:", "ssh_user")
        self._update_funcs.append(u_ssh_user)
        _, self._vars["ssh_key_path"], u_ssh_key = create_ssh_row(frame, "SSH Key:", "ssh_key_path", is_file=True)
        self._update_funcs.append(u_ssh_key)
        _, self._vars["ssh_local_port"], u_local_port = create_ssh_row(frame, "Local Port:", "ssh_local_port")
        self._update_funcs.append(u_local_port)
        _, self._vars["ssh_remote_host"], u_remote_host = create_ssh_row(frame, "Remote Host:", "ssh_remote_host")
        self._update_funcs.append(u_remote_host)
        _, self._vars["ssh_remote_port"], u_remote_port = create_ssh_row(frame, "Remote Port:", "ssh_remote_port")
        self._update_funcs.append(u_remote_port)
        _, self._vars["ssh_extra_args"], u_extra_args = create_ssh_row(frame, "SSH Extra Args:", "ssh_extra_args")
        self._update_funcs.append(u_extra_args)

        def update_ui_state():
            for f in self._update_funcs: f()
        
        update_ui_state()

        info_lbl = tk.Label(frame, text="Lang Codes: zh (Chinese), en (English), ja (Japanese), auto\nCloud Mode: remote model and audio paths must be paths on the cloud machine.\nUse SSH Tunnel = local text box -> localhost forwarded port -> remote GPT-SoVITS API.", bg=self.bg_color, fg="#aaaaaa", font=("Segoe UI", 8), justify=tk.LEFT)
        info_lbl.pack(pady=5)

        btn_font = ("Segoe UI", 10)
        btn_frame = tk.Frame(frame, bg=self.bg_color)
        btn_frame.pack(fill=tk.X, pady=(15, 0))
        tk.Button(btn_frame, text="Save & Close", command=lambda: self.save_settings(dlg), bg="#007bff", fg="white", font=btn_font, relief="flat").pack(side=tk.RIGHT, ipadx=10)
        tk.Button(btn_frame, text="Cancel", command=dlg.destroy, bg="#555555", fg="white", font=btn_font, relief="flat").pack(side=tk.RIGHT, padx=10, ipadx=10)

    def save_settings(self, dlg):
        new_config = dict(self.config)
        for k, v in self._vars.items():
            raw_val = v.get()
            val = raw_val.strip() if isinstance(raw_val, str) else raw_val
            if k == "use_ssh_tunnel":
                val = bool(raw_val)
            elif k in ["opacity", "speed_factor"]:
                try:
                    val = float(val)
                except Exception:
                    pass
            elif k in ["ssh_port", "ssh_local_port", "ssh_remote_port", "batch_size"]:
                try:
                    val = int(val)
                except Exception:
                    pass

            new_config[k] = val

        gpt_changed = new_config.get("gpt_model") != self.config.get("gpt_model")
        sovits_changed = new_config.get("sovits_model") != self.config.get("sovits_model")
        self.config = new_config

        if self.config.get("run_mode") != "Cloud" or not self.config.get("use_ssh_tunnel", True):
            self.stop_ssh_tunnel()

        self.save_config()
        self.root.attributes("-alpha", self.config.get("opacity", 0.85))

        if gpt_changed:
            threading.Thread(target=self.set_model, args=("set_gpt_weights", "weights_path", self.config.get("gpt_model", "")), daemon=True).start()
        if sovits_changed:
            threading.Thread(target=self.set_model, args=("set_sovits_weights", "weights_path", self.config.get("sovits_model", "")), daemon=True).start()

        dlg.destroy()

    def set_model(self, endpoint, param_name, model_path):
        if not model_path:
            return
        api_url = self.get_effective_api_url()
        base_url = api_url.rsplit('/', 1)[0]
        try:
            url = f"{base_url}/{endpoint}?{param_name}={urllib.parse.quote(model_path)}"
            urllib.request.urlopen(url)
            print(f"Successfully sent {endpoint} -> {model_path}")
        except Exception as e:
            print(f"Error setting model {model_path} via API: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = FloatingTTSApp(root)
    root.mainloop()
