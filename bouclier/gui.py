"""Interface Graphique de Bureau Native (Tkinter v2.5 Moderne).

100% LOCAL, SANS INTERNET, SANS SERVEUR EXTERNE :
- Onglet 1 : OCR et Caviardage d'images (JPEG, PNG, WEBP)
- Onglet 2 : Anonymiseur de texte & NER
- Onglet 3 : Nettoyeur par lot de metadonnees (PDF, Office, Images)
- Onglet 4 : Analyseur local de messages suspects & liens
"""
from __future__ import annotations

import io
import os
import queue
import sys
import tempfile
import threading
import traceback
from datetime import datetime
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    from tkinter import font as tkfont
except ImportError:
    tk = None
    filedialog = None
    messagebox = None
    ttk = None
    tkfont = None

try:
    from PIL import Image, ImageOps, ImageTk
except Exception:  # Pillow absent, ou ImageTk indisponible : on s'en passe pour l'apercu
    Image = None
    ImageTk = None

from . import __version__, cleaner, ner_engine, ocr_engine, redact, scam, tesseract_setup

THEME = {
    "bg_dark": "#090d16",
    "bg_card": "#131b2e",
    "bg_card_light": "#1c2640",
    "accent": "#10b981",
    "accent_hover": "#059669",
    "text": "#f1f5f9",
    "text_muted": "#94a3b8",
    "border": "#24324f",
    "danger": "#ef4444",
    "warning": "#f59e0b",
    "info": "#38bdf8",
}

APP_DIR = Path(__file__).resolve().parent.parent


def log_error(text: str) -> str:
    """Ecrit une erreur dans bouclier_erreur.log (dossier de l'appli, sinon dossier temporaire)."""
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for folder in (APP_DIR, Path(tempfile.gettempdir())):
        try:
            path = folder / "bouclier_erreur.log"
            with open(path, "a", encoding="utf-8") as f:
                f.write(f"--- {stamp} ---\n{text}\n")
            return str(path)
        except Exception:
            continue
    return ""


def _enable_dpi_awareness() -> None:
    """Evite une interface floue sur les ecrans Windows a haute densite."""
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass


BaseTkClass = tk.Tk if tk is not None else object


