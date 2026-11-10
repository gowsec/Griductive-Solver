"""Griductive Tkinter GUI application framework (dark theme, card-based board)."""

from __future__ import annotations

import time
import tkinter as tk
from tkinter import filedialog, ttk
from tkinter import font as tkfont
from typing import Any

from griductive.engine.dummy_engine import DummyEngine, VerdictOutcome, VerdictResult
from griductive.model.cell import CellId, Status

# ── Palette ──────────────────────────────────────────────────────────────────
BG = "#1f1712"
PANEL = "#2b2119"
PANEL_2 = "#3a2d22"
BORDER = "#52402f"
FG = "#f3e9dc"
MUTED = "#a8957f"

HIDDEN_BG, HIDDEN_HOVER = "#3a2d22", "#4a392b"
CRIM_BG, CRIM_FG = "#4d2420", "#ff6b81"
INNO_BG, INNO_FG = "#24402a", "#5ef0a0"
HILITE = "#f6e05e"
ACCENT = "#d4a373"
GREEN, YELLOW, RED, BLUE = "#5ef0a0", "#f6c85f", "#ff6b81", "#7dd3fc"

FLASH = {  # kind -> (background, border)
    "warn": ("#5a4a1a", YELLOW),
    "error": ("#5a2622", RED),
    "hint": ("#1f4a5c", BLUE),
}


def _pick_font(root: tk.Misc, candidates: tuple[str, ...], fallback: str) -> str:
    families = set(tkfont.families(root))
    return next((f for f in candidates if f in families), fallback)


