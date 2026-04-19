import os
import io
import cProfile
import pstats
from time import perf_counter

import wx
import wx.lib.mixins.listctrl as listmix
from intelhex import IntelHex, HexRecordError


PROFILE = True


class HexListCtrl(wx.ListCtrl, listmix.ListCtrlAutoWidthMixin):
    def __init__(self, parent):
        super().__init__(parent, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        listmix.ListCtrlAutoWidthMixin.__init__(self)


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
        self.goto_history: list[str] = []  # recent addresses for ComboBox

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

        # Go To Address ComboBox
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

        self.list_ctrl = HexListCtrl(panel)

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

        self.CreateStatusBar()
        self.SetStatusText("Open an Intel HEX or BIN file (or drag & drop)")


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
            end = start + self.unit_size - 1
            label = f"{start:02X}" if self.unit_size == 1 else f"{start:02X}-{end:02X}"
            self.list_ctrl.InsertColumn(c + 1, label, width=col_width)

        self.list_ctrl.InsertColumn(cols + 1, "ASCII", width=180)

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

        if self.ih is None:
            wx.MessageBox("No file loaded.", "Go To Address", wx.OK | wx.ICON_INFORMATION)
            return

        # Align target to row base
        row_base = target & ~0x0F
        row_bases = sorted({a & ~0x0F for a in self.ih.addresses()})

        # Find the closest row at or after target
        match = next((i for i, rb in enumerate(row_bases) if rb >= row_base), None)

        if match is None:
            wx.MessageBox(
                f"Address 0x{target:08X} is beyond the end of the file.",
                "Go To Address",
                wx.OK | wx.ICON_INFORMATION,
            )
            return

        self.list_ctrl.EnsureVisible(match)
        self.list_ctrl.Select(match)
        self.list_ctrl.Focus(match)

        # Save to history (avoid duplicates, keep latest at top)
        formatted = f"0x{target:08X}"
        if formatted in self.goto_history:
            self.goto_history.remove(formatted)
        self.goto_history.insert(0, formatted)
        self.goto_history = self.goto_history[:20]  # keep last 20

        self.combo_goto.Set(self.goto_history)
        self.combo_goto.SetValue(formatted)

        self.SetStatusText(f"Jumped to 0x{target:08X} (row 0x{row_bases[match]:08X})")

    def _load_hex_file(self, path: str) -> bool:
        try:
            ih = IntelHex()
            self._profile_call("load_hex", ih.loadhex, path)
            self.ih = ih
            self._profile_call("populate_table", self.populate_table)
            self.SetStatusText(f"Loaded HEX: {path}")
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
                for i, b in enumerate(data):
                    ih[offset + i] = b
                return ih

            self.ih = self._profile_call("load_bin", build_ih)
            self._profile_call("populate_table", self.populate_table)
            self.SetStatusText(f"Loaded BIN: {path} @ 0x{offset:X} ({len(data)} bytes)")
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
            "Open Intel HEX file",
            wildcard="HEX files (*.hex;*.ihex;*.ihx)|*.hex;*.ihex;*.ihx|All files (*.*)|*.*",
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

        self.list_ctrl.Freeze()
        try:
            self.list_ctrl.DeleteAllItems()
            if self.ih is None:
                return

            addrs = self.ih.addresses()
            if not addrs:
                return

            t1 = perf_counter()

            addr_set = set(addrs)
            row_bases = sorted({a & ~0x0F for a in addrs})  # 16-byte rows
            cols = 16 // self.unit_size
            ascii_col = cols + 1

            t2 = perf_counter()

            for row_base in row_bases:
                idx = self.list_ctrl.InsertItem(self.list_ctrl.GetItemCount(), f"0x{row_base:08X}")
                ascii_chars = []

                for col in range(cols):
                    group_start = row_base + (col * self.unit_size)
                    group_bytes = []
                    all_present = True

                    for j in range(self.unit_size):
                        addr = group_start + j
                        if addr in addr_set:
                            group_bytes.append(self.ih[addr])
                        else:
                            all_present = False
                            group_bytes.append(None)

                    if all_present:
                        val = "".join(f"{b:02X}" for b in group_bytes if b is not None)
                        self.list_ctrl.SetItem(idx, col + 1, val)
                    else:
                        self.list_ctrl.SetItem(idx, col + 1, "." * (2 * self.unit_size))

                for i in range(16):
                    addr = row_base + i
                    if addr in addr_set:
                        b = self.ih[addr]
                        ascii_chars.append(chr(b) if 32 <= b <= 126 else ".")
                    else:
                        ascii_chars.append(" ")

                self.list_ctrl.SetItem(idx, ascii_col, "".join(ascii_chars))

            t3 = perf_counter()
        finally:
            self.list_ctrl.Thaw()

        if PROFILE:
            print(
                f"populate_table timings: "
                f"prep1={t1 - t0:.3f}s, "
                f"prep2={t2 - t1:.3f}s, "
                f"ui={t3 - t2:.3f}s, "
                f"total={t3 - t0:.3f}s"
            )


class HexViewerApp(wx.App):
    def OnInit(self):
        frame = MainFrame()
        frame.Show()
        return True


if __name__ == "__main__":
    app = HexViewerApp(False)
    app.MainLoop()