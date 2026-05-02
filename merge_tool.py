import os
from pathlib import Path

import wx
import wx.grid as gridlib
from wx.lib.wordwrap import wordwrap
from intelhex import IntelHex
import ctypes
from version import __version_merge__ as __version__


COL_ENABLED = 0
COL_TYPE = 1
COL_FILE = 2
COL_OFFSET = 3
COL_BLOCK_START = 4
COL_BLOCK_LENGTH = 5


class FileDropTarget(wx.FileDropTarget):
    def __init__(self, callback, source=None):
        super().__init__()
        self.callback = callback
        self.source = source

    def OnDropFiles(self, x, y, filenames):
        return bool(self.callback(x, y, filenames, self.source))


class MergeFrame(wx.Frame):
    def __init__(self):
        super().__init__(None, title=f"Intel HEX / Binary Merge Tool v{__version__}", size=(1100, 700))
        self._set_app_icon()
        self._build_ui()
        self.Centre()

    def _set_app_icon(self):
        icon_path = Path(__file__).resolve().parent / "icons" / "merge_tool.ico"
        if icon_path.is_file():
            self.SetIcon(wx.Icon(str(icon_path), wx.BITMAP_TYPE_ICO))

    def _build_ui(self):
        panel = wx.Panel(self)
        root = wx.BoxSizer(wx.VERTICAL)

        info1 = wx.StaticText(
            panel,
            label=(
                "Add one row per merge input. HEX rows use file addresses. "
                "BIN rows require a target offset and can optionally specify a block. "
            ),
        )
        root.Add(info1, 0, wx.ALL | wx.EXPAND, 8)

        # make the static text font bigger
        font = info1.GetFont()
        font.SetPointSize(font.GetPointSize() + 2)
        info1.SetFont(font)
        
        info2 = wx.StaticText(
            panel,
            label=(
                "Files can also be dragged onto the table or window."
            ),
            
        )
        root.Add(info2, 0, wx.ALL | wx.EXPAND, 8)
        # make the static text font bigger
        font = info2.GetFont()
        font.SetPointSize(font.GetPointSize() + 2)
        info2.SetFont(font)
        
        self.grid = gridlib.Grid(panel)
        self.grid.CreateGrid(0, 6)
        self.grid.SetDefaultCellAlignment(wx.ALIGN_LEFT, wx.ALIGN_TOP)
        self.grid.SetDefaultRowSize(24, resizeExistingRows=True)

        # Make row-number area narrow (just enough for row indices)
        self._fit_row_label_width()

        self.grid.SetColLabelValue(COL_ENABLED, "Use")
        self.grid.SetColLabelValue(COL_TYPE, "Type")
        self.grid.SetColLabelValue(COL_FILE, "File")
        self.grid.SetColLabelValue(COL_OFFSET, "Target Offset")
        self.grid.SetColLabelValue(COL_BLOCK_START, "Block Start")
        self.grid.SetColLabelValue(COL_BLOCK_LENGTH, "Block Length")

        self.grid.SetColFormatBool(COL_ENABLED)

        # Center-align checkbox cells in the "Use" column
        enabled_attr = gridlib.GridCellAttr()
        enabled_attr.SetEditor(gridlib.GridCellBoolEditor())
        enabled_attr.SetRenderer(gridlib.GridCellBoolRenderer())
        enabled_attr.SetAlignment(wx.ALIGN_CENTER, wx.ALIGN_CENTER)
        self.grid.SetColAttr(COL_ENABLED, enabled_attr)

        self.grid.SetColSize(COL_ENABLED, 60)
        self.grid.SetColSize(COL_TYPE, 80)
        self.grid.SetColSize(COL_FILE, 460)
        self.grid.SetColSize(COL_OFFSET, 120)
        self.grid.SetColSize(COL_BLOCK_START, 120)
        self.grid.SetColSize(COL_BLOCK_LENGTH, 120)

        root.Add(self.grid, 1, wx.ALL | wx.EXPAND, 8)

        grid_buttons = wx.BoxSizer(wx.HORIZONTAL)
        add_btn = wx.Button(panel, label="Add Row")
        del_btn = wx.Button(panel, label="Remove Row")
        up_btn = wx.Button(panel, label="Move Up")
        down_btn = wx.Button(panel, label="Move Down")
        browse_btn = wx.Button(panel, label="Browse File...")
        sample_btn = wx.Button(panel, label="Add Sample Rows")
        grid_buttons.Add(add_btn, 0, wx.RIGHT, 6)
        grid_buttons.Add(del_btn, 0, wx.RIGHT, 6)
        grid_buttons.Add(up_btn, 0, wx.RIGHT, 6)
        grid_buttons.Add(down_btn, 0, wx.RIGHT, 6)
        grid_buttons.Add(browse_btn, 0, wx.RIGHT, 6)
        grid_buttons.Add(sample_btn, 0)
        root.Add(grid_buttons, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        output_box = wx.StaticBoxSizer(wx.StaticBox(panel, label="Output"), wx.VERTICAL)

        out_row = wx.BoxSizer(wx.HORIZONTAL)
        out_row.Add(wx.StaticText(panel, label="Merge Target"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        self.output_path = wx.TextCtrl(panel)
        out_row.Add(self.output_path, 1, wx.RIGHT, 6)
        out_browse_btn = wx.Button(panel, label="Browse...")
        out_row.Add(out_browse_btn, 0)
        output_box.Add(out_row, 0, wx.ALL | wx.EXPAND, 8)

        bin_row = wx.BoxSizer(wx.HORIZONTAL)
        bin_row.Add(wx.StaticText(panel, label="BIN Start Address"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        self.bin_start = wx.TextCtrl(panel, value="")
        bin_row.Add(self.bin_start, 0, wx.RIGHT, 16)

        bin_row.Add(wx.StaticText(panel, label="Fill Byte"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        self.fill_byte = wx.TextCtrl(panel, value="0xFF")
        bin_row.Add(self.fill_byte, 0)
        output_box.Add(bin_row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        root.Add(output_box, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

        self.log = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL)
        root.Add(self.log, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

        action_row = wx.BoxSizer(wx.HORIZONTAL)
        merge_btn = wx.Button(panel, label="Merge")
        close_btn = wx.Button(panel, label="Close")
        action_row.AddStretchSpacer(1)
        action_row.Add(merge_btn, 0, wx.RIGHT, 6)
        action_row.Add(close_btn, 0)
        root.Add(action_row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

        panel.SetSizer(root)

        self.grid_window = self.grid.GetGridWindow()
        self.grid_window.SetDropTarget(FileDropTarget(self.on_drop_input_files, self.grid_window))
        panel.SetDropTarget(FileDropTarget(self.on_drop_input_files, panel))
        self.log.SetDropTarget(FileDropTarget(self.on_drop_input_files, self.log))
        self.output_path.SetDropTarget(FileDropTarget(self.on_drop_output_file, self.output_path))

        add_btn.Bind(wx.EVT_BUTTON, self.on_add_row)
        del_btn.Bind(wx.EVT_BUTTON, self.on_remove_row)
        up_btn.Bind(wx.EVT_BUTTON, self.on_move_up)
        down_btn.Bind(wx.EVT_BUTTON, self.on_move_down)
        browse_btn.Bind(wx.EVT_BUTTON, self.on_browse_input)
        sample_btn.Bind(wx.EVT_BUTTON, self.on_add_sample_rows)
        out_browse_btn.Bind(wx.EVT_BUTTON, self.on_browse_output)
        merge_btn.Bind(wx.EVT_BUTTON, self.on_merge)
        close_btn.Bind(wx.EVT_BUTTON, lambda evt: self.Close())

        self.grid.Bind(gridlib.EVT_GRID_CELL_CHANGED, self.on_grid_cell_changed)
        self.grid.Bind(gridlib.EVT_GRID_COL_SIZE, self.on_grid_col_size)
        self.Bind(wx.EVT_SIZE, self.on_frame_size)

        for _ in range(4):
            self.add_row()

        wx.CallAfter(self._refresh_all_row_heights)

    def _fit_row_label_width(self):
        rows = max(1, self.grid.GetNumberRows())
        digits = len(str(rows))
        dc = wx.ClientDC(self.grid.GetGridWindow())
        dc.SetFont(self.grid.GetLabelFont())
        text_w, _ = dc.GetTextExtent("9" * digits)
        self.grid.SetRowLabelSize(max(24, text_w + 10))
        
    def _set_row_values(self, row, file_path="", file_type="auto", offset="", block_start="", block_length="", enabled=True):
        self.grid.SetCellEditor(row, COL_TYPE, gridlib.GridCellChoiceEditor(["auto", "hex", "bin"]))
        self.grid.SetCellRenderer(row, COL_FILE, gridlib.GridCellAutoWrapStringRenderer())
        self.grid.SetCellAlignment(row, COL_FILE, wx.ALIGN_LEFT, wx.ALIGN_TOP)

        # Defaults for BIN rows:
        # - offset: 0
        # - block_start: 0
        # - block_length: blank => entire file
        if (file_type or "").strip().lower() == "bin":
            if not str(offset).strip():
                offset = "0x0"
            if not str(block_start).strip():
                block_start = "0x0"

        self.grid.SetCellValue(row, COL_ENABLED, "1" if enabled else "")
        self.grid.SetCellValue(row, COL_TYPE, file_type)
        self.grid.SetCellValue(row, COL_FILE, file_path)
        self.grid.SetCellValue(row, COL_OFFSET, offset)
        self.grid.SetCellValue(row, COL_BLOCK_START, block_start)
        self.grid.SetCellValue(row, COL_BLOCK_LENGTH, block_length)

        self._apply_file_defaults_for_row(row)
        self._update_row_height(row)

    def _apply_file_defaults_for_row(self, row):
        if row < 0 or row >= self.grid.GetNumberRows():
            return

        path = self.grid.GetCellValue(row, COL_FILE).strip()
        if not path or not os.path.isfile(path):
            return

        configured = self.grid.GetCellValue(row, COL_TYPE).strip().lower() or "auto"
        file_type = self.detect_type(path, configured)

        if file_type == "bin":
            if not self.grid.GetCellValue(row, COL_OFFSET).strip():
                self.grid.SetCellValue(row, COL_OFFSET, "0x0")
            if not self.grid.GetCellValue(row, COL_BLOCK_START).strip():
                self.grid.SetCellValue(row, COL_BLOCK_START, "0x0")

            # Show default block length for BIN (entire file from block_start)
            if not self.grid.GetCellValue(row, COL_BLOCK_LENGTH).strip():
                file_size = os.path.getsize(path)
                try:
                    block_start = self.parse_int(
                        self.grid.GetCellValue(row, COL_BLOCK_START),
                        "block start",
                        allow_blank=True,
                        default=0,
                    )
                except Exception:
                    block_start = 0

                remaining = max(0, file_size - max(0, block_start))
                self.grid.SetCellValue(row, COL_BLOCK_LENGTH, str(remaining))
            return

        # HEX: show derived values in offset/start/length columns
        try:
            ih = IntelHex(path)
            addresses = ih.addresses()
        except Exception:
            return

        if not addresses:
            self.grid.SetCellValue(row, COL_OFFSET, "0x0")
            self.grid.SetCellValue(row, COL_BLOCK_START, "0x0")
            self.grid.SetCellValue(row, COL_BLOCK_LENGTH, "0")
            return

        start = min(addresses)
        length = len(addresses)  # actual byte count present in HEX data

        self.grid.SetCellValue(row, COL_OFFSET, f"0x{start:X}")
        self.grid.SetCellValue(row, COL_BLOCK_START, f"0x{start:X}")
        self.grid.SetCellValue(row, COL_BLOCK_LENGTH, str(length))

    def _update_row_height(self, row):
        if row < 0 or row >= self.grid.GetNumberRows():
            return

        text = self.grid.GetCellValue(row, COL_FILE)
        dc = wx.ClientDC(self.grid.GetGridWindow())
        dc.SetFont(self.grid.GetDefaultCellFont())

        wrap_width = max(40, self.grid.GetColSize(COL_FILE) - 8)
        wrapped = wordwrap(text, wrap_width, dc, breakLongWords=True) if text else ""
        line_count = max(1, wrapped.count("\n") + 1)

        _, line_height = dc.GetTextExtent("Ag")
        padding = 8
        needed_height = max(self.grid.GetDefaultRowSize(), line_count * line_height + padding)
        self.grid.SetRowSize(row, needed_height)

    def _refresh_all_row_heights(self):
        for row in range(self.grid.GetNumberRows()):
            self._update_row_height(row)
        self.grid.ForceRefresh()

    def on_grid_cell_changed(self, event):
        row = event.GetRow()
        col = event.GetCol()
        if col in (COL_FILE, COL_TYPE):
            wx.CallAfter(self._apply_file_defaults_for_row, row)
            wx.CallAfter(self._update_row_height, row)
        event.Skip()

    def on_grid_col_size(self, event):
        if event.GetRowOrCol() == COL_FILE:
            wx.CallAfter(self._refresh_all_row_heights)
        event.Skip()

    def on_frame_size(self, event):
        wx.CallAfter(self._refresh_all_row_heights)
        event.Skip()

    def add_row(self, file_path="", file_type="auto", offset="", block_start="", block_length="", enabled=True):
        row = self.grid.GetNumberRows()
        self.grid.AppendRows(1)
        self._set_row_values(row, file_path, file_type, offset, block_start, block_length, enabled)
        self._fit_row_label_width()
        return row

    def insert_row(self, row, file_path="", file_type="auto", offset="", block_start="", block_length="", enabled=True):
        row = max(0, min(row, self.grid.GetNumberRows()))
        self.grid.InsertRows(row, 1)
        self._set_row_values(row, file_path, file_type, offset, block_start, block_length, enabled)
        self._fit_row_label_width()
        return row

    def log_line(self, text):
        self.log.AppendText(text + os.linesep)

    def infer_type_from_path(self, path):
        suffix = Path(path).suffix.lower()
        if suffix in {".hex", ".ihx", ".ihex"}:
            return "hex"
        if suffix == ".bin":
            return "bin"
        return "auto"

    def _drop_row_from_grid_y(self, y):
        _, unscrolled_y = self.grid.CalcUnscrolledPosition(0, y)
        row = self.grid.YToRow(unscrolled_y)
        if row == wx.NOT_FOUND:
            return self.grid.GetNumberRows()
        return row

    def on_drop_input_files(self, x, y, paths, source=None):
        added = 0
        skipped = []

        insert_row = None
        if source is self.grid_window:
            insert_row = self._drop_row_from_grid_y(y)

        for path in paths:
            if not os.path.isfile(path):
                skipped.append(path)
                continue

            if insert_row is None:
                row = self.add_row(
                    file_path=path,
                    file_type=self.infer_type_from_path(path),
                    enabled=True,
                )
            else:
                row = self.insert_row(
                    insert_row,
                    file_path=path,
                    file_type=self.infer_type_from_path(path),
                    enabled=True,
                )
                insert_row += 1

            added += 1

        if added:
            self.grid.ClearSelection()
            target_row = (insert_row - 1) if insert_row is not None else (self.grid.GetNumberRows() - 1)
            if target_row >= 0:
                self.grid.SetGridCursor(target_row, COL_FILE)
                self.grid.SelectRow(target_row)
            self.log_line(f"Added {added} file(s) by drag and drop.")

        if skipped:
            wx.MessageBox(
                "Only files can be dropped here.\n\nSkipped:\n" + "\n".join(skipped[:20]),
                "Drag and drop",
                wx.OK | wx.ICON_WARNING,
            )

        return added > 0

    def on_drop_output_file(self, x, y, paths, source=None):
        for path in paths:
            if os.path.isfile(path):
                self.output_path.SetValue(path)
                self.log_line(f"Output path set by drag and drop: {path}")
                return True

        wx.MessageBox(
            "Drop a file onto Merge Target.",
            "Drag and drop",
            wx.OK | wx.ICON_INFORMATION,
        )
        return False

    def _active_row(self):
        row = self.grid.GetGridCursorRow()
        if row == wx.NOT_FOUND:
            rows = self.grid.GetSelectedRows()
            if rows:
                row = rows[0]
        return row

    def _row_values(self, row):
        return [self.grid.GetCellValue(row, col) for col in range(self.grid.GetNumberCols())]

    def _write_row_values(self, row, values):
        for col, value in enumerate(values):
            self.grid.SetCellValue(row, col, value)
        self._update_row_height(row)

    def _swap_rows(self, row_a, row_b):
        values_a = self._row_values(row_a)
        values_b = self._row_values(row_b)
        self._write_row_values(row_a, values_b)
        self._write_row_values(row_b, values_a)

    def on_move_up(self, _event):
        row = self._active_row()
        if row in (wx.NOT_FOUND, None) or row <= 0:
            return

        self._swap_rows(row, row - 1)
        self.grid.ClearSelection()
        self.grid.SetGridCursor(row - 1, COL_FILE)
        self.grid.SelectRow(row - 1)

    def on_move_down(self, _event):
        row = self._active_row()
        if row in (wx.NOT_FOUND, None) or row >= self.grid.GetNumberRows() - 1:
            return

        self._swap_rows(row, row + 1)
        self.grid.ClearSelection()
        self.grid.SetGridCursor(row + 1, COL_FILE)
        self.grid.SelectRow(row + 1)

    def on_add_row(self, _event):
        self.add_row()

    def on_remove_row(self, _event):
        rows = sorted(set(self.grid.GetSelectedRows()), reverse=True)
        if not rows:
            row = self.grid.GetGridCursorRow()
            if row >= 0:
                rows = [row]

        for row in rows:
            if 0 <= row < self.grid.GetNumberRows():
                self.grid.DeleteRows(row, 1)

        if self.grid.GetNumberRows() == 0:
            self.add_row()

        self._fit_row_label_width()
        wx.CallAfter(self._refresh_all_row_heights)

    def on_browse_input(self, _event):
        row = self.grid.GetGridCursorRow()
        if row < 0:
            wx.MessageBox("Select a row first.", "Input File", wx.OK | wx.ICON_INFORMATION)
            return

        wildcard = (
            "Supported files (*.hex;*.ihx;*.ihex;*.bin)|*.hex;*.ihx;*.ihex;*.bin|"
            "Intel HEX (*.hex;*.ihx;*.ihex)|*.hex;*.ihx;*.ihex|"
            "Binary (*.bin)|*.bin|"
            "All files (*.*)|*.*"
        )
        with wx.FileDialog(self, "Select input file", wildcard=wildcard, style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return

            path = dlg.GetPath()
            self.grid.SetCellValue(row, COL_FILE, path)
            self._update_row_height(row)

            suffix = Path(path).suffix.lower()
            if suffix in {".hex", ".ihx", ".ihex"}:
                self.grid.SetCellValue(row, COL_TYPE, "hex")
            elif suffix == ".bin":
                self.grid.SetCellValue(row, COL_TYPE, "bin")
            else:
                self.grid.SetCellValue(row, COL_TYPE, "auto")

            self._apply_file_defaults_for_row(row)

    def on_browse_output(self, _event):
        wildcard = (
            "Intel HEX (*.hex)|*.hex|"
            "Binary (*.bin)|*.bin|"
            "All files (*.*)|*.*"
        )
        with wx.FileDialog(
            self,
            "Select merge target",
            wildcard=wildcard,
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        ) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                self.output_path.SetValue(dlg.GetPath())

    def on_add_sample_rows(self, _event):
        self.add_row(r"C:\temp\bootloader.hex", "hex", "", "", "", True)
        self.add_row(r"C:\temp\app.bin", "bin", "0x10000", "0x0", "0x4000", True)

    def parse_int(self, value, field_name, allow_blank=False, default=None):
        text = value.strip()
        if not text:
            if allow_blank:
                return default
            raise ValueError(f"{field_name} is required.")

        lower = text.lower()
        if lower.endswith("h"):
            return int(lower[:-1], 16)
        return int(text, 0)

    def row_enabled(self, row):
        value = self.grid.GetCellValue(row, COL_ENABLED).strip().lower()
        return value not in {"", "0", "false", "no"}

    def detect_type(self, path, configured_type):
        if configured_type in {"hex", "bin"}:
            return configured_type

        suffix = Path(path).suffix.lower()
        if suffix in {".hex", ".ihx", ".ihex"}:
            return "hex"
        if suffix == ".bin":
            return "bin"
        raise ValueError(f"Cannot auto-detect file type for: {path}")

    def collect_rows(self):
        entries = []
        for row in range(self.grid.GetNumberRows()):
            if not self.row_enabled(row):
                continue

            path = self.grid.GetCellValue(row, COL_FILE).strip()
            if not path:
                continue

            if not os.path.isfile(path):
                raise ValueError(f"Row {row + 1}: file not found: {path}")

            file_type = self.detect_type(path, self.grid.GetCellValue(row, COL_TYPE).strip().lower() or "auto")

            entry = {
                "row": row + 1,
                "path": path,
                "type": file_type,
            }

            if file_type == "bin":
                entry["offset"] = self.parse_int(
                    self.grid.GetCellValue(row, COL_OFFSET),
                    f"Row {row + 1} target offset",
                    allow_blank=True,
                    default=0,
                )
                entry["block_start"] = self.parse_int(
                    self.grid.GetCellValue(row, COL_BLOCK_START),
                    f"Row {row + 1} block start",
                    allow_blank=True,
                    default=0,
                )
                entry["block_length"] = self.parse_int(
                    self.grid.GetCellValue(row, COL_BLOCK_LENGTH),
                    f"Row {row + 1} block length",
                    allow_blank=True,
                    default=None,
                )
            entries.append(entry)

        if not entries:
            raise ValueError("No enabled input rows were provided.")

        return entries

    def merge_entries(self, entries):
        merged = {}
        overlaps = []
        summary = []

        for entry in entries:
            if entry["type"] == "hex":
                ih = IntelHex(entry["path"])
                addresses = ih.addresses()
                if not addresses:
                    summary.append(f"Row {entry['row']}: HEX {entry['path']} -> no data")
                    continue

                for addr in addresses:
                    new_value = ih[addr]
                    if addr in merged:
                        overlaps.append(
                            f"Row {entry['row']}: address 0x{addr:08X} already has 0x{merged[addr]:02X}, new 0x{new_value:02X}"
                        )
                    merged[addr] = new_value

                summary.append(
                    f"Row {entry['row']}: HEX {entry['path']} -> {len(addresses)} bytes at 0x{min(addresses):08X}-0x{max(addresses):08X}"
                )
                continue

            with open(entry["path"], "rb") as f:
                data = f.read()

            block_start = entry["block_start"]
            if block_start < 0:
                raise ValueError(f"Row {entry['row']}: block start must be >= 0.")
            if block_start > len(data):
                raise ValueError(
                    f"Row {entry['row']}: block start 0x{block_start:X} is beyond file size 0x{len(data):X}."
                )

            if entry["block_length"] is None:
                block_end = len(data)
            else:
                if entry["block_length"] < 0:
                    raise ValueError(f"Row {entry['row']}: block length must be >= 0.")
                block_end = block_start + entry["block_length"]

            if block_end > len(data):
                raise ValueError(
                    f"Row {entry['row']}: requested block exceeds file size. "
                    f"End=0x{block_end:X}, Size=0x{len(data):X}."
                )

            chunk = data[block_start:block_end]
            for index, byte_value in enumerate(chunk):
                addr = entry["offset"] + index
                if addr in merged:
                    overlaps.append(
                        f"Row {entry['row']}: address 0x{addr:08X} already has 0x{merged[addr]:02X}, new 0x{byte_value:02X}"
                    )
                merged[addr] = byte_value

            if chunk:
                summary.append(
                    f"Row {entry['row']}: BIN {entry['path']} -> {len(chunk)} bytes from "
                    f"file[0x{block_start:X}:0x{block_end:X}] to 0x{entry['offset']:08X}-0x{entry['offset'] + len(chunk) - 1:08X}"
                )
            else:
                summary.append(f"Row {entry['row']}: BIN {entry['path']} -> empty block")

        if not merged:
            raise ValueError("No data was merged.")

        return merged, overlaps, summary

    def warn_for_overlaps(self, overlaps):
        if not overlaps:
            return True

        preview_count = 20
        preview = overlaps[:preview_count]
        message = (
            f"The merge target already contains data at {len(overlaps)} address(es).\n\n"
            + "\n".join(preview)
        )
        if len(overlaps) > preview_count:
            message += f"\n... and {len(overlaps) - preview_count} more."

        message += "\n\nContinue and let later rows overwrite earlier rows?"

        dlg = wx.MessageDialog(
            self,
            message,
            "Address overlap warning",
            style=wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
        )
        try:
            return dlg.ShowModal() == wx.ID_YES
        finally:
            dlg.Destroy()

    def warn_if_output_has_data(self, out_path):
        if not os.path.exists(out_path):
            return True

        try:
            size = os.path.getsize(out_path)
        except OSError:
            size = 0

        if size <= 0:
            return True

        dlg = wx.MessageDialog(
            self,
            f"The merge target already exists and has {size} byte(s).\n\nOverwrite it?",
            "Output file warning",
            style=wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
        )
        try:
            return dlg.ShowModal() == wx.ID_YES
        finally:
            dlg.Destroy()

    def write_output(self, out_path, merged):
        suffix = Path(out_path).suffix.lower()

        if suffix in {".hex", ".ihx", ".ihex"}:
            ih = IntelHex()
            for addr, value in merged.items():
                ih[addr] = value
            ih.write_hex_file(out_path)
            return f"Wrote HEX: {out_path}"

        fill = self.parse_int(self.fill_byte.GetValue(), "Fill byte", allow_blank=True, default=0xFF)
        if not (0 <= fill <= 0xFF):
            raise ValueError("Fill byte must be in range 0..255.")

        min_addr = min(merged.keys())
        max_addr = max(merged.keys())
        start_addr = self.parse_int(
            self.bin_start.GetValue(),
            "BIN start address",
            allow_blank=True,
            default=min_addr,
        )

        if start_addr > max_addr:
            raise ValueError("BIN start address is beyond the highest merged address.")

        with open(out_path, "wb") as f:
            for addr in range(start_addr, max_addr + 1):
                f.write(bytes([merged.get(addr, fill)]))

        return f"Wrote BIN: {out_path} (0x{start_addr:08X}-0x{max_addr:08X}, fill=0x{fill:02X})"

    def on_merge(self, _event):
        self.log.Clear()

        try:
            out_path = self.output_path.GetValue().strip()
            if not out_path:
                raise ValueError("Merge target is required.")

            entries = self.collect_rows()
            merged, overlaps, summary = self.merge_entries(entries)

            for line in summary:
                self.log_line(line)

            self.log_line(f"Total merged bytes: {len(merged)}")
            self.log_line(f"Address range: 0x{min(merged.keys()):08X}-0x{max(merged.keys()):08X}")

            if not self.warn_for_overlaps(overlaps):
                self.log_line("Merge cancelled due to address overlap.")
                return

            if not self.warn_if_output_has_data(out_path):
                self.log_line("Merge cancelled because output file already has data.")
                return

            result = self.write_output(out_path, merged)
            self.log_line(result)
            wx.MessageBox(result, "Merge complete", wx.OK | wx.ICON_INFORMATION)

        except Exception as exc:
            self.log_line(f"Error: {exc}")
            wx.MessageBox(str(exc), "Merge failed", wx.OK | wx.ICON_ERROR)


class MergeApp(wx.App):
    def OnInit(self):
        frame = MergeFrame()
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
    app = MergeApp(False)
    app.MainLoop()