class ModernDesktopApp(BaseTkClass):
    """Application de bureau native 100% locale."""

    def __init__(self) -> None:
        if tk is None:
            raise RuntimeError("Tkinter n'est pas disponible dans cet environnement.")
        super().__init__()
        self.report_callback_exception = self._on_callback_error
        self.title(f"Bouclier v{__version__} - Studio d'Anonymisation Local & OCR")
        self.geometry("1100x780")
        self.minsize(860, 600)
        self.configure(bg=THEME["bg_dark"])

        win = sys.platform.startswith("win")
        self.base_font = tkfont.Font(family="Segoe UI" if win else "Helvetica", size=10)
        self.bold_font = tkfont.Font(family="Segoe UI" if win else "Helvetica", size=10, weight="bold")
        self.title_font = tkfont.Font(family="Segoe UI" if win else "Helvetica", size=13, weight="bold")
        self.mono_font = tkfont.Font(family="Consolas" if win else "Courier", size=9)

        self.current_image_path = None
        self.ocr_result_data = None
        self.ocr_result_format = "PNG"
        self._photo = None
        self._preview_source = None
        self._view_is_result = False
        self.manual_boxes = []      # zones tracees a la souris, en pixels de l'image
        self._scale = 1.0
        self._off = (0, 0)
        self._drag_start = None
        self._drag_item = None
        self._busy = False
        self._results_queue = queue.Queue()
        self.cleaner_files = {}

        self._build_header()

        self.status_var = tk.StringVar(value="Prêt. Application 100% autonome et locale sur votre ordinateur.")
        status_bar = tk.Label(
            self, textvariable=self.status_var, bg=THEME["bg_card"], fg=THEME["text_muted"],
            font=self.base_font, anchor="w", padx=12, pady=6, bd=1, relief="solid",
        )
        status_bar.pack(side="bottom", fill="x")

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=(8, 4))

        self._build_ocr_image_tab()
        self._build_text_tab()
        self._build_cleaner_tab()
        self._build_scam_tab()
        self._build_patterns_tab()
        self.after(300, self._refresh_ocr_state)

    # ------------------------------------------------------------------ erreurs
    def _on_callback_error(self, exc, val, tb) -> None:
        """Toute erreur dans un bouton est journalisee et affichee, au lieu d'etre avalee."""
        details = "".join(traceback.format_exception(exc, val, tb))
        path = log_error(details)
        self.status_var.set(f"Erreur : {val}")
        try:
            messagebox.showerror("Bouclier - erreur", f"{val}\n\nDétails enregistrés dans :\n{path}")
        except Exception:
            pass

    # ------------------------------------------------------------------ en-tete
    def _build_header(self) -> None:
        header = tk.Frame(self, bg=THEME["bg_card"], height=56, padx=16, pady=10)
        header.pack(fill="x")
        title_box = tk.Frame(header, bg=THEME["bg_card"])
        title_box.pack(side="left")
        tk.Label(title_box, text="Bouclier v2.5", font=self.title_font, bg=THEME["bg_card"], fg=THEME["text"]).pack(side="left")
        tk.Label(title_box, text="— Anonymisation OCR & Caviardage Local", font=self.base_font, bg=THEME["bg_card"], fg=THEME["text_muted"]).pack(side="left", padx=(6, 0))
        tk.Label(header, text="100% HORS-LIGNE (ZÉRO INTERNET)", font=self.bold_font, bg="#064e3b", fg="#6ee7b7", padx=10, pady=4).pack(side="right")

    # ------------------------------------------------------------------ onglet 1 : images
    def _build_ocr_image_tab(self) -> None:
        tab = tk.Frame(self.notebook, bg=THEME["bg_dark"], padx=10, pady=10)
        self.notebook.add(tab, text="  OCR & Caviardage d'Images  ")
        top_bar = tk.Frame(tab, bg=THEME["bg_card"], padx=12, pady=10, bd=1, relief="solid")
        top_bar.pack(fill="x", pady=(0, 10))

        ttk.Button(top_bar, text="Ouvrir une image (JPEG/PNG)…", command=self.load_image_dialog).pack(side="left", padx=(0, 8))
        self.btn_ocr = ttk.Button(top_bar, text="Lancer l'OCR & Masquage", command=self.run_ocr_and_redact)
        self.btn_ocr.pack(side="left", padx=(0, 8))
        ttk.Button(top_bar, text="Sauvegarder l'image anonymisée", command=self.save_redacted_image).pack(side="left")

        tools = tk.Frame(tab, bg=THEME["bg_card"], padx=12, pady=6, bd=1, relief="solid")
        tools.pack(fill="x", pady=(0, 10))
        tk.Label(tools, text="Tracez des zones à masquer à la souris sur l'image :", bg=THEME["bg_card"], fg=THEME["text_muted"], font=self.base_font).pack(side="left", padx=(0, 10))
        ttk.Button(tools, text="Annuler la dernière zone", command=self.undo_manual_box).pack(side="left", padx=(0, 6))
        ttk.Button(tools, text="Effacer les zones", command=self.clear_manual_boxes).pack(side="left", padx=(0, 6))
        self.btn_toggle_view = ttk.Button(tools, text="Voir l'original / le résultat", command=self.toggle_view)
        self.btn_toggle_view.pack(side="left", padx=(0, 6))
        self.auto_detect_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            tools, text="Détection automatique (OCR)", variable=self.auto_detect_var, bg=THEME["bg_card"], fg=THEME["text"],
            selectcolor=THEME["bg_card_light"], activebackground=THEME["bg_card"], activeforeground=THEME["text"],
        ).pack(side="right")

        self.image_mode_var = tk.StringVar(value="blackout")
        mode_box = tk.Frame(top_bar, bg=THEME["bg_card"])
        mode_box.pack(side="right")
        tk.Label(mode_box, text="Mode :", bg=THEME["bg_card"], fg=THEME["text_muted"], font=self.bold_font).pack(side="left", padx=(0, 6))
        for m_val, m_lbl in [("blackout", "Boîte noire"), ("blur", "Flou"), ("pixelate", "Mosaïque")]:
            tk.Radiobutton(
                mode_box, text=m_lbl, value=m_val, variable=self.image_mode_var,
                bg=THEME["bg_card"], fg=THEME["text"], selectcolor=THEME["bg_card_light"],
                activebackground=THEME["bg_card"], activeforeground=THEME["text"],
            ).pack(side="left", padx=4)

        body = tk.PanedWindow(tab, orient="horizontal", bg=THEME["bg_dark"], bd=0, sashwidth=6)
        body.pack(fill="both", expand=True)

        canvas_frame = tk.Frame(body, bg=THEME["bg_card"], bd=1, relief="solid")
        # NB : tk.PanedWindow n'accepte pas "weight" (option de ttk) -> "stretch"
        body.add(canvas_frame, stretch="always", minsize=300)
        self.img_canvas = tk.Canvas(canvas_frame, bg="#050811", highlightthickness=0, cursor="crosshair")
        self.img_canvas.pack(fill="both", expand=True, padx=6, pady=6)
        self.img_canvas.bind("<Configure>", lambda _e: self._redraw_preview())
        self.img_canvas.bind("<ButtonPress-1>", self._on_press)
        self.img_canvas.bind("<B1-Motion>", self._on_drag)
        self.img_canvas.bind("<ButtonRelease-1>", self._on_release)

        side_panel = tk.Frame(body, bg=THEME["bg_card"], width=320, padx=12, pady=10, bd=1, relief="solid")
        body.add(side_panel, stretch="never", minsize=240)
        tk.Label(side_panel, text="ZONES SENSIBLES DÉTECTÉES", font=self.bold_font, bg=THEME["bg_card"], fg=THEME["accent"]).pack(anchor="w", pady=(0, 6))
        self.ocr_info_lbl = tk.Label(
            side_panel, text="Chargez une image pour exécuter l'OCR local.", font=self.base_font,
            bg=THEME["bg_card"], fg=THEME["text_muted"], justify="left", wraplength=280,
        )
        self.ocr_info_lbl.pack(anchor="w", pady=(0, 10))
        self.boxes_listbox = tk.Listbox(side_panel, bg=THEME["bg_dark"], fg=THEME["text"], font=self.mono_font)
        self.boxes_listbox.pack(fill="both", expand=True, pady=(0, 8))

        self.btn_install_ocr = ttk.Button(side_panel, text="Installer l'OCR automatiquement", command=self.install_ocr)
        self.btn_redetect = ttk.Button(side_panel, text="Re-détecter l'OCR", command=self._refresh_ocr_state)

    # -- etat de l'OCR (detection de Tesseract deja present ou non)
    def _refresh_ocr_state(self) -> None:
        ocr_engine.reset_detection()
        st = ocr_engine.ocr_status()
        self.btn_install_ocr.pack_forget()
        self.btn_redetect.pack_forget()
        if st["usable"] and not st["missing_langs"]:
            self.ocr_info_lbl.config(text=f"✔ OCR Tesseract détecté et testé : il lit bien le texte ({st['cmd']}).", fg=THEME["accent"])
            return
        if st["usable"]:
            txt = f"⚠ OCR fonctionnel, mais langue(s) manquante(s) : {', '.join(st['missing_langs'])}. Cliquez ci-dessous pour les télécharger."
        elif st["installed"]:
            txt = f"✖ Tesseract est présent mais ne fonctionne pas : {st['error']}\nCliquez ci-dessous pour réparer (réinstallation + langues)."
        else:
            txt = "✖ Tesseract (OCR) n'est pas installé. Cliquez ci-dessous pour l'installer automatiquement."
        self.ocr_info_lbl.config(text=txt, fg=THEME["warning"])
        self.btn_install_ocr.pack(anchor="w", pady=(0, 4))
        self.btn_redetect.pack(anchor="w")

    def install_ocr(self) -> None:
        if self._busy:
            return
        if not messagebox.askyesno(
            "Installer l'OCR",
            "Bouclier va télécharger et installer Tesseract (OCR gratuit) ainsi que les langues français/anglais.\n\n"
            "• Une connexion internet est nécessaire UNIQUEMENT pour cette étape.\n"
            "• Windows peut demander une autorisation administrateur : acceptez-la.\n\nContinuer ?",
        ):
            return
        self._busy = True
        self.btn_install_ocr.state(["disabled"])
        lines = []

        def log(msg: str) -> None:
            lines.append(msg)
            self._results_queue.put(("log", msg))

        def work() -> None:
            try:
                self._results_queue.put(("ocr_done", tesseract_setup.ensure_ocr(log)))
            except Exception:
                self._results_queue.put(("err_install", traceback.format_exc()))

        threading.Thread(target=work, daemon=True).start()
        self.status_var.set("Installation de l'OCR en cours… (patientez, cela peut prendre quelques minutes)")
        self.after(150, self._poll_install)

    def _poll_install(self) -> None:
        finished = False
        while True:
            try:
                kind, payload = self._results_queue.get_nowait()
            except queue.Empty:
                break
            if kind == "log":
                self.status_var.set(f"OCR : {payload.strip()}")
            elif kind in ("ocr_done", "err_install"):
                finished = True
                self._busy = False
                self.btn_install_ocr.state(["!disabled"])
                self._refresh_ocr_state()
                if kind == "err_install":
                    log_error(payload)
                    messagebox.showerror("Bouclier", "L'installation de l'OCR a échoué (détails dans bouclier_erreur.log).")
                else:
                    self.status_var.set(payload["message"])
                    (messagebox.showinfo if payload["ok"] else messagebox.showwarning)("Bouclier - OCR", payload["message"])
        if not finished:
            self.after(150, self._poll_install)

    # -- apercu + zones manuelles
    def _show_preview(self, source, is_result: bool = False) -> None:
        self._preview_source = source
        self._view_is_result = is_result
        self._redraw_preview()

    def _redraw_preview(self) -> None:
        canvas = self.img_canvas
        canvas.delete("all")
        src = self._preview_source
        if src is None:
            return
        cw = max(canvas.winfo_width(), 200)
        ch = max(canvas.winfo_height(), 200)
        if Image is None or ImageTk is None:
            canvas.create_text(cw // 2, ch // 2, fill=THEME["text_muted"], font=self.base_font,
                               text="Aperçu indisponible (ImageTk absent)\nLe traitement fonctionne quand même.")
            return
        try:
            img = Image.open(io.BytesIO(src)) if isinstance(src, bytes) else Image.open(src)
            img = ImageOps.exif_transpose(img)  # memes coordonnees que le traitement
            img.load()
            ow, oh = img.size
            self._scale = min((cw - 8) / ow, (ch - 8) / oh, 1.0)
            dw, dh = max(1, int(ow * self._scale)), max(1, int(oh * self._scale))
            shown = img.convert("RGB").resize((dw, dh), Image.Resampling.LANCZOS)
            self._photo = ImageTk.PhotoImage(shown)
            self._off = ((cw - dw) // 2, (ch - dh) // 2)
            canvas.create_image(self._off[0], self._off[1], image=self._photo, anchor="nw")
            if not self._view_is_result:
                for (x0, y0, x1, y1) in self.manual_boxes:
                    canvas.create_rectangle(*self._to_canvas(x0, y0), *self._to_canvas(x1, y1), outline=THEME["danger"], width=2)
        except Exception as e:
            canvas.create_text(cw // 2, ch // 2, fill=THEME["danger"], font=self.base_font, text=f"Aperçu impossible : {e}")

    def _to_canvas(self, x: float, y: float):
        return (x * self._scale + self._off[0], y * self._scale + self._off[1])

    def _to_image(self, cx: float, cy: float):
        return (int((cx - self._off[0]) / self._scale), int((cy - self._off[1]) / self._scale))

    def _on_press(self, event) -> None:
        if self.current_image_path is None:
            return
        if self._view_is_result:      # on dessine toujours sur l'original
            self._show_preview(self.current_image_path)
        self._drag_start = (event.x, event.y)
        self._drag_item = None

    def _on_drag(self, event) -> None:
        if not self._drag_start:
            return
        if self._drag_item is not None:
            self.img_canvas.delete(self._drag_item)
        self._drag_item = self.img_canvas.create_rectangle(
            self._drag_start[0], self._drag_start[1], event.x, event.y, outline=THEME["warning"], width=2, dash=(4, 3))

    def _on_release(self, event) -> None:
        if not self._drag_start:
            return
        start, self._drag_start, self._drag_item = self._drag_start, None, None
        x0, y0 = self._to_image(*start)
        x1, y1 = self._to_image(event.x, event.y)
        x0, x1 = sorted((x0, x1))
        y0, y1 = sorted((y0, y1))
        if x1 - x0 >= 4 and y1 - y0 >= 4:
            self.manual_boxes.append((x0, y0, x1, y1))
            self._refresh_manual_list()
            self.status_var.set(f"{len(self.manual_boxes)} zone(s) manuelle(s). Cliquez sur « Lancer l'OCR & Masquage » pour appliquer.")
        self._redraw_preview()

    def _refresh_manual_list(self) -> None:
        for i in range(self.boxes_listbox.size() - 1, -1, -1):
            if str(self.boxes_listbox.get(i)).startswith("▭"):
                self.boxes_listbox.delete(i)
        for n, (x0, y0, x1, y1) in enumerate(self.manual_boxes, 1):
            self.boxes_listbox.insert("end", f"▭ Zone manuelle {n} ({x1 - x0}×{y1 - y0} px)")

    def undo_manual_box(self) -> None:
        if self.manual_boxes:
            self.manual_boxes.pop()
            self._refresh_manual_list()
            self._redraw_preview()
            self.status_var.set(f"{len(self.manual_boxes)} zone(s) manuelle(s).")

    def clear_manual_boxes(self) -> None:
        self.manual_boxes.clear()
        self._refresh_manual_list()
        self._redraw_preview()
        self.status_var.set("Zones manuelles effacées.")

    def toggle_view(self) -> None:
        if self._view_is_result and self.current_image_path:
            self._show_preview(self.current_image_path)
        elif self.ocr_result_data:
            self._show_preview(self.ocr_result_data, is_result=True)

    def load_image_dialog(self) -> None:
        p = filedialog.askopenfilename(filetypes=[("Images", "*.jpg *.jpeg *.png *.webp *.tif *.tiff"), ("Tous", "*.*")])
        if not p:
            return
        self.current_image_path = Path(p)
        self.ocr_result_data = None
        self.manual_boxes.clear()
        self.boxes_listbox.delete(0, "end")
        self._show_preview(self.current_image_path)
        self.status_var.set(f"Image chargée : {self.current_image_path.name}")

    def run_ocr_and_redact(self) -> None:
        if self._busy:
            return
        if not self.current_image_path:
            messagebox.showinfo("Bouclier", "Ouvrez d'abord une image.")
            return
        auto = self.auto_detect_var.get()
        if not auto and not self.manual_boxes:
            messagebox.showinfo("Bouclier", "Détection automatique désactivée : tracez au moins une zone à la souris.")
            return
        boxes = list(self.manual_boxes)
        self._busy = True
        self.btn_ocr.state(["disabled"])
        self.status_var.set("Analyse OCR en cours… (peut prendre quelques secondes)")
        path, mode = self.current_image_path, self.image_mode_var.get()

        def work() -> None:
            try:
                self._results_queue.put(("ok", ocr_engine.detect_and_redact_image(
                    path, mode=mode, extra_boxes=boxes, auto_detect=auto)))
            except Exception as e:
                self._results_queue.put(("err", (e, traceback.format_exc())))

        threading.Thread(target=work, daemon=True).start()
        self.after(100, self._poll_ocr)

    def _poll_ocr(self) -> None:
        try:
            kind, payload = self._results_queue.get_nowait()
        except queue.Empty:
            self.after(100, self._poll_ocr)
            return
        self._busy = False
        self.btn_ocr.state(["!disabled"])
        if kind == "err":
            exc, tb = payload
            path = log_error(tb)
            self.status_var.set("OCR impossible : voir le message.")
            messagebox.showerror("Bouclier - OCR impossible", f"{exc}\n\n(Détails techniques : {path})")
            return
        res = payload
        self.ocr_result_data = res["data"]
        self.ocr_result_format = res["format"]
        self._show_preview(res["data"], is_result=True)
        engine = {"tesseract": "Tesseract", "manual": "zones manuelles"}.get(res["ocr_engine"], res["ocr_engine"])
        self.status_var.set(f"OCR terminé ({engine}) : {res['entities_count']} donnée(s) masquée(s).")
        if res.get("pages", 1) > 1:
            messagebox.showwarning("Bouclier", f"Ce fichier contient {res['pages']} pages ou images : "
                                   "seule la première est traitée et enregistrée.")
        if self.auto_detect_var.get() and res["ocr_engine"] == "manual":
            self.status_var.set("Texte NON lu : seules vos zones manuelles ont été masquées.")
            messagebox.showwarning("Bouclier - Texte non lu",
                                   "Texte NON lu : l'OCR (Tesseract) n'est pas installé.\n"
                                   "Seules vos zones manuelles ont été masquées. Vérifiez l'image avant de la partager.")
        self.boxes_listbox.delete(0, "end")
        for ent in res["entities"]:
            self.boxes_listbox.insert("end", f"● {ent.get('label', 'Zone')} : {ent.get('value', '')}")

    def save_redacted_image(self) -> None:
        if not self.ocr_result_data:
            messagebox.showinfo("Bouclier", "Lancez d'abord l'anonymisation sur l'image.")
            return
        # le format reel des octets (JPEG ou PNG) determine l'extension, pas celle du fichier source
        ext = ".jpg" if self.ocr_result_format == "JPEG" else ".png"
        p = filedialog.asksaveasfilename(initialfile=f"propre{ext}", defaultextension=ext, filetypes=[("Image", f"*{ext}")])
        if p:
            Path(p).write_bytes(self.ocr_result_data)
            messagebox.showinfo("Succès", f"Image anonymisée enregistrée :\n{p}")

    # ------------------------------------------------------------------ onglet 2 : texte
    def _build_text_tab(self) -> None:
        tab = tk.Frame(self.notebook, bg=THEME["bg_dark"], padx=10, pady=10)
        self.notebook.add(tab, text="  Anonymiseur de Texte & NER  ")
        ctrl_frame = tk.Frame(tab, bg=THEME["bg_card"], padx=12, pady=10, bd=1, relief="solid")
        ctrl_frame.pack(fill="x", pady=(0, 10))

        self.kind_vars = {}
        for k, lbl in redact.LABELS.items():
            var = tk.BooleanVar(value=True)
            self.kind_vars[k] = var
            tk.Checkbutton(
                ctrl_frame, text=lbl, variable=var, bg=THEME["bg_card"], fg=THEME["text"],
                selectcolor=THEME["bg_card_light"], activebackground=THEME["bg_card"], activeforeground=THEME["text"],
            ).pack(side="left", padx=5)

        btn_bar = tk.Frame(tab, bg=THEME["bg_dark"])
        btn_bar.pack(side="bottom", fill="x")
        ttk.Button(btn_bar, text="Détecter & Masquer", command=self.run_text_redact).pack(side="left", padx=(0, 8))
        ttk.Button(btn_bar, text="Copier le résultat", command=self.copy_text_result).pack(side="left")

        panes = tk.PanedWindow(tab, orient="horizontal", bg=THEME["bg_dark"], bd=0, sashwidth=6)
        panes.pack(fill="both", expand=True, pady=(0, 10))
        left_box = tk.Frame(panes, bg=THEME["bg_card"], padx=8, pady=8, bd=1, relief="solid")
        panes.add(left_box, stretch="always")
        self.txt_source = tk.Text(left_box, bg=THEME["bg_dark"], fg=THEME["text"], insertbackground=THEME["text"], font=self.mono_font, wrap="word")
        self.txt_source.pack(fill="both", expand=True)

        right_box = tk.Frame(panes, bg=THEME["bg_card"], padx=8, pady=8, bd=1, relief="solid")
        panes.add(right_box, stretch="always")
        self.txt_result = tk.Text(right_box, bg=THEME["bg_dark"], fg="#86efac", insertbackground=THEME["text"], font=self.mono_font, wrap="word")
        self.txt_result.pack(fill="both", expand=True)

    def run_text_redact(self) -> None:
        raw = self.txt_source.get("1.0", "end-1c")
        enabled = {k for k, v in self.kind_vars.items() if v.get()}
        res = redact.redact(raw, kinds=enabled)
        self.txt_result.delete("1.0", "end")
        self.txt_result.insert("1.0", res["redacted"])
        self.status_var.set(f"{len(res['findings'])} donnée(s) masquée(s).")

    def copy_text_result(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self.txt_result.get("1.0", "end-1c"))
        self.status_var.set("Résultat copié dans le presse-papiers.")

    # ------------------------------------------------------------------ onglet 3 : nettoyeur
    def _build_cleaner_tab(self) -> None:
        tab = tk.Frame(self.notebook, bg=THEME["bg_dark"], padx=10, pady=10)
        self.notebook.add(tab, text="  Nettoyeur Multi-Formats  ")
        bar = tk.Frame(tab, bg=THEME["bg_card"], padx=12, pady=10)
        bar.pack(fill="x")
        ttk.Button(bar, text="Ajouter des fichiers…", command=self.add_cleaner_files).pack(side="left", padx=(0, 8))
        ttk.Button(bar, text="Nettoyer les fichiers", command=self.run_cleaner).pack(side="left", padx=(0, 8))
        ttk.Button(bar, text="Vider la liste", command=self.clear_cleaner).pack(side="left")
        tk.Label(
            tab, text="Les originaux ne sont jamais modifiés : une copie « _propre » est créée à côté.",
            bg=THEME["bg_dark"], fg=THEME["text_muted"], font=self.base_font,
        ).pack(anchor="w", pady=(6, 0))

        self.clean_tree = ttk.Treeview(tab, columns=("status", "size"), selectmode="extended")
        self.clean_tree.heading("#0", text="Fichier")
        self.clean_tree.heading("status", text="Statut")
        self.clean_tree.heading("size", text="Taille")
        self.clean_tree.column("#0", width=380)
        self.clean_tree.column("status", width=380)
        self.clean_tree.column("size", width=120, anchor="e")
        self.clean_tree.pack(fill="both", expand=True, pady=10)

    def add_cleaner_files(self) -> None:
        exts = " ".join(f"*{e}" for e in sorted(cleaner.SUPPORTED_EXTS))
        paths = filedialog.askopenfilenames(filetypes=[("Documents & images", exts), ("Tous", "*.*")])
        for p in paths:
            path = Path(p)
            iid = self.clean_tree.insert("", "end", text=path.name, values=("En attente", f"{path.stat().st_size // 1024} Ko"))
            self.cleaner_files[iid] = path

    def clear_cleaner(self) -> None:
        self.clean_tree.delete(*self.clean_tree.get_children())
        self.cleaner_files.clear()

    def run_cleaner(self) -> None:
        if not self.cleaner_files:
            messagebox.showinfo("Bouclier", "Ajoutez d'abord des fichiers.")
            return
        done = 0
        for iid, path in list(self.cleaner_files.items()):
            try:
                res = cleaner.clean_file(path.name, path.read_bytes())
                out = path.with_name(res["filename"])
                out.write_bytes(res["data"])
                found = ", ".join(res["found"]) if res["found"] else "aucune métadonnée trouvée"
                self.clean_tree.item(iid, values=(f"✔ Nettoyé → {out.name} ({found})", f"{res['size_after'] // 1024} Ko"))
                done += 1
            except Exception as e:
                self.clean_tree.item(iid, values=(f"✖ Échec : {e}", ""))
            self.update_idletasks()
        self.status_var.set(f"{done}/{len(self.cleaner_files)} fichier(s) nettoyé(s).")

    # ------------------------------------------------------------------ onglet 4 : arnaques
    def _build_scam_tab(self) -> None:
        tab = tk.Frame(self.notebook, bg=THEME["bg_dark"], padx=10, pady=10)
        self.notebook.add(tab, text="  Anti-Arnaque & Phishing  ")
        self.scam_input = tk.Text(tab, height=4, bg=THEME["bg_card"], fg=THEME["text"], insertbackground=THEME["text"], font=self.mono_font)
        self.scam_input.pack(fill="x", pady=6)
        ttk.Button(tab, text="Analyser le message", command=self.run_scam_analysis).pack(anchor="w")
        self.scam_report = tk.Text(tab, bg=THEME["bg_card"], fg=THEME["text"], font=self.base_font)
        self.scam_report.pack(fill="both", expand=True, pady=6)

    def run_scam_analysis(self) -> None:
        txt = self.scam_input.get("1.0", "end-1c")
        res = scam.analyze(txt)
        self.scam_report.delete("1.0", "end")
        self.scam_report.insert("end", f"VERDICT : {res['label']} ({res['score']}/100)\n\n")
        for r in res["reasons"]:
            self.scam_report.insert("end", f"● {r['text']}\n")
        for a in res.get("advice", []):
            self.scam_report.insert("end", f"→ {a}\n")

    # ------------------------------------------------------------------ onglet 5 : motifs perso
    def _build_patterns_tab(self) -> None:
        tab = tk.Frame(self.notebook, bg=THEME["bg_dark"], padx=10, pady=10)
        self.notebook.add(tab, text="  Motifs & Mots-clés  ")
        tk.Label(
            tab, bg=THEME["bg_dark"], fg=THEME["text_muted"], font=self.base_font, justify="left", anchor="w",
            text="Ajoutez vos propres données à masquer (n° de dossier, nom de projet…). Elles s'appliquent au texte ET aux images (OCR).\n"
                 "Exemple de motif (expression régulière) : DOS-\\d{4}      Exemple de mot-clé : Projet Phoenix",
        ).pack(fill="x", pady=(0, 8))

        form = tk.Frame(tab, bg=THEME["bg_card"], padx=12, pady=10, bd=1, relief="solid")
        form.pack(fill="x", pady=(0, 8))
        tk.Label(form, text="Nom :", bg=THEME["bg_card"], fg=THEME["text"], font=self.base_font).grid(row=0, column=0, sticky="w")
        self.pat_label_var = tk.StringVar()
        tk.Entry(form, textvariable=self.pat_label_var, width=24).grid(row=0, column=1, padx=6)
        tk.Label(form, text="Motif (regex) :", bg=THEME["bg_card"], fg=THEME["text"], font=self.base_font).grid(row=0, column=2, sticky="w")
        self.pat_regex_var = tk.StringVar()
        tk.Entry(form, textvariable=self.pat_regex_var, width=32).grid(row=0, column=3, padx=6)
        ttk.Button(form, text="Ajouter le motif", command=self.add_pattern).grid(row=0, column=4, padx=6)

        tk.Label(form, text="Mot-clé :", bg=THEME["bg_card"], fg=THEME["text"], font=self.base_font).grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.kw_var = tk.StringVar()
        tk.Entry(form, textvariable=self.kw_var, width=24).grid(row=1, column=1, padx=6, pady=(8, 0))
        ttk.Button(form, text="Ajouter le mot-clé", command=self.add_keyword).grid(row=1, column=4, padx=6, pady=(8, 0))

        self.pat_list = tk.Listbox(tab, bg=THEME["bg_card"], fg=THEME["text"], font=self.mono_font, selectmode="extended")
        self.pat_list.pack(fill="both", expand=True, pady=(0, 8))
        ttk.Button(tab, text="Supprimer la sélection", command=self.delete_pattern_selection).pack(anchor="w")
        self._pat_items = []
        self._refresh_patterns_list()

    def _refresh_patterns_list(self) -> None:
        self.pat_list.delete(0, "end")
        self._pat_items = []
        for p in ner_engine.registry.custom_patterns():
            self.pat_list.insert("end", f"[motif]    {p['label']}  →  {p['regex']}")
            self._pat_items.append(("pattern", p["id"]))
        for kw in sorted(ner_engine.registry.custom_keywords):
            self.pat_list.insert("end", f"[mot-clé] {kw}")
            self._pat_items.append(("keyword", kw))

    def add_pattern(self) -> None:
        label, rx = self.pat_label_var.get().strip(), self.pat_regex_var.get().strip()
        if not label or not rx:
            messagebox.showinfo("Bouclier", "Renseignez un nom et un motif.")
            return
        if not ner_engine.registry.add_custom_pattern(label, rx):
            messagebox.showwarning("Bouclier", "Motif refusé : expression invalide, ou qui accepterait un texte vide.")
            return
        self.pat_label_var.set("")
        self.pat_regex_var.set("")
        self._refresh_patterns_list()
        self.status_var.set(f"Motif « {label} » enregistré.")

    def add_keyword(self) -> None:
        kw = self.kw_var.get().strip()
        if not ner_engine.registry.add_keyword(kw):
            messagebox.showinfo("Bouclier", "Saisissez un mot-clé d'au moins 2 caractères.")
            return
        self.kw_var.set("")
        self._refresh_patterns_list()
        self.status_var.set(f"Mot-clé « {kw} » enregistré.")

    def delete_pattern_selection(self) -> None:
        for idx in self.pat_list.curselection():
            kind, key = self._pat_items[idx]
            (ner_engine.registry.remove_pattern if kind == "pattern" else ner_engine.registry.remove_keyword)(key)
        self._refresh_patterns_list()


def main() -> None:
    if tk is None:
        raise RuntimeError(
            "Tkinter n'est pas installé. Windows/macOS : réinstallez Python depuis python.org "
            "(cochez « tcl/tk and IDLE »). Linux : sudo apt install python3-tk"
        )
    _enable_dpi_awareness()
    ModernDesktopApp().mainloop()