class GriductiveGUI:
    """Tkinter Graphical User Interface for Griductive solver."""

    def __init__(self, root: tk.Tk, engine: Any = None) -> None:
        self.root = root
        self.root.title("Griductive Solver - Propositional Logic Deduction")
        self.root.geometry("1100x720")
        self.root.minsize(900, 600)
        self.root.configure(bg=BG)

        self.engine = engine if engine is not None else DummyEngine()
        self.selected_cell: CellId | None = None
        self.highlighted_cells: set[CellId] = set()
        self.auto_solving = False
        self.cards: dict[CellId, dict[str, Any]] = {}

        sans = _pick_font(root, ("Segoe UI", "SF Pro Text", "Helvetica Neue", "Ubuntu", "DejaVu Sans"), "Helvetica")
        mono = _pick_font(root, ("Cascadia Mono", "Consolas", "Menlo", "DejaVu Sans Mono"), "Courier")
        self.f_title = (sans, 20, "bold")
        self.f_h2 = (sans, 11, "bold")
        self.f_body = (sans, 10)
        self.f_small = (sans, 9)
        self.f_head = (sans, 11, "bold")
        self.f_icon = (sans, 24)
        self.f_mono = (mono, 10)
        self.f_mono_s = (mono, 9)

        self._setup_style()
        self._setup_ui()
        self._bind_shortcuts()
        self.refresh()

    # ── Setup ────────────────────────────────────────────────────────────────
    def _setup_style(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(
            "Tool.TButton", background=PANEL_2, foreground=FG, borderwidth=0,
            focuscolor=PANEL_2, padding=(14, 7), font=self.f_body,
        )
        style.map("Tool.TButton", background=[("active", "#5a4535"), ("pressed", "#6b523f")])
        style.configure(
            "Accent.TButton", background=ACCENT, foreground="#1f1712", borderwidth=0,
            focuscolor=ACCENT, padding=(14, 7), font=(self.f_body[0], 10, "bold"),
        )
        style.map("Accent.TButton", background=[("active", "#e6bf94"), ("pressed", "#b9885a")])
        style.configure(
            "Prog.Horizontal.TProgressbar", troughcolor=PANEL_2, background=GREEN,
            bordercolor=PANEL_2, lightcolor=GREEN, darkcolor=GREEN, thickness=10,
        )
        style.configure(
            "Dark.Vertical.TScrollbar", background="#5a4535", troughcolor=PANEL,
            bordercolor=PANEL, arrowcolor=FG, relief="flat",
        )

    def _panel(self, parent: tk.Misc, title: str) -> tuple[tk.Frame, tk.Frame]:
        outer = tk.Frame(parent, bg=PANEL, highlightthickness=1, highlightbackground=BORDER)
        tk.Label(outer, text=title, bg=PANEL, fg=FG, font=self.f_h2, anchor="w").pack(
            fill=tk.X, padx=14, pady=(10, 6)
        )
        body = tk.Frame(outer, bg=PANEL)
        body.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))
        return outer, body

    def _setup_ui(self) -> None:
        # Header: title + actions
        header = tk.Frame(self.root, bg=BG)
        header.pack(side=tk.TOP, fill=tk.X, padx=16, pady=(14, 8))

        title_box = tk.Frame(header, bg=BG)
        title_box.pack(side=tk.LEFT)
        tk.Label(title_box, text="🕵️ Griductive", bg=BG, fg=FG, font=self.f_title).pack(anchor="w")
        tk.Label(
            title_box, text="Propositional logic deduction - prove every cell without guessing",
            bg=BG, fg=MUTED, font=self.f_small,
        ).pack(anchor="w")

        actions = tk.Frame(header, bg=BG)
        actions.pack(side=tk.RIGHT)
        ttk.Button(actions, text="📂  Load", style="Tool.TButton", command=self.on_load_puzzle).pack(side=tk.LEFT, padx=4)
        ttk.Button(actions, text="🔄  Restart", style="Tool.TButton", command=self.on_restart).pack(side=tk.LEFT, padx=4)
        ttk.Button(actions, text="💡  Hint", style="Tool.TButton", command=self.on_hint).pack(side=tk.LEFT, padx=4)
        self.btn_auto_solve = ttk.Button(actions, text="⚡  Auto Solve", style="Accent.TButton", command=self.on_auto_solve)
        self.btn_auto_solve.pack(side=tk.LEFT, padx=(4, 0))

        # Footer: status + progress (packed before main so it keeps its space)
        footer = tk.Frame(self.root, bg=PANEL, highlightthickness=1, highlightbackground=BORDER)
        footer.pack(side=tk.BOTTOM, fill=tk.X)
        self.lbl_status = tk.Label(footer, text="Ready", bg=PANEL, fg=FG, font=self.f_h2, anchor="w")
        self.lbl_status.pack(side=tk.LEFT, padx=14, pady=8)
        self.lbl_progress = tk.Label(footer, text="0 / 0", bg=PANEL, fg=MUTED, font=self.f_small)
        self.lbl_progress.pack(side=tk.RIGHT, padx=14)
        self.progress = ttk.Progressbar(footer, style="Prog.Horizontal.TProgressbar", length=180, mode="determinate")
        self.progress.pack(side=tk.RIGHT, pady=8)

        # Main area
        main = tk.Frame(self.root, bg=BG)
        main.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 12))
        main.grid_columnconfigure(0, weight=3, uniform="cols")
        main.grid_columnconfigure(1, weight=2, uniform="cols")
        main.grid_rowconfigure(0, weight=1)

        board_outer, board_body = self._panel(main, "Puzzle Grid")
        board_outer.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.grid_frame = tk.Frame(board_body, bg=PANEL)
        self.grid_frame.pack(fill=tk.BOTH, expand=True)

        right = tk.Frame(main, bg=BG)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        right.grid_rowconfigure(0, weight=3)
        right.grid_rowconfigure(1, weight=2)
        right.grid_columnconfigure(0, weight=1)

        clue_outer, clue_body = self._panel(right, "Revealed Clues")
        clue_outer.grid(row=0, column=0, sticky="nsew", pady=(0, 8))
        clue_scroll = ttk.Scrollbar(clue_body, style="Dark.Vertical.TScrollbar")
        clue_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.clue_listbox = tk.Listbox(
            clue_body, font=self.f_mono, bg=PANEL_2, fg=FG, bd=0, highlightthickness=0,
            selectbackground=ACCENT, selectforeground="#1f1712", activestyle="none",
            exportselection=False, yscrollcommand=clue_scroll.set,
        )
        self.clue_listbox.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        clue_scroll.config(command=self.clue_listbox.yview)
        self.clue_listbox.bind("<<ListboxSelect>>", self.on_clue_selected)

        log_outer, log_body = self._panel(right, "Deduction Log")
        log_outer.grid(row=1, column=0, sticky="nsew")
        log_scroll = ttk.Scrollbar(log_body, style="Dark.Vertical.TScrollbar")
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text = tk.Text(
            log_body, height=8, state=tk.DISABLED, font=self.f_mono_s, bg=PANEL_2, fg=FG,
            bd=0, highlightthickness=0, wrap=tk.WORD, padx=8, pady=6, yscrollcommand=log_scroll.set,
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        log_scroll.config(command=self.log_text.yview)
        for tag, color in (("time", MUTED), ("info", FG), ("ok", GREEN), ("warn", YELLOW), ("err", RED), ("hint", BLUE)):
            self.log_text.tag_config(tag, foreground=color)

    def _bind_shortcuts(self) -> None:
        self.root.bind("<Control-o>", lambda _e: self.on_load_puzzle())
        self.root.bind("<Control-r>", lambda _e: self.on_restart())
        self.root.bind("<Control-h>", lambda _e: self.on_hint())
        self.root.bind("<Control-Return>", lambda _e: self.on_auto_solve())
        self.root.bind("<Escape>", lambda _e: self._clear_highlight())

    # ── Rendering ────────────────────────────────────────────────────────────
    def refresh(self) -> None:
        """Re-render the grid board and clues panel based on engine state."""
        state = self.engine.public_state()
        self._render_grid(state)

        self.clue_listbox.delete(0, tk.END)
        for clue in state.revealed_clues:
            self.clue_listbox.insert(tk.END, f" [{clue.id}]  {clue.describe()}")

        total = state.n * state.n
        done = len(state.proved)
        self.progress.config(maximum=max(total, 1), value=done)
        self.lbl_progress.config(text=f"{done} / {total} cells")

        if self.engine.is_solved():
            self._stop_auto()
            self.set_status("🎉 PUZZLE SOLVED!", GREEN)

    def _render_grid(self, state: Any) -> None:
        for child in self.grid_frame.winfo_children():
            child.destroy()
        self.cards.clear()
        n = state.n

        for c in range(n):
            tk.Label(
                self.grid_frame, text=chr(ord("A") + c), bg=PANEL, fg=MUTED, font=self.f_head
            ).grid(row=0, column=c + 1, sticky="nsew", pady=(0, 4))
        for r in range(n):
            tk.Label(
                self.grid_frame, text=str(r + 1), bg=PANEL, fg=MUTED, font=self.f_head, width=2
            ).grid(row=r + 1, column=0, sticky="nsew", padx=(0, 4))
            for c in range(n):
                self._create_cell_widget(CellId(r, c), r + 1, c + 1, state)

        for i in range(1, n + 1):
            self.grid_frame.grid_rowconfigure(i, weight=1, uniform="row", minsize=80)
            self.grid_frame.grid_columnconfigure(i, weight=1, uniform="col", minsize=90)

    def _create_cell_widget(self, cell: CellId, grid_r: int, grid_c: int, state: Any) -> None:
        status = state.proved.get(cell)
        hidden = status is None

        if status == Status.CRIMINAL:
            bg, fg, icon, text = CRIM_BG, CRIM_FG, "🔴", "CRIMINAL"
            border = CRIM_FG
        elif status is not None:
            bg, fg, icon, text = INNO_BG, INNO_FG, "🟢", "INNOCENT"
            border = INNO_FG
        else:
            bg, fg, icon, text = HIDDEN_BG, MUTED, "❓", "HIDDEN"
            border = BORDER

        if cell in self.highlighted_cells:
            border = HILITE

        card = tk.Frame(
            self.grid_frame, bg=bg, highlightthickness=2, highlightbackground=border,
            cursor="hand2" if hidden else "arrow",
        )
        card.grid(row=grid_r, column=grid_c, sticky="nsew", padx=5, pady=5)

        lbl_name = tk.Label(card, text=str(cell), bg=bg, fg=MUTED, font=self.f_small, anchor="w")
        lbl_name.pack(fill=tk.X, padx=8, pady=(6, 0))
        lbl_icon = tk.Label(card, text=icon, bg=bg, fg=fg, font=self.f_icon)
        lbl_icon.pack(expand=True)
        lbl_text = tk.Label(card, text=text, bg=bg, fg=fg, font=(self.f_body[0], 9, "bold"))
        lbl_text.pack(pady=(0, 8))

        widgets = [card, lbl_name, lbl_icon, lbl_text]
        self.cards[cell] = {"frame": card, "widgets": widgets, "bg": bg, "border": border}

        for w in widgets:
            w.bind("<Button-1>", lambda _e, c=cell: self.on_cell_clicked(c))
            if hidden:
                w.bind("<Enter>", lambda _e, c=cell: self._paint(c, bg=HIDDEN_HOVER, border=ACCENT))
                w.bind("<Leave>", lambda _e, c=cell: self._restore(c))

    def _paint(self, cell: CellId, bg: str, border: str) -> None:
        card = self.cards.get(cell)
        if not card or not card["frame"].winfo_exists():
            return
        card["frame"].config(bg=bg, highlightbackground=border)
        for w in card["widgets"][1:]:
            w.config(bg=bg)

    def _restore(self, cell: CellId) -> None:
        card = self.cards.get(cell)
        if card:
            self._paint(cell, card["bg"], card["border"])

    def _flash_cell(self, cell: CellId, kind: str = "warn") -> None:
        if cell not in self.cards:
            return
        bg, border = FLASH.get(kind, FLASH["warn"])
        self._paint(cell, bg, border)
        self.root.after(800, lambda: self._restore(cell))

    # ── Log / status ─────────────────────────────────────────────────────────
    def set_status(self, text: str, color: str = FG) -> None:
        self.lbl_status.config(text=text, fg=color)

    def log(self, message: str, level: str | None = None) -> None:
        """Append a colour-coded, timestamped message to the deduction log."""
        if level is None:
            if message.startswith("✅"):
                level = "ok"
            elif message.startswith("⚠"):
                level = "warn"
            elif message.startswith(("❌", "🚨")):
                level = "err"
            elif message.startswith("💡"):
                level = "hint"
            else:
                level = "info"
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, time.strftime("%H:%M:%S  "), "time")
        self.log_text.insert(tk.END, message + "\n", level)
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    # ── Interactions ─────────────────────────────────────────────────────────
    def on_cell_clicked(self, cell: CellId) -> None:
        """Handle clicking a cell card to open verdict selection."""
        state = self.engine.public_state()
        if cell in state.proved:
            self.log(f"Cell {cell} already solved as {state.proved[cell].value}.")
            return
        self.selected_cell = cell
        self._open_verdict_dialog(cell)

    def _open_verdict_dialog(self, cell: CellId) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Verdict - {cell}")
        dialog.configure(bg=PANEL)
        dialog.resizable(False, False)
        dialog.transient(self.root)

        w, h = 380, 190
        x = self.root.winfo_rootx() + (self.root.winfo_width() - w) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - h) // 2
        dialog.geometry(f"{w}x{h}+{x}+{y}")

        tk.Label(dialog, text=f"Cell {cell}", bg=PANEL, fg=FG, font=(self.f_title[0], 16, "bold")).pack(pady=(18, 2))
        tk.Label(dialog, text="Can you prove this cell's status?", bg=PANEL, fg=MUTED, font=self.f_body).pack()

        def make_verdict(st: Status) -> None:
            dialog.destroy()
            self._handle_verdict_result(cell, st, self.engine.submit(cell, st))

        row = tk.Frame(dialog, bg=PANEL)
        row.pack(pady=18)
        for text, st, bg, fg in (
            ("🔴  Criminal  (C)", Status.CRIMINAL, CRIM_BG, CRIM_FG),
            ("🟢  Innocent  (I)", Status.INNOCENT, INNO_BG, INNO_FG),
        ):
            tk.Button(
                row, text=text, command=lambda s=st: make_verdict(s), bg=bg, fg=fg,
                activebackground=bg, activeforeground=fg, relief=tk.FLAT, bd=0,
                font=(self.f_body[0], 10, "bold"), padx=14, pady=10, cursor="hand2",
            ).pack(side=tk.LEFT, padx=8)

        dialog.bind("<c>", lambda _e: make_verdict(Status.CRIMINAL))
        dialog.bind("<i>", lambda _e: make_verdict(Status.INNOCENT))
        dialog.bind("<Escape>", lambda _e: dialog.destroy())
        dialog.focus_set()
        dialog.grab_set()

    def _handle_verdict_result(self, cell: CellId, st: Status, res: VerdictResult) -> None:
        if res.outcome == VerdictOutcome.ACCEPTED:
            self.log(f"✅ ACCEPTED: Cell {cell} proved {st.value}.")
            self.set_status(f"Proved {cell} as {st.value}", GREEN)
            self.refresh()
        elif res.outcome == VerdictOutcome.NOT_PROVABLE:
            self.log(f"⚠️ NOT_PROVABLE: {st.value} for {cell} cannot be proved without guessing!")
            self.set_status(f"NOT_PROVABLE for {cell}", YELLOW)
            self._flash_cell(cell, "warn")
        elif res.outcome == VerdictOutcome.CONTRADICTED:
            self.log(f"❌ CONTRADICTED: {st.value} for {cell} is contradicted by current clues!")
            self.set_status(f"CONTRADICTED for {cell}", RED)
            self._flash_cell(cell, "error")
        elif res.outcome == VerdictOutcome.INCONSISTENT:
            self.log("🚨 INCONSISTENT: Knowledge base contains a contradiction!")
            self.set_status("INCONSISTENT KB", RED)

    def on_clue_selected(self, event: Any = None) -> None:
        """Highlight grid cells associated with the selected clue."""
        selection = self.clue_listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        state = self.engine.public_state()
        if 0 <= idx < len(state.revealed_clues):
            clue = state.revealed_clues[idx]
            try:
                self.highlighted_cells = set(clue.cells(state.n))
                self.log(f"Highlighting cells for clue {clue.id}: {sorted(str(c) for c in self.highlighted_cells)}")
                self._render_grid(state)  # keep clue selection intact
            except Exception as e:  # noqa: BLE001
                self.log(f"Could not highlight clue cells: {e}", "err")

    def _clear_highlight(self) -> None:
        if self.highlighted_cells:
            self.highlighted_cells.clear()
            self.clue_listbox.selection_clear(0, tk.END)
            self._render_grid(self.engine.public_state())

    def on_load_puzzle(self) -> None:
        filename = filedialog.askopenfilename(filetypes=[("JSON Puzzles", "*.json"), ("All Files", "*.*")])
        if filename:
            self.log(f"Selected puzzle file: {filename}")

    def on_restart(self) -> None:
        self._stop_auto()
        self.engine.restart()
        self.highlighted_cells.clear()
        self.log("Game restarted to initial revealed cards.")
        self.set_status("Ready", FG)
        self.refresh()

    def on_hint(self) -> None:
        state = self.engine.public_state()
        if state.unsolved:
            first_unsolved = state.unsolved[0]
            self.log(f"💡 Hint: Try investigating unsolved cell {first_unsolved}.")
            self._flash_cell(first_unsolved, "hint")

    # ── Auto solve ───────────────────────────────────────────────────────────
    def _stop_auto(self) -> None:
        self.auto_solving = False
        self.btn_auto_solve.config(text="⚡  Auto Solve")

    def on_auto_solve(self) -> None:
        if self.auto_solving:
            self._stop_auto()
            self.log("Auto solve stopped.")
            return
        if self.engine.is_solved():
            self.log("Puzzle already solved.")
            return
        self.auto_solving = True
        self.btn_auto_solve.config(text="⏹  Stop")
        self._auto_step()

    def _auto_step(self) -> None:
        if not self.auto_solving:
            return
        state = self.engine.public_state()
        puzzle = getattr(self.engine, "puzzle", None)
        if self.engine.is_solved() or not state.unsolved or puzzle is None:
            self._stop_auto()
            return

        cell = state.unsolved[0]
        if cell not in puzzle.solution:
            self._stop_auto()
            return
        correct = puzzle.solution[cell]
        res = self.engine.submit(cell, correct)
        self._handle_verdict_result(cell, correct, res)

        if res.outcome == VerdictOutcome.ACCEPTED and not self.engine.is_solved():
            self.root.after(400, self._auto_step)
        else:
            self._stop_auto()