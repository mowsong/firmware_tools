import os
import ctypes
import wx
import wx.stc as stc
from intelhex import IntelHex, HexRecordError

STYLE_NORMAL = 0
STYLE_DIFF = 1
INDIC_CURRENT_DIFF = 0
MONO_FACE = "Consolas"


ICON_DIR = os.path.join(os.path.dirname(__file__), "icons")


def _load_icon(name: str, size: tuple[int, int] = (16, 16)) -> wx.Bitmap:
    path = os.path.join(ICON_DIR, name)
    img = wx.Image(path, wx.BITMAP_TYPE_PNG)
    img.Rescale(*size, wx.IMAGE_QUALITY_HIGH)
    return wx.Bitmap(img)


def ask_offset(parent: wx.Window, side: str, path: str) -> int | None:
    while True:
        with wx.TextEntryDialog(
            parent,
            f"{side} file is BIN:\n{path}\n\nEnter load offset (decimal or hex, e.g. 0x8000):",
            f"{side} BIN Offset",
            value="0x0",
        ) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return None
            raw = dlg.GetValue().strip()

        try:
            value = int(raw, 0)
            if value < 0:
                raise ValueError("negative")
            return value
        except ValueError:
            wx.MessageBox(
                "Invalid offset.\nUse decimal (32768) or hex (0x8000).",
                "Invalid Input",
                wx.OK | wx.ICON_WARNING,
            )


def load_path(parent: wx.Window, path: str, side: str) -> dict[int, int]:
    ext = os.path.splitext(path)[1].lower()

    if ext in (".hex", ".ihex", ".ihx"):
        ih = IntelHex()
        try:
            ih.loadhex(path)
        except (OSError, HexRecordError, ValueError) as e:
            raise RuntimeError(f"{side} load failed: {e}") from e
        return ih.todict()

    if ext == ".bin":
        try:
            with open(path, "rb") as f:
                data = f.read()
        except OSError as e:
            raise RuntimeError(f"{side} load failed: {e}") from e

        offset = ask_offset(parent, side, path)
        if offset is None:
            raise RuntimeError(f"{side} load cancelled")
        return {offset + i: b for i, b in enumerate(data)}

    raise RuntimeError(f"{side}: unsupported file type '{ext or '(no extension)'}'")


