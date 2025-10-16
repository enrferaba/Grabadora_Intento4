"""Tkinter user interface for Transcriptor de FERIA."""
from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path
from typing import Callable, Iterable, List, Mapping, Optional

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
if __package__ in (None, ""):
    if str(PACKAGE_ROOT) not in sys.path:
        sys.path.insert(0, str(PACKAGE_ROOT))

    from transcriptor.config import ConfigManager, PATHS  # type: ignore
    from transcriptor.disclaimer import (  # type: ignore
        DISCLAIMER_TEXT,
        disclaimer_with_signature,
        timestamp,
    )
    from transcriptor.license import (  # type: ignore
        extract_payload,
        license_is_active,
        load_license,
        save_license,
        verify_license,
    )
    from transcriptor.logging_utils import configure_logging  # type: ignore
    from transcriptor.theme import get_theme  # type: ignore
    from transcriptor.transcription import (  # type: ignore
        GrammarCorrector,
        ModelProvider,
        OutputWriter,
        Segment,
        Transcriber,
    )
else:
    from .config import ConfigManager, PATHS
    from .disclaimer import DISCLAIMER_TEXT, disclaimer_with_signature, timestamp
    from .license import extract_payload, license_is_active, load_license, save_license, verify_license
    from .logging_utils import configure_logging
    from .theme import get_theme
    from .transcription import GrammarCorrector, ModelProvider, OutputWriter, Segment, Transcriber

logger = configure_logging()

try:  # pragma: no cover - optional dependency
    from tkinterdnd2 import DND_FILES, TkinterDnD  # type: ignore

    HAS_DND = True
except Exception:  # pragma: no cover
    HAS_DND = False


SUPPORTED_AUDIO = (".mp3", ".wav", ".ogg", ".m4a", ".flac")


class Typewriter:
    def __init__(self, root: tk.Tk, widget: tk.Text, cps: int) -> None:
        self.root = root
        self.widget = widget
        self.cps = max(30, cps)
        self._queue: List[str] = []
        self._after: Optional[str] = None

    def set_speed(self, cps: int) -> None:
        self.cps = max(30, cps)

    def reset(self) -> None:
        self._queue.clear()
        if self._after:
            try:
                self.root.after_cancel(self._after)
            except Exception:
                pass
        self._after = None

    def enqueue(self, text: str) -> None:
        if not text:
            return
        self._queue.append(text)
        if not self._after:
            self._tick()

    def _tick(self) -> None:
        if not self._queue:
            self._after = None
            return
        chunk = self._queue[0]
        char = chunk[0]
        rest = chunk[1:]
        if rest:
            self._queue[0] = rest
        else:
            self._queue.pop(0)
        self.widget.insert(tk.END, char)
        self.widget.see(tk.END)
        delay = max(5, int(1000 / self.cps))
        self._after = self.root.after(delay, self._tick)


