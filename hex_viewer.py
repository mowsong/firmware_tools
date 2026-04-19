import os
import io
import cProfile
import pstats
import zlib
from bisect import bisect_left
from time import perf_counter
import ctypes


import wx
import wx.lib.mixins.listctrl as listmix
from intelhex import IntelHex, HexRecordError


PROFILE = False


class HexListCtrl(wx.ListCtrl, listmix.ListCtrlAutoWidthMixin):
    def __init__(self, parent, owner: "MainFrame"):
        super().__init__(parent, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.LC_VIRTUAL)
        listmix.ListCtrlAutoWidthMixin.__init__(self)
        self.owner = owner

    def OnGetItemText(self, item, col):
        return self.owner.get_cell_text(item, col)


class HexFileDropTarget(wx.FileDropTarget):
    def __init__(self, frame: "MainFrame"):
        super().__init__()
        self.frame = frame

    def OnDropFiles(self, x, y, filenames):
        if not filenames:
            return False
        self.frame.open_path(filenames[0], from_drop=True)
        return True


class MainFrame(wx.Frame):
    def __init__(self):
        super().__init__(None, title="Intel HEX Viewer", size=(1100, 700))

        # App window icon
        ico_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hex_viewer.ico")
        if os.path.exists(ico_path):
            self.SetIcon(wx.Icon(ico_path, wx.BITMAP_TYPE_ICO))

        self.ih: IntelHex | None = None
        self.unit_size = 1  # 1, 2, 4 bytes
        self.goto_history: list[str] = []

        # Virtual view cache
        self.mem: dict[int, int] = {}
        self.row_bases: list[int] = []

        self.data_crc32: int | None = None
        self.file_crc32: int | None = None

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        toolbar = wx.BoxSizer(wx.HORIZONTAL)

        btn_open = wx.Button(panel, label="Open...")
        btn_open.Bind(wx.EVT_BUTTON, self.on_open)
        toolbar.Add(btn_open, 0, wx.RIGHT, 16)

        toolbar.Add(wx.StaticText(panel, label="View as:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.choice_unit = wx.Choice(panel, choices=["1 byte", "2 bytes", "4 bytes"])
        self.choice_unit.SetSelection(0)
        self.choice_unit.Bind(wx.EVT_CHOICE, self.on_unit_change)
        toolbar.Add(self.choice_unit, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 16)

        toolbar.Add(wx.StaticText(panel, label="Go to:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.combo_goto = wx.ComboBox(
            panel,
            size=(140, -1),
            style=wx.CB_DROPDOWN | wx.TE_PROCESS_ENTER,
        )
        self.combo_goto.Bind(wx.EVT_TEXT_ENTER, self.on_goto)
        toolbar.Add(self.combo_goto, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)

        btn_goto = wx.Button(panel, label="Go", size=(40, -1))
        btn_goto.Bind(wx.EVT_BUTTON, self.on_goto)
        toolbar.Add(btn_goto, 0, wx.ALIGN_CENTER_VERTICAL)

        # Push CRC text to the right side of toolbar
        toolbar.AddStretchSpacer(1)
        self.lbl_crc = wx.StaticText(panel, label="Data CRC32: N/A   File CRC32: N/A")
        toolbar.Add(self.lbl_crc, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 12)

        self.list_ctrl = HexListCtrl(panel, self)

        # Use Courier-style monospace font for data grid
        mono_font = wx.Font(
            10,
            wx.FONTFAMILY_TELETYPE,
            wx.FONTSTYLE_NORMAL,
            wx.FONTWEIGHT_NORMAL,
            faceName="Courier New",
        )
        self.list_ctrl.SetFont(mono_font)

        self.configure_columns()

        sizer.Add(toolbar, 0, wx.ALL, 8)
        sizer.Add(self.list_ctrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        panel.SetSizer(sizer)

        # Drag & drop support
        self.SetDropTarget(HexFileDropTarget(self))
        panel.SetDropTarget(HexFileDropTarget(self))
        self.list_ctrl.SetDropTarget(HexFileDropTarget(self))

        self.CreateStatusBar()  # single field for file path/status
        self.SetStatusText("Open an Intel HEX or BIN file (or drag & drop)")
        self._update_crc_status()

    def _update_crc_status(self):
        data_s = "N/A" if self.data_crc32 is None else f"0x{self.data_crc32:08X}"
        file_s = "N/A" if self.file_crc32 is None else f"0x{self.file_crc32:08X}"
        self.lbl_crc.SetLabel(f"Data CRC32: {data_s}   File CRC32: {file_s}")

    @staticmethod
    def _crc32_bytes(data: bytes) -> int:
        # Matches crcmod.mkCrcFun(0x104C11DB7, initCrc=0, rev=True, xorOut=0)
        return (zlib.crc32(data, 0xFFFFFFFF) ^ 0xFFFFFFFF) & 0xFFFFFFFF

    def _calc_data_crc32_from_intelhex(self, ih: IntelHex) -> int | None:
        addrs = ih.addresses()
        if not addrs:
            return None

        crc = 0xFFFFFFFF
        chunk = bytearray()
        for a in addrs:  # ascending addresses
            chunk.append(ih[a])
            if len(chunk) >= 65536:
                crc = zlib.crc32(chunk, crc)
                chunk.clear()

        if chunk:
            crc = zlib.crc32(chunk, crc)

        return (crc ^ 0xFFFFFFFF) & 0xFFFFFFFF

    def _profile_call(self, name, func, *args, **kwargs):
        if not PROFILE:
            return func(*args, **kwargs)

        profiler = cProfile.Profile()
        start = perf_counter()
        try:
            profiler.enable()
            return func(*args, **kwargs)
        finally:
            profiler.disable()
            elapsed = perf_counter() - start

            s = io.StringIO()
            stats = pstats.Stats(profiler, stream=s).sort_stats("cumulative")
            stats.print_stats(25)

            report = f"=== PROFILE: {name} ({elapsed:.3f}s) ===\n{s.getvalue()}"
            print(report)

            report_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                f"profile_{name}.txt",
            )
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(report)
                
    def configure_columns(self):
        self.list_ctrl.ClearAll()
        self.list_ctrl.InsertColumn(0, "Address", width=110)

        cols = 16 // self.unit_size
        col_width = {1: 38, 2: 64, 4: 112}[self.unit_size]

        for c in range(cols):
            start = c * self.unit_size
            # Show base only: byte -> 0..F, halfword -> 0,2,4..E, word -> 0,4,8,C
            label = f"{start:X}"
            self.list_ctrl.InsertColumn(c + 1, label, width=col_width)

        self.list_ctrl.InsertColumn(cols + 1, "ASCII", width=180)
        self.list_ctrl.Refresh()

    def on_unit_change(self, _evt):
        self.unit_size = [1, 2, 4][self.choice_unit.GetSelection()]
        self.configure_columns()
        self.populate_table()

    def on_goto(self, _evt):
        raw = self.combo_goto.GetValue().strip()
        if not raw:
            return

        try:
            target = int(raw, 0)
            if target < 0:
                raise ValueError("negative address")
        except ValueError:
            wx.MessageBox(
                "Invalid address.\nUse decimal (32768) or hex (0x8000).",
                "Invalid Address",
                wx.OK | wx.ICON_WARNING,
            )
            return

        if not self.row_bases:
            wx.MessageBox("No file loaded.", "Go To Address", wx.OK | wx.ICON_INFORMATION)
            return

        row_base = target & ~0x0F
        match = bisect_left(self.row_bases, row_base)

        if match >= len(self.row_bases):
            wx.MessageBox(
                f"Address 0x{target:08X} is beyond the end of the file.",
                "Go To Address",
                wx.OK | wx.ICON_INFORMATION,
            )
            return

        self.list_ctrl.EnsureVisible(match)
        self.list_ctrl.Select(match)
        self.list_ctrl.Focus(match)

        formatted = f"0x{target:08X}"
        if formatted in self.goto_history:
            self.goto_history.remove(formatted)
        self.goto_history.insert(0, formatted)
        self.goto_history = self.goto_history[:20]

        self.combo_goto.Set(self.goto_history)
        self.combo_goto.SetValue(formatted)

        self.SetStatusText(f"Jumped to 0x{target:08X} (row 0x{self.row_bases[match]:08X})")

    def _load_hex_file(self, path: str) -> bool:
        try:
            # raw file CRC32 (exact file bytes)
            with open(path, "rb") as f:
                raw = f.read()
            file_crc = self._crc32_bytes(raw)

            ih = IntelHex()
            self._profile_call("load_hex", ih.loadhex, path)

            self.ih = ih
            self.file_crc32 = file_crc
            self.data_crc32 = self._calc_data_crc32_from_intelhex(ih)

            self._profile_call("populate_table", self.populate_table)
            self.SetStatusText(f"Loaded HEX: {path}", 0)
            self._update_crc_status()
            return True
        except (OSError, HexRecordError, ValueError) as e:
            wx.MessageBox(str(e), "Error", wx.OK | wx.ICON_ERROR)
            return False

    def _load_bin_file(self, path: str, offset: int) -> bool:
        try:
            with open(path, "rb") as f:
                data = f.read()

            def build_ih():
                ih = IntelHex()
                ih.frombytes(data, offset=offset)
                return ih

            self.ih = self._profile_call("load_bin", build_ih)

            self.file_crc32 = self._crc32_bytes(data)   # raw file bytes
            self.data_crc32 = self._crc32_bytes(data)   # decoded data bytes (same for BIN)

            self._profile_call("populate_table", self.populate_table)
            self.SetStatusText(f"Loaded BIN: {path} @ 0x{offset:X} ({len(data)} bytes)", 0)
            self._update_crc_status()
            return True
        except OSError as e:
            wx.MessageBox(str(e), "Error", wx.OK | wx.ICON_ERROR)
            return False

    def open_path(self, path: str, from_drop: bool = False):
        ext = os.path.splitext(path)[1].lower()

        if ext in (".hex", ".ihex", ".ihx"):
            self._load_hex_file(path)
            return

        if ext == ".bin":
            offset = self._ask_offset()
            if offset is None:
                return
            self._load_bin_file(path, offset)
            return

        wx.MessageBox(
            f"Unsupported file type: {ext or '(no extension)'}\nSupported: .hex, .bin",
            "Unsupported File",
            wx.OK | wx.ICON_INFORMATION,
        )

    def on_open(self, _evt):
        with wx.FileDialog(
            self,
            "Open file",
            wildcard=(
                "Supported files (*.hex;*.ihex;*.ihx;*.bin)|*.hex;*.ihex;*.ihx;*.bin|"
                "HEX files (*.hex;*.ihex;*.ihx)|*.hex;*.ihex;*.ihx|"
                "BIN files (*.bin)|*.bin|"
                "All files (*.*)|*.*"
            ),
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            self.open_path(dlg.GetPath())

    def _ask_offset(self) -> int | None:
        while True:
            with wx.TextEntryDialog(
                self,
                "Enter load offset (decimal or hex, e.g. 0x8000):",
                "Binary Load Offset",
                value="0x0",
            ) as dlg:
                if dlg.ShowModal() != wx.ID_OK:
                    return None
                raw = dlg.GetValue().strip()

            try:
                offset = int(raw, 0)
                if offset < 0:
                    raise ValueError("negative offset")
                return offset
            except ValueError:
                wx.MessageBox(
                    "Invalid offset.\nUse decimal (32768) or hex (0x8000).",
                    "Invalid Input",
                    wx.OK | wx.ICON_WARNING,
                )

    def populate_table(self):
        t0 = perf_counter()

        if self.ih is None:
            self.mem = {}
            self.row_bases = []
            self.list_ctrl.SetItemCount(0)
            self.list_ctrl.Refresh()
            return

        addrs = self.ih.addresses()
        if not addrs:
            self.mem = {}
            self.row_bases = []
            self.list_ctrl.SetItemCount(0)
            self.list_ctrl.Refresh()
            return

        t1 = perf_counter()

        self.mem = self.ih.todict()
        
        if self.mem:
            min_base = min(self.mem.keys()) & ~0x0F
            max_base = max(self.mem.keys()) & ~0x0F
            self.row_bases = list(range(min_base, max_base + 0x10, 0x10))
        else:
            self.row_bases = []
        # ...existing code...

        t2 = perf_counter()

        self.list_ctrl.Freeze()
        try:
            self.list_ctrl.SetItemCount(len(self.row_bases))
            self.list_ctrl.Refresh()
        finally:
            self.list_ctrl.Thaw()

        t3 = perf_counter()

        if PROFILE:
            print(
                f"populate_table timings: "
                f"prep1={t1 - t0:.3f}s, "
                f"prep2={t2 - t1:.3f}s, "
                f"ui={t3 - t2:.3f}s, "
                f"total={t3 - t0:.3f}s"
            )

    def get_cell_text(self, item: int, col: int) -> str:
        if item < 0 or item >= len(self.row_bases):
            return ""

        row_base = self.row_bases[item]
        cols = 16 // self.unit_size
        ascii_col = cols + 1
        mem = self.mem

        if col == 0:
            return f"0x{row_base:08X}"

        if col == ascii_col:
            chars = []
            for i in range(16):
                b = mem.get(row_base + i)
                if b is None:
                    chars.append(" ")
                else:
                    chars.append(chr(b) if 32 <= b <= 126 else ".")
            return "".join(chars)

        if 1 <= col <= cols:
            group_start = row_base + ((col - 1) * self.unit_size)
            vals = [mem.get(group_start + j) for j in range(self.unit_size)]
            if any(v is None for v in vals):
                return "." * (2 * self.unit_size)
            return "".join(f"{v:02X}" for v in vals)

        return ""


class HexViewerApp(wx.App):
    def OnInit(self):
        frame = MainFrame()
        frame.Show()
        return True


def enable_high_dpi_windows():
    """Enable best-available DPI awareness on Windows."""
    if os.name != "nt":
        return
    try:
        # Windows 10+ (Per-Monitor v2)
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        return
    except Exception:
        pass
    try:
        # Windows 8.1+ (Per-Monitor)
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except Exception:
        pass
    try:
        # Vista+ (System DPI aware)
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


if __name__ == "__main__":
    enable_high_dpi_windows()  # must run before wx.App()
    app = HexViewerApp(False)
    app.MainLoop()