class DiffMarkerStrip(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent, size=(10, -1))
        self.diff_lines: list[int] = []
        self.current_line: int | None = None
        self.total_lines: int = 1

        self.SetMinSize((10, -1))
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.Bind(wx.EVT_PAINT, self.on_paint)

    def update_markers(self, diff_lines: list[int], total_lines: int, current_line: int | None = None):
        self.diff_lines = diff_lines
        self.total_lines = max(1, total_lines)
        self.current_line = current_line
        self.Refresh()

    def on_paint(self, _evt):
        dc = wx.AutoBufferedPaintDC(self)
        width, height = self.GetClientSize()

        dc.SetBackground(wx.Brush(wx.Colour(245, 245, 245)))
        dc.Clear()

        if height <= 0 or width <= 0 or self.total_lines <= 0:
            return

        dc.SetPen(wx.TRANSPARENT_PEN)

        def line_to_y(line: int) -> int:
            # map line -> y using the same ratio for all markers
            return int(line * height / self.total_lines)

        dc.SetBrush(wx.Brush(wx.Colour(220, 0, 0)))
        for line in self.diff_lines:
            y = line_to_y(line)
            dc.DrawRectangle(1, y, max(1, width - 2), max(2, height // self.total_lines or 2))

        if self.current_line is not None:
            y = line_to_y(self.current_line)
            dc.SetBrush(wx.Brush(wx.Colour(0, 120, 215)))
            dc.DrawRectangle(0, y, width, max(3, height // self.total_lines or 3))


class DiffFrame(wx.Frame):
    
    def __init__(self):
        super().__init__(None, title="HEX/BIN Byte Diff", size=(1620, 880))

        self.left_path = ""
        self.right_path = ""
        self.left_mem: dict[int, int] = {}
        self.right_mem: dict[int, int] = {}

        self._syncing_scroll = False
        self._updating_text = False

        self.diff_nav_positions: list[tuple[int, int]] = []
        self.current_diff_idx: int = -1

        panel = wx.Panel(self)
        root = wx.BoxSizer(wx.VERTICAL)

        # ── toolbar ──────────────────────────────────────────────────────────
        toolbar = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_open_left  = wx.Button(panel, label="Open Left...")
        self.btn_open_right = wx.Button(panel, label="Open Right...")
        self.chk_only_diff  = wx.CheckBox(panel, label="Only differences")
        self.txt_range_start = wx.TextCtrl(panel, value="", style=wx.TE_PROCESS_ENTER, size=(95, -1))
        self.txt_range_end   = wx.TextCtrl(panel, value="", style=wx.TE_PROCESS_ENTER, size=(95, -1))
        self.btn_first_diff = wx.BitmapButton(panel, bitmap=_load_icon("icon_first.png"), size=(36, -1))
        self.btn_prev_diff  = wx.BitmapButton(panel, bitmap=_load_icon("icon_prev.png"),  size=(36, -1))
        self.btn_next_diff  = wx.BitmapButton(panel, bitmap=_load_icon("icon_next.png"),  size=(36, -1))
        self.btn_last_diff  = wx.BitmapButton(panel, bitmap=_load_icon("icon_last.png"),  size=(36, -1))
        self.btn_refresh    = wx.Button(panel, label="Refresh")

        self.btn_open_left.Bind(wx.EVT_BUTTON,    self.on_open_left)
        self.btn_open_right.Bind(wx.EVT_BUTTON,   self.on_open_right)
        self.chk_only_diff.Bind(wx.EVT_CHECKBOX,  self.on_refresh)
        self.txt_range_start.Bind(wx.EVT_TEXT_ENTER, self.on_refresh)
        self.txt_range_end.Bind(wx.EVT_TEXT_ENTER,   self.on_refresh)
        self.btn_first_diff.Bind(wx.EVT_BUTTON,   self.on_first_diff)
        self.btn_prev_diff.Bind(wx.EVT_BUTTON,    self.on_prev_diff)
        self.btn_next_diff.Bind(wx.EVT_BUTTON,    self.on_next_diff)
        self.btn_last_diff.Bind(wx.EVT_BUTTON,    self.on_last_diff)
        self.btn_refresh.Bind(wx.EVT_BUTTON,      self.on_refresh)

        if hasattr(self.txt_range_start, "SetHint"):
            self.txt_range_start.SetHint("start")
            self.txt_range_end.SetHint("stop")

        toolbar.Add(self.btn_open_left,  0, wx.RIGHT, 8)
        toolbar.Add(self.btn_open_right, 0, wx.RIGHT, 12)
        toolbar.Add(self.chk_only_diff,  0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 12)
        toolbar.Add(wx.StaticText(panel, label="Range [start, stop):"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        toolbar.Add(wx.StaticText(panel, label="0x"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 2)
        toolbar.Add(self.txt_range_start, 0, wx.RIGHT, 6)
        toolbar.Add(wx.StaticText(panel, label="to"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        toolbar.Add(wx.StaticText(panel, label="0x"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 2)
        toolbar.Add(self.txt_range_end,   0, wx.RIGHT, 12)
        toolbar.Add(self.btn_first_diff, 0, wx.RIGHT, 4)
        toolbar.Add(self.btn_prev_diff,  0, wx.RIGHT, 4)
        toolbar.Add(self.btn_next_diff,  0, wx.RIGHT, 4)
        toolbar.Add(self.btn_last_diff,  0, wx.RIGHT, 12)
        toolbar.Add(self.btn_refresh,    0)

        root.Add(toolbar, 0, wx.ALL | wx.EXPAND, 8)

        # ── pane labels + splitter ────────────────────────────────────────────
        pane_container = wx.Panel(panel)
        pane_sizer = wx.BoxSizer(wx.VERTICAL)

        labels = wx.BoxSizer(wx.HORIZONTAL)
        self.lbl_left  = wx.StaticText(pane_container, label="LEFT")
        self.lbl_right = wx.StaticText(pane_container, label="RIGHT")
        labels.Add(self.lbl_left,  1, wx.LEFT, 4)
        labels.Add(self.lbl_right, 1, wx.LEFT, 8)
        pane_sizer.Add(labels, 0, wx.BOTTOM | wx.EXPAND, 4)

        self.splitter = wx.SplitterWindow(pane_container, style=wx.SP_LIVE_UPDATE | wx.SP_3D)

        self.left_pane  = wx.Panel(self.splitter)
        self.right_pane = wx.Panel(self.splitter)

        left_pane_sizer  = wx.BoxSizer(wx.HORIZONTAL)
        right_pane_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.left_view   = stc.StyledTextCtrl(self.left_pane)
        self.right_view  = stc.StyledTextCtrl(self.right_pane)
        self.left_marker_strip  = DiffMarkerStrip(self.left_pane)
        self.right_marker_strip = DiffMarkerStrip(self.right_pane)

        left_pane_sizer.Add(self.left_view,  1, wx.EXPAND)
        left_pane_sizer.Add(self.left_marker_strip,  0, wx.EXPAND)
        right_pane_sizer.Add(self.right_view, 1, wx.EXPAND)
        right_pane_sizer.Add(self.right_marker_strip, 0, wx.EXPAND)

        self.left_pane.SetSizer(left_pane_sizer)
        self.right_pane.SetSizer(right_pane_sizer)

        self.splitter.SplitVertically(self.left_pane, self.right_pane, sashPosition=805)

        self._setup_stc(self.left_view)
        self._setup_stc(self.right_view)

        self.left_view.Bind(stc.EVT_STC_UPDATEUI,  self._on_left_update_ui)
        self.right_view.Bind(stc.EVT_STC_UPDATEUI, self._on_right_update_ui)

        pane_sizer.Add(self.splitter, 1, wx.EXPAND)
        pane_container.SetSizer(pane_sizer)

        root.Add(pane_container, 1, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)
        panel.SetSizer(root)

        # ── status bar: single field ─────────────────────────────────────────
        self.CreateStatusBar(1)
        self.SetStatusText("Open LEFT and RIGHT files")
        self._update_nav_buttons()

        # ── accelerators ─────────────────────────────────────────────────────
        self.ID_NEXT_DIFF = wx.NewIdRef()
        self.ID_PREV_DIFF = wx.NewIdRef()
        accel = wx.AcceleratorTable([
            (wx.ACCEL_NORMAL, wx.WXK_F7, self.ID_NEXT_DIFF),
            (wx.ACCEL_SHIFT,  wx.WXK_F7, self.ID_PREV_DIFF),
        ])
        self.SetAcceleratorTable(accel)
        self.Bind(wx.EVT_MENU, self.on_next_diff, id=self.ID_NEXT_DIFF)
        self.Bind(wx.EVT_MENU, self.on_prev_diff, id=self.ID_PREV_DIFF)

    # ── status bar helper ────────────────────────────────────────────────────
    def _set_status(self, *parts: str):
        """Join non-empty parts with  |  and show in the single status field."""
        text = "  |  ".join(p for p in parts if p)
        self.SetStatusText(text)

    # ── STC setup ────────────────────────────────────────────────────────────
    def _setup_stc(self, ctrl: stc.StyledTextCtrl):
        ctrl.SetLexer(stc.STC_LEX_NULL)
        ctrl.StyleClearAll()

        ctrl.SetCodePage(stc.STC_CP_UTF8)
        ctrl.SetEOLMode(stc.STC_EOL_LF)

        ctrl.StyleSetFaceName(STYLE_NORMAL, MONO_FACE)
        ctrl.StyleSetSize(STYLE_NORMAL, 10)
        ctrl.StyleSetForeground(STYLE_NORMAL, wx.Colour(0, 0, 0))
        ctrl.StyleSetBackground(STYLE_NORMAL, wx.Colour(255, 255, 255))

        ctrl.StyleSetFaceName(STYLE_DIFF, MONO_FACE)
        ctrl.StyleSetSize(STYLE_DIFF, 10)
        ctrl.StyleSetBold(STYLE_DIFF, True)
        ctrl.StyleSetForeground(STYLE_DIFF, wx.Colour(255, 255, 255))
        ctrl.StyleSetBackground(STYLE_DIFF, wx.Colour(220, 0, 0))

        ctrl.StyleSetFaceName(stc.STC_STYLE_DEFAULT,    MONO_FACE)
        ctrl.StyleSetFaceName(stc.STC_STYLE_LINENUMBER, MONO_FACE)

        ctrl.SetWrapMode(stc.STC_WRAP_NONE)
        ctrl.SetUseHorizontalScrollBar(True)
        ctrl.SetReadOnly(True)
        ctrl.SetCaretLineVisible(False)
        ctrl.SetMarginWidth(0, 0)
        ctrl.SetMarginWidth(1, 0)
        ctrl.SetMarginWidth(2, 0)
        ctrl.SetSelBackground(True, wx.Colour(220, 235, 255))

        ctrl.IndicatorSetStyle(INDIC_CURRENT_DIFF, stc.STC_INDIC_ROUNDBOX)
        ctrl.IndicatorSetForeground(INDIC_CURRENT_DIFF, wx.Colour(0, 120, 215))
        try:
            ctrl.IndicatorSetAlpha(INDIC_CURRENT_DIFF, 110)
            ctrl.IndicatorSetOutlineAlpha(INDIC_CURRENT_DIFF, 180)
        except Exception:
            pass

    # ── file picker ──────────────────────────────────────────────────────────
    def _pick_path(self, title: str) -> str | None:
        with wx.FileDialog(
            self, title,
            wildcard=(
                "Supported files (*.hex;*.ihex;*.ihx;*.bin)|*.hex;*.ihex;*.ihx;*.bin|"
                "HEX files (*.hex;*.ihex;*.ihx)|*.hex;*.ihex;*.ihx|"
                "BIN files (*.bin)|*.bin|"
                "All files (*.*)|*.*"
            ),
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return None
            return dlg.GetPath()

    # ── helpers ──────────────────────────────────────────────────────────────
    @staticmethod
    def _fmt(v: int | None) -> str:
        return ".." if v is None else f"{v:02X}"

    def _parse_addr_or_blank(self, raw: str) -> int | None:
        raw = raw.strip()
        if not raw:
            return None
        if raw.lower().startswith("0x"):
            raw = raw[2:]
        raw = raw.replace("_", "")
        if not raw:
            raise ValueError("empty hex")
        value = int(raw, 16)
        if value < 0:
            raise ValueError("negative address")
        return value

    def _get_compare_bounds(self, show_error: bool = False) -> tuple[int | None, int | None] | None:
        try:
            start = self._parse_addr_or_blank(self.txt_range_start.GetValue())
            stop  = self._parse_addr_or_blank(self.txt_range_end.GetValue())
            if start is not None and stop is not None and stop <= start:
                raise ValueError("stop must be > start")
            return start, stop
        except ValueError as e:
            if show_error:
                wx.MessageBox(
                    f"Invalid range: {e}\nEnter HEX values only (e.g. 8000 or 0x8000).\n"
                    "Stop must be strictly greater than Start.",
                    "Invalid Range",
                    wx.OK | wx.ICON_WARNING,
                )
            return None

    @staticmethod
    def _addr_in_range(addr: int, bounds: tuple[int | None, int | None]) -> bool:
        start, stop = bounds
        if start is not None and addr < start:
            return False
        if stop is not None and addr >= stop:
            return False
        return True

    @staticmethod
    def _row_overlaps_range(base: int, bounds: tuple[int | None, int | None]) -> bool:
        start, stop = bounds
        row_stop = base + 16
        if start is not None and row_stop <= start:
            return False
        if stop is not None and base >= stop:
            return False
        return True

    @staticmethod
    def _format_range_label(bounds: tuple[int | None, int | None]) -> str:
        start, stop = bounds
        if start is None and stop is None:
            return "full range"
        if start is None:
            return f"[.., 0x{stop:08X})"
        if stop is None:
            return f"[0x{start:08X}, ..)"
        return f"[0x{start:08X}, 0x{stop:08X})"

    def _build_sparse_row_bases(self, bounds: tuple[int | None, int | None]) -> list[int]:
        addrs = set(self.left_mem.keys()) | set(self.right_mem.keys())
        if not addrs:
            return []
        bases = sorted({a & ~0x0F for a in addrs})
        bases = [b for b in bases if self._row_overlaps_range(b, bounds)]

        if not self.chk_only_diff.GetValue():
            return bases

        out: list[int] = []
        for base in bases:
            for i in range(16):
                a = base + i
                if not self._addr_in_range(a, bounds):
                    continue
                if self.left_mem.get(a) != self.right_mem.get(a):
                    out.append(base)
                    break
        return out

    def _build_single_pane_text(self, mem: dict[int, int], bounds: tuple[int | None, int | None]) -> str:
        if not mem:
            return ""
        bases = sorted({a & ~0x0F for a in mem.keys()})
        bases = [b for b in bases if self._row_overlaps_range(b, bounds)]
        chunks: list[str] = []
        for base in bases:
            chunks.append(f"{base:08X}: ")
            for i in range(16):
                if i > 0:
                    chunks.append(" ")
                a = base + i
                chunks.append(self._fmt(mem.get(a)) if self._addr_in_range(a, bounds) else "..")
            chunks.append("\n")
        return "".join(chunks)

    def _build_texts_and_spans(
        self, bases: list[int], bounds: tuple[int | None, int | None]
    ) -> tuple[str, list[tuple[int, int]], str, list[tuple[int, int]], int, int, list[tuple[int, int]]]:
        left_chunks:   list[str]             = []
        right_chunks:  list[str]             = []
        left_spans:    list[tuple[int, int]] = []
        right_spans:   list[tuple[int, int]] = []
        nav_positions: list[tuple[int, int]] = []

        left_pos = right_pos = compared = diffs = 0

        for base in bases:
            prefix = f"{base:08X}: "
            left_chunks.append(prefix)
            right_chunks.append(prefix)
            left_pos  += len(prefix)
            right_pos += len(prefix)

            for i in range(16):
                a  = base + i
                lv = self.left_mem.get(a)
                rv = self.right_mem.get(a)

                if i > 0:
                    left_chunks.append(" ");  left_pos  += 1
                    right_chunks.append(" "); right_pos += 1

                in_range = self._addr_in_range(a, bounds)
                ltok = self._fmt(lv) if in_range else ".."
                rtok = self._fmt(rv) if in_range else ".."

                left_chunks.append(ltok)
                right_chunks.append(rtok)

                if in_range:
                    if lv is not None or rv is not None:
                        compared += 1
                    if lv != rv and not (lv is None and rv is None):
                        diffs += 1
                        left_spans.append((left_pos, 2))
                        right_spans.append((right_pos, 2))
                        nav_positions.append((left_pos, right_pos))

                left_pos  += 2
                right_pos += 2

            left_chunks.append("\n");  left_pos  += 1
            right_chunks.append("\n"); right_pos += 1

        return (
            "".join(left_chunks), left_spans,
            "".join(right_chunks), right_spans,
            compared, diffs, nav_positions,
        )

    # ── indicator helpers ────────────────────────────────────────────────────
    def _clear_current_diff_highlight(self):
        for ctrl in (self.left_view, self.right_view):
            ctrl.SetIndicatorCurrent(INDIC_CURRENT_DIFF)
            ctrl.IndicatorClearRange(0, ctrl.GetTextLength())

    def _mark_current_diff_highlight(self, left_pos: int, right_pos: int, length: int = 2):
        self._clear_current_diff_highlight()
        self.left_view.SetIndicatorCurrent(INDIC_CURRENT_DIFF)
        self.left_view.IndicatorFillRange(left_pos, length)
        self.right_view.SetIndicatorCurrent(INDIC_CURRENT_DIFF)
        self.right_view.IndicatorFillRange(right_pos, length)

    # ── marker strip ─────────────────────────────────────────────────────────
    def _update_marker_strips(self):
        left_total  = max(1, self.left_view.GetLineCount())
        right_total = max(1, self.right_view.GetLineCount())

        diff_lines: list[int] = []
        if self.diff_nav_positions:
            seen: set[int] = set()
            for lpos, _ in self.diff_nav_positions:
                line = self.left_view.LineFromPosition(lpos)
                if line not in seen:
                    seen.add(line)
                    diff_lines.append(line)

        current_line = None
        if 0 <= self.current_diff_idx < len(self.diff_nav_positions):
            lpos, _ = self.diff_nav_positions[self.current_diff_idx]
            current_line = self.left_view.LineFromPosition(lpos)

        self.left_marker_strip.update_markers(diff_lines, left_total, current_line)
        self.right_marker_strip.update_markers(diff_lines, right_total, current_line)

    def _update_nav_buttons(self):
        enabled = bool(self.left_path and self.right_path and self.diff_nav_positions)
        self.btn_first_diff.Enable(enabled)
        self.btn_prev_diff.Enable(enabled)
        self.btn_next_diff.Enable(enabled)
        self.btn_last_diff.Enable(enabled)

    # ── scroll sync ──────────────────────────────────────────────────────────
    def _sync_to_other(self, source: stc.StyledTextCtrl, target: stc.StyledTextCtrl):
        if self._syncing_scroll or self._updating_text:
            return
        self._syncing_scroll = True
        try:
            delta = source.GetFirstVisibleLine() - target.GetFirstVisibleLine()
            if delta:
                target.LineScroll(0, delta)
            src_x = source.GetXOffset()
            if src_x != target.GetXOffset():
                target.SetXOffset(src_x)
        finally:
            self._syncing_scroll = False

    def _on_left_update_ui(self, _evt):
        self._sync_to_other(self.left_view, self.right_view)

    def _on_right_update_ui(self, _evt):
        self._sync_to_other(self.right_view, self.left_view)

    # ── apply styled text ────────────────────────────────────────────────────
    def _apply_styled_text(self, ctrl: stc.StyledTextCtrl, text: str, diff_spans: list[tuple[int, int]]):
        ctrl.Freeze()
        try:
            ctrl.SetReadOnly(False)
            ctrl.SetText(text)
            ctrl.StartStyling(0)
            ctrl.SetStyling(len(text), STYLE_NORMAL)
            for start, length in diff_spans:
                if start >= 0 and length > 0 and (start + length) <= len(text):
                    ctrl.StartStyling(start)
                    ctrl.SetStyling(length, STYLE_DIFF)
            ctrl.EmptyUndoBuffer()
            ctrl.SetReadOnly(True)
        finally:
            ctrl.Thaw()

    # ── open handlers ────────────────────────────────────────────────────────
    def on_open_left(self, _evt):
        path = self._pick_path("Select LEFT file")
        if not path:
            return
        try:
            self.left_mem  = load_path(self, path, "LEFT")
            self.left_path = path
            self.lbl_left.SetLabel(f"LEFT:  {os.path.basename(path)}")
            self.refresh_views()
        except RuntimeError as e:
            wx.MessageBox(str(e), "Load Error", wx.OK | wx.ICON_ERROR)

    def on_open_right(self, _evt):
        path = self._pick_path("Select RIGHT file")
        if not path:
            return
        try:
            self.right_mem  = load_path(self, path, "RIGHT")
            self.right_path = path
            self.lbl_right.SetLabel(f"RIGHT: {os.path.basename(path)}")
            self.refresh_views()
        except RuntimeError as e:
            wx.MessageBox(str(e), "Load Error", wx.OK | wx.ICON_ERROR)

    def on_refresh(self, _evt):
        self.refresh_views()

    # ── navigation ───────────────────────────────────────────────────────────
    def _jump_to_diff(self, idx: int):
        if not self.diff_nav_positions:
            return
        idx %= len(self.diff_nav_positions)
        self.current_diff_idx = idx
        lpos, rpos = self.diff_nav_positions[idx]

        self._syncing_scroll = True
        try:
            self._mark_current_diff_highlight(lpos, rpos, 2)
            self.left_view.GotoPos(lpos)
            self.right_view.GotoPos(rpos)
            self.left_view.EnsureCaretVisible()
            self.right_view.EnsureCaretVisible()
        finally:
            self._syncing_scroll = False

        self._update_marker_strips()
        self._set_status(
            self._format_range_label(self._get_compare_bounds() or (None, None)),
            f"Diff {idx + 1} / {len(self.diff_nav_positions)}",
            "F7/Shift+F7: next/prev diff",
        )

    def on_first_diff(self, _evt):
        if not (self.left_path and self.right_path) or not self.diff_nav_positions:
            return
        self._jump_to_diff(0)

    def on_last_diff(self, _evt):
        if not (self.left_path and self.right_path) or not self.diff_nav_positions:
            return
        self._jump_to_diff(len(self.diff_nav_positions) - 1)

    def on_next_diff(self, _evt):
        if not (self.left_path and self.right_path) or not self.diff_nav_positions:
            return
        self._jump_to_diff(self.current_diff_idx + 1)

    def on_prev_diff(self, _evt):
        if not (self.left_path and self.right_path) or not self.diff_nav_positions:
            return
        if self.current_diff_idx < 0:
            self._jump_to_diff(len(self.diff_nav_positions) - 1)
        else:
            self._jump_to_diff(self.current_diff_idx - 1)

    # ── main refresh ─────────────────────────────────────────────────────────
    def refresh_views(self):
        bounds = self._get_compare_bounds(show_error=True)
        if bounds is None:
            return

        range_label  = self._format_range_label(bounds)
        left_loaded  = bool(self.left_path)
        right_loaded = bool(self.right_path)

        self._updating_text = True
        try:
            self.diff_nav_positions = []
            self.current_diff_idx   = -1
            self._clear_current_diff_highlight()

            if not left_loaded and not right_loaded:
                self._apply_styled_text(self.left_view,  "", [])
                self._apply_styled_text(self.right_view, "", [])
                self._update_marker_strips()
                self._set_status("Open LEFT and RIGHT files")
                return

            if left_loaded and not right_loaded:
                self._apply_styled_text(self.left_view,  self._build_single_pane_text(self.left_mem, bounds), [])
                self._apply_styled_text(self.right_view, "", [])
                self.left_view.ScrollToLine(0);  self.left_view.SetXOffset(0)
                self.right_view.ScrollToLine(0); self.right_view.SetXOffset(0)
                self._update_marker_strips()
                self._set_status(range_label, "Load RIGHT file to compare")
                return

            if right_loaded and not left_loaded:
                self._apply_styled_text(self.left_view,  "", [])
                self._apply_styled_text(self.right_view, self._build_single_pane_text(self.right_mem, bounds), [])
                self.left_view.ScrollToLine(0);  self.left_view.SetXOffset(0)
                self.right_view.ScrollToLine(0); self.right_view.SetXOffset(0)
                self._update_marker_strips()
                self._set_status(range_label, "Load LEFT file to compare")
                return

            bases = self._build_sparse_row_bases(bounds)
            if not bases:
                self._apply_styled_text(self.left_view,  "", [])
                self._apply_styled_text(self.right_view, "", [])
                self._update_marker_strips()
                self._set_status(range_label, "No data in range")
                return

            left_text, left_spans, right_text, right_spans, compared, diffs, nav_positions = \
                self._build_texts_and_spans(bases, bounds)

            self.diff_nav_positions = nav_positions
            self._apply_styled_text(self.left_view,  left_text,  left_spans)
            self._apply_styled_text(self.right_view, right_text, right_spans)
            self.left_view.ScrollToLine(0);  self.left_view.SetXOffset(0)
            self.right_view.ScrollToLine(0); self.right_view.SetXOffset(0)
            self._update_marker_strips()

            nav = "F7/Shift+F7: next/prev diff" if diffs else "No differences"
            self._set_status(range_label, f"Rows: {len(bases)}", f"Compared: {compared}", f"Diffs: {diffs}", nav)

        finally:
            self._updating_text = False
            self._update_nav_buttons()


class DiffApp(wx.App):
    def OnInit(self):
        frame = DiffFrame()
        frame.Show()
        return True


def enable_high_dpi_windows():
    if os.name != "nt":
        return
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        return
    except Exception:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


if __name__ == "__main__":
    enable_high_dpi_windows()
    app = DiffApp(False)
    app.MainLoop()