class ThemeManager:
    def __init__(self, root: tk.Tk, cfg: ConfigManager) -> None:
        self.root = root
        self.cfg = cfg
        self.style = ttk.Style(root)
        try:
            self.style.theme_use("clam")
        except Exception:
            pass
        self.current = ""
        self._callbacks: List[Callable[[str], None]] = []
        self.apply(cfg.theme())

    def apply(self, theme_name: str) -> None:
        if theme_name == self.current:
            return
        theme = get_theme(theme_name)
        colors = theme.palette
        self.root.configure(bg=colors["bg"])

        self.style.configure("TFrame", background=colors["bg"])
        self.style.configure("TLabel", background=colors["bg"], foreground=colors["text"])
        self.style.configure("Header.TLabel", font=("Segoe UI", 13, "bold"))
        self.style.configure("Hint.TLabel", foreground=colors["text-muted"], background=colors["bg"])

        self.style.configure("TButton", font=("Segoe UI", 11), padding=8, background=colors["surface"], foreground=colors["text"], relief="flat")
        self.style.map(
            "TButton",
            background=[("active", colors["surface-alt"]), ("disabled", colors["surface-alt"])],
            foreground=[("disabled", colors["text-muted"])],
        )
        self.style.configure("Accent.TButton", background=colors["accent"], foreground="#04150f", padding=10, font=("Segoe UI", 12, "bold"))
        self.style.map("Accent.TButton", background=[("active", colors["accent-alt"])] )
        self.style.configure("Danger.TButton", background=colors["danger"], foreground="#ffffff")
        self.style.map("Danger.TButton", background=[("active", "#f87171")])

        self.style.configure("TCombobox", fieldbackground=colors["surface"], background=colors["surface"], foreground=colors["text"])
        self.style.map("TCombobox", fieldbackground=[("readonly", colors["surface"])] )

        self.style.configure("Accent.Horizontal.TProgressbar", troughcolor=colors["surface"], background=colors["accent"], thickness=14)

        self.style.configure(
            "Treeview",
            background=colors["surface"],
            fieldbackground=colors["surface"],
            foreground=colors["text"],
            rowheight=28,
        )
        self.style.map(
            "Treeview",
            background=[("selected", colors["selection"])],
            foreground=[("selected", colors["selection-fg"])],
        )
        self.style.configure(
            "Treeview.Heading",
            background=colors["surface-alt"],
            foreground=colors["text"],
            font=("Segoe UI", 10, "bold"),
        )

        self.current = theme_name
        self.cfg.set_theme(theme_name)
        for callback in list(self._callbacks):
            try:
                callback(theme_name)
            except Exception:
                logger.debug("theme callback failed", exc_info=True)

    def on_change(self, callback: Callable[[str], None]) -> None:
        self._callbacks.append(callback)


class TranscriptorApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Transcriptor de FERIA — faster-whisper")
        self.root.geometry("1120x860")
        self.root.minsize(900, 640)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.report_callback_exception = self._on_exception

        self.cfg = ConfigManager(PATHS.config_file)
        self.theme_manager = ThemeManager(root, self.cfg)

        self.model_provider = ModelProvider(PATHS.models_dir)
        self.corrector = GrammarCorrector("es")
        self.writer = OutputWriter()
        self.typewriter = Typewriter(self.root, tk.Text(), self.cfg.get_cps())  # placeholder, replaced later

        self.queue: List[Path] = []
        self.cancel_event = threading.Event()
        self.transcribing = False
        self.license_secret: Optional[str] = None
        self.license_active = False

        self._build_menu()
        self._build_layout()
        self._load_disclaimer()
        self._load_license_from_config()

        if HAS_DND:
            try:
                self.tree.drop_target_register(DND_FILES)
                self.tree.dnd_bind("<<Drop>>", self._on_drop)
            except Exception:
                pass

    # ------------------------------------------------------------------
    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)

        self.theme_choice = tk.StringVar(value=self.cfg.theme())

        app_menu = tk.Menu(menubar, tearoff=False)
        app_menu.add_command(label="Ver descargo de responsabilidad", command=self._show_disclaimer)
        app_menu.add_separator()
        app_menu.add_command(label="Salir", command=self._on_close)
        menubar.add_cascade(label="Aplicación", menu=app_menu)

        theme_menu = tk.Menu(menubar, tearoff=False)
        theme_menu.add_radiobutton(
            label="Tema oscuro",
            value="dark",
            variable=self.theme_choice,
            command=lambda: self.theme_manager.apply("dark"),
        )
        theme_menu.add_radiobutton(
            label="Tema claro",
            value="light",
            variable=self.theme_choice,
            command=lambda: self.theme_manager.apply("light"),
        )
        menubar.add_cascade(label="Tema", menu=theme_menu)

        license_menu = tk.Menu(menubar, tearoff=False)
        license_menu.add_command(label="Importar licencia…", command=self._import_license)
        license_menu.add_command(label="Guardar licencia actual…", command=self._export_license)
        license_menu.add_separator()
        license_menu.add_command(label="Mostrar detalles", command=self._show_license_info)
        menubar.add_cascade(label="Licencia", menu=license_menu)

        help_menu = tk.Menu(menubar, tearoff=False)
        help_menu.add_command(label="Acerca de", command=self._show_about)
        menubar.add_cascade(label="Ayuda", menu=help_menu)

        self.root.config(menu=menubar)

    # ------------------------------------------------------------------
    def _build_layout(self) -> None:
        container = ttk.Frame(self.root, padding=16)
        container.pack(fill=tk.BOTH, expand=True)

        ttk.Label(container, text="Modelo:").grid(row=0, column=0, sticky="w")
        self.model_var = tk.StringVar(value="large-v3")
        ttk.Combobox(container, textvariable=self.model_var, values=["tiny", "base", "small", "medium", "large-v3"], state="readonly").grid(row=0, column=1, sticky="ew")

        ttk.Label(container, text="Idioma:").grid(row=0, column=2, sticky="w", padx=(12, 0))
        self.lang_var = tk.StringVar(value="Auto")
        ttk.Combobox(container, textvariable=self.lang_var, values=["Auto", "es", "en", "fr", "de", "it", "pt"], state="readonly").grid(row=0, column=3, sticky="ew")

        ttk.Label(container, text="Dispositivo:").grid(row=1, column=0, sticky="w", pady=(8, 4))
        self.device_var = tk.StringVar(value="cuda")
        ttk.Radiobutton(container, text="GPU", variable=self.device_var, value="cuda").grid(row=1, column=1, sticky="w")
        ttk.Radiobutton(container, text="CPU", variable=self.device_var, value="cpu").grid(row=1, column=1, sticky="e")

        self.vad_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(container, text="VAD (silencios)", variable=self.vad_var).grid(row=1, column=3, sticky="e")

        ttk.Separator(container).grid(row=2, column=0, columnspan=4, sticky="ew", pady=10)

        ttk.Label(container, text="Destino:").grid(row=3, column=0, sticky="w")
        self.dest_var = tk.StringVar(value="(Misma carpeta)")
        self.dest_combo = ttk.Combobox(container, textvariable=self.dest_var, state="readonly")
        self.dest_combo.grid(row=3, column=1, sticky="ew", pady=(0, 6))
        self.dest_combo.bind("<<ComboboxSelected>>", lambda *_: self._toggle_open_button())

        dest_btn_frame = ttk.Frame(container)
        dest_btn_frame.grid(row=3, column=2, columnspan=2, sticky="e")
        ttk.Button(dest_btn_frame, text="Añadir carpeta", command=self._add_destination).pack(side=tk.LEFT, padx=4)
        self.open_dest_btn = ttk.Button(dest_btn_frame, text="Abrir carpeta", command=self._open_destination)
        self.open_dest_btn.pack(side=tk.LEFT, padx=4)

        self._refresh_destinations()

        ttk.Separator(container).grid(row=4, column=0, columnspan=4, sticky="ew", pady=10)

        ttk.Label(container, text="Cola de archivos", style="Header.TLabel").grid(row=5, column=0, columnspan=4, sticky="w")
        columns = ("name", "size", "status")
        self.tree = ttk.Treeview(container, columns=columns, show="headings", height=8)
        self.tree.heading("name", text="Nombre")
        self.tree.heading("size", text="Tamaño")
        self.tree.heading("status", text="Estado")
        self.tree.column("name", width=540, anchor="w")
        self.tree.column("size", width=120, anchor="center")
        self.tree.column("status", width=180, anchor="center")
        self.tree.grid(row=6, column=0, columnspan=4, sticky="nsew", pady=6)

        self._configure_tree_tags(self.cfg.theme())

        self.tree.bind("<Button-3>", self._context_menu)
        self.menu = tk.Menu(self.root, tearoff=False)
        self.menu.add_command(label="Eliminar seleccionado", command=self._remove_selected)
        self.menu.add_command(label="Vaciar cola", command=self._clear_queue)

        queue_btns = ttk.Frame(container)
        queue_btns.grid(row=7, column=0, columnspan=4, sticky="ew", pady=4)
        ttk.Button(queue_btns, text="Agregar audios", command=self._pick_files).pack(side=tk.LEFT, padx=4)
        self.process_btn = ttk.Button(queue_btns, text="Procesar cola", command=self._start_queue, style="Accent.TButton", state=tk.DISABLED)
        self.process_btn.pack(side=tk.LEFT, padx=4)

        speed_frame = ttk.Frame(container)
        speed_frame.grid(row=8, column=0, columnspan=4, sticky="ew", pady=(12, 0))
        ttk.Label(speed_frame, text="Velocidad máquina de escribir:", style="Hint.TLabel").pack(side=tk.LEFT)
        self.speed_value = ttk.Label(speed_frame, text="", style="Hint.TLabel")
        self.speed_value.pack(side=tk.LEFT, padx=(8, 12))
        self.speed_var = tk.IntVar(value=self.cfg.get_cps())
        self.speed_scale = tk.Scale(
            speed_frame,
            from_=30,
            to=400,
            orient=tk.HORIZONTAL,
            variable=self.speed_var,
            showvalue=False,
            resolution=10,
            bg=get_theme(self.cfg.theme()).color("bg"),
            fg=get_theme(self.cfg.theme()).color("text"),
            troughcolor=get_theme(self.cfg.theme()).color("surface"),
            highlightthickness=0,
            bd=0,
            sliderrelief="flat",
            activebackground=get_theme(self.cfg.theme()).color("accent"),
        )
        self.speed_scale.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.speed_scale.bind("<B1-Motion>", lambda *_: self._update_speed())
        self.speed_scale.bind("<ButtonRelease-1>", lambda *_: self._update_speed())

        ttk.Separator(container).grid(row=9, column=0, columnspan=4, sticky="ew", pady=10)

        self.time_label = ttk.Label(container, text="Duración estimada: —", style="Hint.TLabel")
        self.time_label.grid(row=10, column=0, columnspan=4, sticky="w")
        self.status_label = ttk.Label(container, text="Estado: listo")
        self.status_label.grid(row=11, column=0, columnspan=4, sticky="w", pady=(2, 6))

        self.progress = ttk.Progressbar(container, mode="determinate", maximum=100, style="Accent.Horizontal.TProgressbar")
        self.progress.grid(row=12, column=0, columnspan=3, sticky="ew", pady=6)
        self.cancel_btn = ttk.Button(container, text="Cancelar", command=self.cancel_event.set, state=tk.DISABLED, style="Danger.TButton")
        self.cancel_btn.grid(row=12, column=3, sticky="e")

        self.output = tk.Text(container, wrap=tk.WORD, font=("Segoe UI", 11))
        self.output.grid(row=13, column=0, columnspan=4, sticky="nsew", pady=(8, 0))

        self._apply_palette(self.cfg.theme())
        self.typewriter = Typewriter(self.root, self.output, self.cfg.get_cps())
        self._update_speed()

        container.rowconfigure(13, weight=1)
        container.columnconfigure(1, weight=1)
        container.columnconfigure(3, weight=1)

        footer = ttk.Frame(self.root, padding=(16, 8))
        footer.pack(fill=tk.X)
        self.save_btn = ttk.Button(footer, text="Guardar TXT", command=self._save_text, state=tk.DISABLED)
        self.save_btn.pack(side=tk.LEFT, padx=4)
        self.copy_btn = ttk.Button(footer, text="Copiar", command=self._copy_text, state=tk.DISABLED)
        self.copy_btn.pack(side=tk.LEFT, padx=4)
        self.license_label = ttk.Label(footer, text="Licencia: no verificada", style="Hint.TLabel")
        self.license_label.pack(side=tk.RIGHT)

        self.theme_manager.on_change(self._apply_palette)

    # ------------------------------------------------------------------
    def _configure_tree_tags(self, theme_name: str) -> None:
        colors = get_theme(theme_name).palette
        self.tree.tag_configure("odd", background=colors["surface"])
        self.tree.tag_configure("even", background=colors["surface-alt"])
        self.tree.tag_configure("ok", foreground=colors["accent"])
        self.tree.tag_configure("err", foreground=colors["danger"])
        self.tree.tag_configure("run", foreground=colors["accent-alt"])

    def _apply_palette(self, theme_name: str) -> None:
        colors = get_theme(theme_name).palette
        self.output.configure(
            bg=colors["surface"],
            fg=colors["text"],
            insertbackground=colors["accent"],
            highlightbackground=colors["outline"],
        )
        self.speed_scale.configure(
            bg=colors["bg"],
            fg=colors["text"],
            troughcolor=colors["surface"],
            activebackground=colors["accent"],
        )
        self._configure_tree_tags(theme_name)
        self.theme_choice.set(theme_name)

    # ------------------------------------------------------------------
    # Menu handlers
    def _show_about(self) -> None:
        messagebox.showinfo("Transcriptor de FERIA", "Transcriptor de FERIA\nMotor faster-whisper optimizado\n© 2024")

    def _show_disclaimer(self) -> None:
        messagebox.showinfo("Descargo de responsabilidad", disclaimer_with_signature(self._license_signature()))

    def _load_disclaimer(self) -> None:
        if not self.cfg.disclaimer_ack():
            if messagebox.askokcancel("Descargo de responsabilidad", DISCLAIMER_TEXT):
                self.cfg.set_disclaimer_ack(timestamp())
            else:
                self.root.after(100, self.root.destroy)

    # ------------------------------------------------------------------
    # License handling
    def _license_signature(self) -> Optional[str]:
        blob = self.cfg.license_blob()
        if blob and isinstance(blob.get("signature"), str):
            return blob["signature"]
        return None

    def _load_license_from_config(self) -> None:
        blob = self.cfg.license_blob()
        if not blob:
            self._deactivate_license(clear_blob=False)
            return

        secret = self.cfg.license_secret()
        if secret and verify_license(blob, secret):
            self._activate_license(blob, secret, inform=False)
        else:
            self._deactivate_license(clear_blob=True)
            if blob:
                def _warn() -> None:
                    if license_is_active(blob):
                        text = "La licencia guardada no se pudo verificar. Reimpórtala e introduce la clave correcta."
                    else:
                        text = "La licencia guardada expiró o es inválida. Solicita una nueva licencia para continuar."
                    messagebox.showwarning("Licencia", text)

                self.root.after(200, _warn)

    def _activate_license(self, blob: dict, secret: str, inform: bool = True) -> bool:
        if not verify_license(blob, secret):
            return False

        payload = extract_payload(blob)
        holder = payload.holder if payload else blob.get("payload", {}).get("holder")
        expires = payload.expires_at if payload else blob.get("payload", {}).get("expires_at")
        signature = blob.get("signature") if isinstance(blob.get("signature"), str) else None

        self.cfg.set_license_blob(blob)
        self.cfg.set_license_secret(secret)
        self.license_secret = secret
        self.license_active = True
        self._update_license_label(True, holder, expires, signature)
        self._update_process_button()

        if inform:
            messagebox.showinfo("Licencia", "Licencia activada correctamente.")
        return True

    def _deactivate_license(self, *, clear_blob: bool = False) -> None:
        if clear_blob:
            self.cfg.set_license_blob(None)
        self.cfg.set_license_secret(None)
        self.license_secret = None
        self.license_active = False
        self._update_license_label(False)
        self._update_process_button()

    def _update_license_label(self, valid: bool, holder: Optional[str] = None, expires: Optional[str] = None, signature: Optional[str] = None) -> None:
        if valid:
            self.license_label.config(text=f"Licencia válida: {holder} (expira {expires})", foreground="green")
        else:
            self.license_label.config(text="Licencia: no verificada", foreground="red")
        if signature:
            self.license_label.config(text=self.license_label.cget("text") + f" — {signature[:10]}…")

    def _import_license(self) -> None:
        path = filedialog.askopenfilename(title="Selecciona licencia", filetypes=[("JSON", "*.json"), ("Todos", "*.*")])
        if not path:
            return
        try:
            blob = load_license(Path(path))
        except Exception as exc:
            messagebox.showerror("Licencia", f"No se pudo leer el archivo: {exc}")
            return
        secret = simpledialog.askstring("Clave de activación", "Introduce la clave de activación proporcionada:", parent=self.root, show="*")
        if not secret:
            return
        if not self._activate_license(blob, secret):
            messagebox.showerror("Licencia", "No se pudo verificar la licencia. Comprueba la clave o solicita una nueva.")
            self._load_license_from_config()

    def _export_license(self) -> None:
        blob = self.cfg.license_blob()
        if not blob:
            messagebox.showerror("Licencia", "No hay ninguna licencia cargada.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if not path:
            return
        save_license(blob, Path(path))
        messagebox.showinfo("Licencia", "Licencia guardada.")

    def _show_license_info(self) -> None:
        blob = self.cfg.license_blob()
        if not blob:
            messagebox.showinfo("Licencia", "No hay licencia activa.")
            return
        messagebox.showinfo("Licencia", json.dumps(blob, indent=2, ensure_ascii=False))

    # ------------------------------------------------------------------
    # Queue management
    def _context_menu(self, event) -> None:
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def _pick_files(self) -> None:
        filenames = filedialog.askopenfilenames(filetypes=[("Audio", "*.mp3 *.wav *.ogg *.m4a *.flac"), ("Todos", "*.*")])
        self._add_to_queue(Path(name) for name in filenames)

    def _on_drop(self, event) -> None:
        paths = self._parse_drop(event.data)
        self._add_to_queue(paths)

    def _parse_drop(self, data: str) -> Iterable[Path]:
        buffer = ""
        in_brace = False
        for char in data:
            if char == "{":
                in_brace = True
                buffer = ""
                continue
            if char == "}":
                in_brace = False
                if buffer:
                    yield Path(buffer)
                buffer = ""
                continue
            if in_brace:
                buffer += char
            elif char == " ":
                if buffer:
                    yield Path(buffer)
                    buffer = ""
            else:
                buffer += char
        if buffer:
            yield Path(buffer)

    def _add_to_queue(self, candidates: Iterable[Path]) -> None:
        colors = get_theme(self.cfg.theme()).palette
        for path in candidates:
            if path.suffix.lower() not in SUPPORTED_AUDIO:
                continue
            if path in self.queue:
                continue
            if not path.exists():
                continue
            self.queue.append(path)
            tag = "even" if len(self.tree.get_children()) % 2 == 0 else "odd"
            size_mb = f"{path.stat().st_size / (1024*1024):.2f} MB"
            self.tree.insert("", tk.END, values=(path.name, size_mb, "Pendiente"), tags=(tag,))
        self._update_process_button()

    def _remove_selected(self) -> None:
        selection = self.tree.selection()
        names = {self.tree.item(item, "values")[0] for item in selection}
        self.queue = [path for path in self.queue if path.name not in names]
        for item in selection:
            self.tree.delete(item)
        self._update_process_button()

    def _clear_queue(self) -> None:
        self.queue.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._update_process_button()

    def _update_process_button(self) -> None:
        enabled = bool(self.queue and self.license_active)
        self.process_btn.config(state=tk.NORMAL if enabled else tk.DISABLED)
        if not self.license_active:
            self.status_label.config(text="Estado: importe una licencia para comenzar", foreground="red")
        elif not self.transcribing:
            base_color = get_theme(self.cfg.theme()).color("text")
            self.status_label.config(text="Estado: listo", foreground=base_color)

    # ------------------------------------------------------------------
    def _refresh_destinations(self) -> None:
        folders = self.cfg.folders
        base = ["(Misma carpeta)", "(Preguntar cada vez)"]
        values = base + list(folders.keys())
        self.dest_combo.config(values=values)
        if self.dest_var.get() not in values:
            self.dest_var.set("(Misma carpeta)")
        self._toggle_open_button(folders)

    def _add_destination(self) -> None:
        alias = simpledialog.askstring("Nueva carpeta", "Nombre de la asignatura o carpeta:", parent=self.root)
        if not alias:
            return
        alias = alias.strip()
        if not alias:
            messagebox.showerror("Destino", "El nombre no puede estar vacío.")
            return
        if alias in ("(Misma carpeta)", "(Preguntar cada vez)"):
            messagebox.showerror("Destino", "Ese nombre está reservado.")
            return
        existing = self.cfg.folders
        if alias in existing:
            messagebox.showerror("Destino", "Ya existe una carpeta con ese nombre.")
            return
        selected = filedialog.askdirectory(title="Selecciona carpeta de destino")
        if not selected:
            return
        try:
            self.cfg.set_folder(alias, Path(selected))
        except ValueError as exc:
            messagebox.showerror("Destino", str(exc))
            return
        self._refresh_destinations()
        self.dest_var.set(alias)
        messagebox.showinfo("Destino", f"Asignado {alias} → {selected}")

    def _open_destination(self) -> None:
        name = self.dest_var.get()
        folders = self.cfg.folders
        path_str = folders.get(name)
        if not path_str:
            return
        path = Path(path_str)
        if not path.exists():
            messagebox.showerror("Destino", "La carpeta ya no existe.")
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(path))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                import subprocess

                subprocess.Popen(["open", str(path)])
            else:
                import subprocess

                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:
            messagebox.showerror("Destino", str(exc))

    def _toggle_open_button(self, folders: Optional[Mapping[str, str]] = None) -> None:
        name = self.dest_var.get()
        if hasattr(self, "open_dest_btn"):
            available = folders if folders is not None else self.cfg.folders
            self.open_dest_btn.config(state=tk.NORMAL if name in available else tk.DISABLED)

    def _destination_for(self, audio: Path) -> Path:
        choice = self.dest_var.get()
        if choice == "(Misma carpeta)":
            return audio.parent
        if choice == "(Preguntar cada vez)":
            picked = filedialog.askdirectory(title="Elige destino")
            if picked:
                return Path(picked)
            return audio.parent
        path_str = self.cfg.folders.get(choice)
        return Path(path_str) if path_str else audio.parent

    # ------------------------------------------------------------------
    def _update_speed(self) -> None:
        cps = self.speed_var.get()
        self.speed_value.config(text=f"{cps} cps")
        self.typewriter.set_speed(cps)
        self.cfg.set_cps(cps)

    # ------------------------------------------------------------------
    def _start_queue(self) -> None:
        if not self.queue or not self.license_active:
            return
        self.transcribing = True
        self.cancel_event.clear()
        self.process_btn.config(state=tk.DISABLED)
        self.cancel_btn.config(state=tk.NORMAL)
        self.status_label.config(text="Estado: transcribiendo…")
        self.progress.config(value=0)
        self.output.delete("1.0", tk.END)
        self.typewriter.reset()
        self.save_btn.config(state=tk.DISABLED)
        self.copy_btn.config(state=tk.DISABLED)
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self) -> None:
        transcriber = Transcriber(self.model_provider, self.corrector)
        beam_size = 1
        language = None if self.lang_var.get() == "Auto" else self.lang_var.get()
        queue = list(self.queue)

        for audio in queue:
            if self.cancel_event.is_set():
                self._set_status(audio.name, "Cancelado", "err")
                break
            self._set_status(audio.name, "Procesando…", "run")

            try:
                text, segments, elapsed = transcriber.transcribe(
                    audio,
                    model_name=self.model_var.get(),
                    device=self.device_var.get(),
                    language=language,
                    vad_filter=self.vad_var.get(),
                    beam_size=beam_size,
                    cancel_event=self.cancel_event,
                    on_progress=lambda pct, seg, name=audio.name: self._on_progress(name, pct, seg),
                )
            except Exception as exc:
                logger.exception("transcription failed")
                self.root.after(0, messagebox.showerror, "Error", str(exc))
                self._set_status(audio.name, "Error", "err")
                continue

            if self.cancel_event.is_set():
                self._set_status(audio.name, "Cancelado", "err")
                break

            destination = self._destination_for(audio)
            txt_path = destination / f"{audio.stem}.txt"
            srt_path = destination / f"{audio.stem}.srt"
            self.writer.write_txt(txt_path, text)
            self.writer.write_srt(srt_path, segments)

            self._set_status(audio.name, "OK", "ok")
            self.root.after(0, messagebox.showinfo, "Archivos generados", f"TXT: {txt_path}\nSRT: {srt_path}")
            self.root.after(0, self._show_metrics, elapsed, audio, segments)

        self.root.after(0, self._finish_worker)

    def _on_progress(self, name: str, pct: Optional[float], segment: Segment) -> None:
        def update_ui() -> None:
            if pct is not None:
                self.progress.config(value=pct)
                self.status_label.config(text=f"Estado: {name} {pct:.1f}%")
            self.typewriter.enqueue(segment.text)

        self.root.after(0, update_ui)

    def _show_metrics(self, elapsed: float, audio: Path, segments: List[Segment]) -> None:
        audio_length = segments[-1].end if segments else 0.0
        ratio = (elapsed / audio_length) if audio_length else 0.0
        ratio_txt = f" | Ratio: {ratio:.2f}x" if ratio else ""
        self.time_label.config(text=f"Tiempo real: {elapsed:.1f}s | Duración audio: {audio_length:.1f}s{ratio_txt}")
        self.save_btn.config(state=tk.NORMAL)
        self.copy_btn.config(state=tk.NORMAL)

    def _finish_worker(self) -> None:
        self.transcribing = False
        self.cancel_btn.config(state=tk.DISABLED)
        self.progress.config(value=0)
        self.status_label.config(text="Estado: completado", foreground="green")
        self._update_process_button()
        self.queue.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)

    def _set_status(self, name: str, status: str, tag: str) -> None:
        for item in self.tree.get_children():
            values = self.tree.item(item, "values")
            if values and values[0] == name:
                self.tree.set(item, column="status", value=status)
                self.tree.item(item, tags=(tag,))
                break

    # ------------------------------------------------------------------
    def _save_text(self) -> None:
        content = self.output.get("1.0", tk.END).strip()
        if not content:
            messagebox.showerror("Guardar", "No hay contenido para guardar.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("TXT", "*.txt")])
        if not path:
            return
        Path(path).write_text(content, encoding="utf-8")
        messagebox.showinfo("Guardar", "Transcripción guardada.")

    def _copy_text(self) -> None:
        content = self.output.get("1.0", tk.END).strip()
        if not content:
            messagebox.showerror("Copiar", "No hay contenido para copiar.")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        messagebox.showinfo("Copiar", "Copiado al portapapeles.")

    # ------------------------------------------------------------------
    def _on_exception(self, exc, value, tb) -> None:  # type: ignore[override]
        logger.error("Unhandled exception", exc_info=(exc, value, tb))
        messagebox.showerror("Error", "Se produjo un error inesperado. Revisa el log de la aplicación.")

    def _on_close(self) -> None:
        if self.transcribing and not messagebox.askyesno("Cerrar", "Hay una transcripción en curso. ¿Deseas salir igualmente?"):
            return
        self.model_provider.dispose()
        self.root.destroy()


def run() -> None:
    root: tk.Tk
    if HAS_DND:
        root = TkinterDnD.Tk()  # type: ignore[call-arg]
    else:
        root = tk.Tk()
    TranscriptorApp(root)
    root.mainloop()


if __name__ == "__main__":
    run()
