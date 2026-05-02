import os
import io
import cProfile
import pstats
import crcmod
import crcmod.predefined
from bisect import bisect_left
from time import perf_counter
import ctypes

import wx
import wx.lib.mixins.listctrl as listmix
from intelhex import IntelHex, HexRecordError
from version import __version_viewer__ as __version__


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
        super().__init__(None, title=f"Intel HEX Viewer v{__version__}", size=(1100, 750))

        ico_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons", "hex_viewer.ico")
        if os.path.exists(ico_path):
            self.SetIcon(wx.Icon(ico_path, wx.BITMAP_TYPE_ICO))

        self.ih: IntelHex | None = None
        self.unit_size = 1
        self.endianness = "little"  # default for multi-byte view
        self.goto_history: list[str] = []

        self.mem: dict[int, int] = {}
        self.row_bases: list[int] = []

        self.data_crc32: int | None = None
        self.file_crc32: int | None = None
        self.block_crc_result: tuple[int, int, int] | None = None  # (start, padded_end, crc)
        self.current_path: str | None = None
        self.current_bin_offset: int | None = None

        # crcmod functions
        self._crc16_fun = crcmod.mkCrcFun(0x11021, initCrc=0, rev=True)
        self._crc32_fun = crcmod.mkCrcFun(0x104C11DB7, initCrc=0, rev=True, xorOut=0)

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # -- Row 1: file open, view, goto, CRC32 values --
        tb1 = wx.BoxSizer(wx.HORIZONTAL)

        btn_open = wx.Button(panel, label="Open...")
        btn_open.Bind(wx.EVT_BUTTON, self.on_open)
        tb1.Add(btn_open, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)

        btn_refresh = wx.Button(panel, label="Refresh")
        btn_refresh.Bind(wx.EVT_BUTTON, self.on_refresh)
        tb1.Add(btn_refresh, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 16)

        # tb1.Add(wx.StaticText(panel, label="View as:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.choice_unit = wx.Choice(panel, choices=["1 byte", "2 bytes", "4 bytes"])
        self.choice_unit.SetSelection(0)
        self.choice_unit.SetToolTip("Grouping")
        self.choice_unit.Bind(wx.EVT_CHOICE, self.on_unit_change)
        tb1.Add(self.choice_unit, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 12)

        # tb1.Add(wx.StaticText(panel, label="Endian:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.choice_endian = wx.Choice(panel, choices=["Little-endian", "Big-endian"])
        self.choice_endian.SetSelection(0)  # default little-endian
        self.choice_endian.SetToolTip("Endianness for multi-byte view")
        self.choice_endian.Bind(wx.EVT_CHOICE, self.on_endian_change)
        self.choice_endian.Enable(False)  # 1-byte mode: endianness not applicable
        tb1.Add(self.choice_endian, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 16)

        # CRC32 labels sticky to the left (no stretch spacer before them)
        self.lbl_data_crc32 = wx.StaticText(panel, label="Data CRC32: N/A", size=(200, -1))
        tb1.Add(self.lbl_data_crc32, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 16)

        self.lbl_file_crc32 = wx.StaticText(panel, label="File CRC32: N/A", size=(200, -1))
        tb1.Add(self.lbl_file_crc32, 0, wx.ALIGN_CENTER_VERTICAL)

        # -- Row 2: block CRC (start, stop, block size, pad, button, result) --
        tb2 = wx.BoxSizer(wx.HORIZONTAL)

        tb2.Add(wx.StaticText(panel, label="Start:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.txt_crc_start = wx.TextCtrl(panel, value="0x00000000", size=(110, -1))
        tb2.Add(self.txt_crc_start, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)

        tb2.Add(wx.StaticText(panel, label="Stop:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.txt_crc_end = wx.TextCtrl(panel, value="0x00000000", size=(110, -1))
        tb2.Add(self.txt_crc_end, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)

        tb2.Add(wx.StaticText(panel, label="Block size:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.txt_block_size = wx.TextCtrl(panel, value="0x100", size=(80, -1))
        tb2.Add(self.txt_block_size, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)

        tb2.Add(wx.StaticText(panel, label="Pad:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.txt_pad = wx.TextCtrl(panel, value="0xFF", size=(60, -1))
        tb2.Add(self.txt_pad, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)

        btn_block_crc16 = wx.Button(panel, label="Block-aligned CRC16")
        btn_block_crc16.Bind(wx.EVT_BUTTON, self.on_calc_block_crc)
        tb2.Add(btn_block_crc16, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 16)

        self.lbl_block_crc = wx.StaticText(panel, label="N/A")
        tb2.Add(self.lbl_block_crc, 0, wx.ALIGN_CENTER_VERTICAL)

        # -- List --
        self.list_ctrl = HexListCtrl(panel, self)
        mono_font = wx.Font(10, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL, faceName="Courier New")
        self.list_ctrl.SetFont(mono_font)

        self.configure_columns()

        sizer.Add(tb1, 0, wx.ALL | wx.EXPAND, 8)
        sizer.Add(tb2, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)
        sizer.Add(self.list_ctrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        panel.SetSizer(sizer)

        self.SetDropTarget(HexFileDropTarget(self))
        panel.SetDropTarget(HexFileDropTarget(self))
        self.list_ctrl.SetDropTarget(HexFileDropTarget(self))

        self.CreateStatusBar()
        self.SetStatusText("Open an Intel HEX or BIN file (or drag & drop)")
        self._update_crc_status()
        self._update_block_crc_status()

        # F5 => Refresh
        self.ID_REFRESH = wx.NewIdRef()
        self.Bind(wx.EVT_MENU, self.on_refresh, id=self.ID_REFRESH)
        self.SetAcceleratorTable(
            wx.AcceleratorTable([
                wx.AcceleratorEntry(wx.ACCEL_NORMAL, wx.WXK_F5, self.ID_REFRESH),
            ])
        )

        # center window
        self.Center()
        
        
    # -- CRC helpers --

    def _crc16_bytes(self, data: bytes) -> int:
        return self._crc16_fun(data)

    def _crc32_bytes(self, data: bytes) -> int:
        return self._crc32_fun(data) & 0xFFFFFFFF

    def _calc_data_crc32_from_intelhex(self, ih: IntelHex) -> int | None:
        addrs = ih.addresses()
        if not addrs:
            return None
        crc = 0
        chunk = bytearray()
        for a in addrs:
            chunk.append(ih[a])
            if len(chunk) >= 65536:
                crc = self._crc32_fun(bytes(chunk), crc)
                chunk.clear()
        if chunk:
            crc = self._crc32_fun(bytes(chunk), crc)
        return crc & 0xFFFFFFFF

    # -- Status label updates --

    def _update_crc_status(self):
        data_s = "N/A" if self.data_crc32 is None else f"0x{self.data_crc32:08X}"
        file_s = "N/A" if self.file_crc32 is None else f"0x{self.file_crc32:08X}"
        self.lbl_data_crc32.SetLabel(f"Data CRC32: {data_s}")
        self.lbl_file_crc32.SetLabel(f"File CRC32: {file_s}")

    def _update_block_crc_status(self):
        if self.block_crc_result is None:
            self.lbl_block_crc.SetLabel("N/A")
            return
        start, padded_end, crc = self.block_crc_result
        self.lbl_block_crc.SetLabel(f"0x{crc:04X} (0x{start:08X}-0x{padded_end:08X})")

    def _set_status_loaded_file(self):
        if not self.current_path:
            self.SetStatusText("Open an Intel HEX or BIN file (or drag & drop)")
            return
        self.SetStatusText(f"{os.path.basename(self.current_path)} - {self.current_path}")

    # -- Input parsing --

    def _parse_non_negative_int(self, raw: str, field_name: str) -> int:
        s = raw.strip()
        if not s:
            raise ValueError(f"Missing {field_name}.")
        try:
            v = int(s, 0)
        except ValueError:
            raise ValueError(f"Invalid {field_name}: {raw!r}. Use decimal or 0x-prefixed hex.")
        if v < 0:
            raise ValueError(f"{field_name.capitalize()} must be non-negative.")
        return v

    # -- Auto-fill CRC range --

    def _autofill_crc_range(self):
        if not self.mem:
            return
        min_addr = min(self.mem.keys())
        max_addr = max(self.mem.keys())
        try:
            block_size = self._parse_non_negative_int(self.txt_block_size.GetValue(), "block size")
            if block_size <= 0:
                raise ValueError()
        except ValueError:
            block_size = 0x100
        snapped_start = (min_addr // block_size) * block_size
        # Stop is exclusive: one past the last address
        self.txt_crc_start.SetValue(f"0x{snapped_start:08X}")
        self.txt_crc_end.SetValue(f"0x{max_addr + 1:08X}")

    # -- CRC button handler --

    def on_calc_block_crc(self, _evt):
        if not self.mem:
            wx.MessageBox("No file loaded.", "Block-aligned CRC16", wx.OK | wx.ICON_INFORMATION)
            return
        try:
            block_size = self._parse_non_negative_int(self.txt_block_size.GetValue(), "block size")
            if block_size <= 0:
                raise ValueError("Block size must be > 0.")
            start = self._parse_non_negative_int(self.txt_crc_start.GetValue(), "start address")
            stop  = self._parse_non_negative_int(self.txt_crc_end.GetValue(),   "stop address")
            if stop <= start:
                raise ValueError("Stop address must be > start address.")
            if start % block_size != 0:
                raise ValueError("Start address must be a multiple of block size.")
            pad_val = self._parse_non_negative_int(self.txt_pad.GetValue(), "pad value")
            if pad_val > 0xFF:
                raise ValueError("Pad value must be 0x00-0xFF.")
        except ValueError as e:
            wx.MessageBox(str(e), "Invalid Input", wx.OK | wx.ICON_WARNING)
            return

        # Collect bytes from [start, stop), pad last block with pad_val
        data = bytearray(self.mem.get(a, pad_val) for a in range(start, stop))
        remainder = len(data) % block_size
        if remainder != 0:
            data += bytearray([pad_val] * (block_size - remainder))

        padded_stop = start + len(data)
        crc = self._crc16_bytes(bytes(data))

        self.block_crc_result = (start, padded_stop - 1, crc)
        self._update_block_crc_status()
        self._set_status_loaded_file()

    # -- File loading --

    def _compute_file_crc32(self, path: str) -> int:
        with open(path, "rb") as f:
            return self._crc32_bytes(f.read())

    def _load_hex_file(self, path: str) -> bool:
        try:
            with open(path, "rb") as f:
                raw = f.read()
            file_crc = self._crc32_bytes(raw)

            ih = IntelHex()
            self._profile_call("load_hex", ih.loadhex, path)

            self.ih = ih
            self.file_crc32 = file_crc
            self.data_crc32 = self._calc_data_crc32_from_intelhex(ih)
            self.block_crc_result = None
            self.current_bin_offset = None

            self._profile_call("populate_table", self.populate_table)
            self._autofill_crc_range()
            self._update_crc_status()
            self._update_block_crc_status()
            self.current_path = path
            self._set_status_loaded_file()
            return True
        except (OSError, HexRecordError, ValueError) as e:
            wx.MessageBox(str(e), "Error", wx.OK | wx.ICON_ERROR)
            return False

    def _load_bin_file(self, path: str, offset: int) -> bool:
        try:
            with open(path, "rb") as f:
                data = f.read()

            ih = IntelHex()
            ih.frombytes(data, offset=offset)

            self.ih = ih
            self.file_crc32 = self._crc32_bytes(data)
            self.data_crc32 = self._crc32_bytes(data)
            self.block_crc_result = None
            self.current_bin_offset = offset

            self._profile_call("populate_table", self.populate_table)
            self._autofill_crc_range()
            self._update_crc_status()
            self._update_block_crc_status()
            self.current_path = path
            self._set_status_loaded_file()
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

    def on_refresh(self, _evt):
        if not self.current_path:
            wx.MessageBox("No file loaded.", "Refresh", wx.OK | wx.ICON_INFORMATION)
            return

        # Flash status so user sees refresh started
        self.SetStatusText("Refreshing...")
        self.GetStatusBar().Update()

        try:
            current_crc = self._compute_file_crc32(self.current_path)
        except OSError as e:
            wx.MessageBox(str(e), "Refresh Error", wx.OK | wx.ICON_ERROR)
            self._set_status_loaded_file()
            return

        # If raw file bytes are unchanged, skip expensive parse/populate.
        if self.file_crc32 is not None and current_crc == self.file_crc32:
            self.SetStatusText(f"No changes: {os.path.basename(self.current_path)}")
            wx.CallLater(300, self._set_status_loaded_file)
            return

        ext = os.path.splitext(self.current_path)[1].lower()
        if ext in (".hex", ".ihex", ".ihx"):
            if self._load_hex_file(self.current_path):
                self.SetStatusText(f"Refreshed: {os.path.basename(self.current_path)}")
                wx.CallLater(300, self._set_status_loaded_file)
            return

        if ext == ".bin":
            offset = self.current_bin_offset
            if offset is None:
                offset = self._ask_offset()
                if offset is None:
                    self._set_status_loaded_file()
                    return
            if self._load_bin_file(self.current_path, offset):
                self.SetStatusText(f"Refreshed: {os.path.basename(self.current_path)}")
                wx.CallLater(1200, self._set_status_loaded_file)
            return

        wx.MessageBox(
            f"Unsupported file type: {ext or '(no extension)'}",
            "Refresh",
            wx.OK | wx.ICON_INFORMATION,
        )

    def _ask_offset(self) -> int | None:
        while True:
            with wx.TextEntryDialog(self, "Enter load offset (decimal or hex, e.g. 0x8000):",
                                    "Binary Load Offset", value="0x0") as dlg:
                if dlg.ShowModal() != wx.ID_OK:
                    return None
                raw = dlg.GetValue().strip()
            try:
                offset = int(raw, 0)
                if offset < 0:
                    raise ValueError("negative offset")
                return offset
            except ValueError:
                wx.MessageBox("Invalid offset.\nUse decimal (32768) or hex (0x8000).",
                              "Invalid Input", wx.OK | wx.ICON_WARNING)

    # -- Profiling --

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
            pstats.Stats(profiler, stream=s).sort_stats("cumulative").print_stats(25)
            report = f"=== PROFILE: {name} ({elapsed:.3f}s) ===\n{s.getvalue()}"
            print(report)
            report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"profile_{name}.txt")
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(report)

    # -- Columns & navigation --

    def configure_columns(self):
        self.list_ctrl.ClearAll()
        self.list_ctrl.InsertColumn(0, "Address", width=128)
        cols = 16 // self.unit_size
        col_width = {1: 38, 2: 64, 4: 112}[self.unit_size]
        for c in range(cols):
            self.list_ctrl.InsertColumn(c + 1, f"{c * self.unit_size:X}", width=col_width)
        self.list_ctrl.InsertColumn(cols + 1, "ASCII", width=180)
        self.list_ctrl.Refresh()

    def on_unit_change(self, _evt):
        self.unit_size = [1, 2, 4][self.choice_unit.GetSelection()]
        self.choice_endian.Enable(self.unit_size > 1)
        self.configure_columns()
        self.populate_table()

    def on_endian_change(self, _evt):
        self.endianness = "little" if self.choice_endian.GetSelection() == 0 else "big"
        self.list_ctrl.Refresh()

    def on_goto(self, _evt):
        raw = self.combo_goto.GetValue().strip()
        if not raw:
            return
        try:
            target = int(raw, 0)
            if target < 0:
                raise ValueError()
        except ValueError:
            wx.MessageBox("Invalid address.\nUse decimal (32768) or hex (0x8000).",
                          "Invalid Address", wx.OK | wx.ICON_WARNING)
            return
        if not self.row_bases:
            wx.MessageBox("No file loaded.", "Go To Address", wx.OK | wx.ICON_INFORMATION)
            return
        row_base = target & ~0x0F
        match = bisect_left(self.row_bases, row_base)
        if match >= len(self.row_bases):
            wx.MessageBox(f"Address 0x{target:08X} is beyond the end of the file.",
                          "Go To Address", wx.OK | wx.ICON_INFORMATION)
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

    # -- Virtual list population --

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

        t2 = perf_counter()
        self.list_ctrl.Freeze()
        try:
            self.list_ctrl.SetItemCount(len(self.row_bases))
            self.list_ctrl.Refresh()
        finally:
            self.list_ctrl.Thaw()

        t3 = perf_counter()
        if PROFILE:
            print(f"populate_table: prep1={t1-t0:.3f}s  prep2={t2-t1:.3f}s  ui={t3-t2:.3f}s  total={t3-t0:.3f}s")

    def get_cell_text(self, item: int, col: int) -> str:
        if item < 0 or item >= len(self.row_bases):
            return ""
        row_base  = self.row_bases[item]
        cols      = 16 // self.unit_size
        ascii_col = cols + 1
        mem       = self.mem

        if col == 0:
            addr = f"{row_base:08X}"
            return f"{addr[:4]}_{addr[4:]}"

        if col == ascii_col:
            chars = []
            for i in range(16):
                b = mem.get(row_base + i)
                chars.append(" " if b is None else (chr(b) if 32 <= b <= 126 else "."))
            return "".join(chars)

        if 1 <= col <= cols:
            group_start = row_base + (col - 1) * self.unit_size
            vals = [mem.get(group_start + j) for j in range(self.unit_size)]
            if any(v is None for v in vals):
                return "." * (2 * self.unit_size)

            if self.unit_size > 1 and self.endianness == "little":
                vals = list(reversed(vals))

            return "".join(f"{v:02X}" for v in vals)

        return ""


class HexViewerApp(wx.App):
    def OnInit(self):
        frame = MainFrame()
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
    app = HexViewerApp(False)
    app.MainLoop()