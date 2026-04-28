# Merge Tool — User Guide

---

## Table of Contents

1. [Overview](#overview)
2. [Requirements](#requirements)
3. [Starting the Program](#starting)
4. [Input File Table](#table)
5. [Adding Files](#adding)
6. [File Type and Defaults](#filetypes)
7. [Reordering Rows](#reorder)
8. [Output Settings](#output)
9. [Merging](#merging)
10. [Warnings](#warnings)
11. [Tips](#tips)

---

## 1. Overview <a name="overview"></a>

Merge Tool combines multiple Intel HEX and/or binary (BIN) files into a single output file.  
Each input file can be added multiple times with different offsets or block ranges.  
The output can be saved as Intel HEX or binary.

---

## 2. Requirements <a name="requirements"></a>

- Windows 7 or later (64-bit recommended)
- Python 3.8+ with `wxPython` and `intelhex` installed, **or** use the pre-built `merge_tool.exe`

```bash
pip install wxPython intelhex
```

---

## 3. Starting the Program <a name="starting"></a>

Run from source:

```bash
python merge_tool.py
```

Or double-click `merge_tool.exe` if using the compiled build.

---

## 4. Input File Table <a name="table"></a>

| Column | Description |
|---|---|
| **Use** | Check to include this row in merge. Uncheck to skip. |
| **Type** | `auto`, `hex`, or `bin`. `auto` detects by extension. |
| **File** | Full input path. Long paths wrap in-cell. |
| **Target Offset** | Base address in merged output. HEX is auto-filled from file. BIN defaults to `0x0`. |
| **Block Start** | Byte offset in source file where reading starts. Default `0x0`. |
| **Block Length** | Number of bytes to read. For BIN, default is full remaining file length. |

---

## 5. Adding Files <a name="adding"></a>

### A. Browse Button
1. Select a row (or click **Add Row**).
2. Click **Browse File…**.
3. Select a file.

### B. Drag and Drop onto Table
- Drop files onto a specific row.
- Files are inserted at that row.

### C. Drag and Drop onto Window/Log
- Drop files outside the grid.
- Files are appended at the end.

---

## 6. File Type and Defaults <a name="filetypes"></a>

### Intel HEX (`.hex`, `.ihx`, `.ihex`)
- Addresses come from HEX file records.
- Offset/start/length are shown for reference.
- Merge uses HEX file addresses as-is.

### Binary (`.bin`)
- No embedded addresses.
- `Target Offset` defines where data is placed.
- `Block Start` and `Block Length` define selected data region.

| Field | HEX default | BIN default |
|---|---|---|
| Target Offset | Auto (from file) | `0x0` |
| Block Start | Auto (from file) | `0x0` |
| Block Length | Auto (byte count) | Full file from Block Start |

Numeric formats accepted: decimal (`65536`), hex (`0x10000`), or hex with `h` suffix (`10000h`).

---

## 7. Reordering Rows <a name="reorder"></a>

Merge runs from top to bottom.

- Use **Move Up** / **Move Down** to reorder.
- If addresses overlap, lower rows overwrite higher rows (after confirmation).

---

## 8. Output Settings <a name="output"></a>

### Merge Target (required)
- Choose output path via **Browse…** or drag-drop to target field.
- `.hex/.ihx/.ihex` => HEX output.
- Other extensions (for example `.bin`) => binary output.

### BIN Start Address (binary output only)
- Lowest address to write.
- Blank = auto (lowest merged address).

### Fill Byte (binary output only)
- Gap fill value, default `0xFF`.

---

## 9. Merging <a name="merging"></a>

1. Add and configure input rows.
2. Set output path.
3. Click **Merge**.
4. Review log summary.
5. Confirm success dialog.

---

## 10. Warnings <a name="warnings"></a>

| Warning | Meaning | Action |
|---|---|---|
| Address overlap | Multiple rows write same address | Continue to overwrite, or cancel |
| Output file already has data | Target exists and not empty | Overwrite or cancel |
| File not found | Input path invalid | Fix path or disable row |
| Block exceeds file size | Start + length invalid | Correct block settings |

---

## 11. Tips <a name="tips"></a>

- Same file can be added multiple times.
- Use **Use** checkbox to temporarily disable rows.
- Widen **File** column for easier reading.
- Build command:

```bash
python -m PyInstaller build.spec --clean
```

---

*© 2026 wxpython_intelhex_viewer project*