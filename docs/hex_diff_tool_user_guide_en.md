# HEX/BIN Byte Diff Tool — User Guide

## 1) Overview
`hex_diff_tool` compares two files byte-by-byte:

- Intel HEX: `.hex`, `.ihex`, `.ihx`
- Binary: `.bin`

It shows:
- hex bytes and ASCII view
- highlighted byte differences
- diff navigation (next/previous)
- bit transition statistics (`0→1`, `1→0`)

---

## 2) Start the Tool

### From source
```bash
python hex_diff_tool.py
```

### From packaged app
Run `hex_diff_tool.exe`.

---

## 3) Main UI

- **Open Left... / Open Right...**: load files
- **Only differences**: show only rows containing differences
- **Range [start, stop)**: compare only selected address range (hex input)
- **Diff navigation buttons**: first / previous / next / last
- **Refresh**: rebuild view
- **Reload / Close per side**: reload file or clear one side
- **Right mini-map strip**: overview of diff locations, clickable/draggable viewport
- **Status bar**: range, rows, compared bytes, diff count, navigation hints
- **Bit changes bar**: counts changed bits (`0→1`, `1→0`, total)

---

## 4) Loading Files

### Open dialogs
Use **Open Left...** and **Open Right...**.

### Drag and drop
- Drop onto left pane: loads LEFT
- Drop onto right pane: loads RIGHT
- Drop onto window background:
  - if 2+ files dropped: first -> LEFT, second -> RIGHT
  - if 1 file dropped: fills LEFT first, then RIGHT

### BIN offset prompt
When loading `.bin`, the tool asks for load offset (decimal or hex, e.g. `0x8000`).
That offset maps file byte index to memory address.

---

## 5) Compare Range

Range is `[start, stop)`:
- Start included
- Stop excluded

Input supports hex (with or without `0x`), for example:
- `8000`
- `0x8000`

Rules:
- blank start/end = unbounded side
- stop must be greater than start

---

## 6) Reading the Diff View

Each line is 16 bytes:

`AAAAAAAA: xx xx ... xx  |ASCII........|`

- `AAAAAAAA`: base address
- `xx`: byte value
- `..`: missing/unavailable byte
- red highlight: difference
- blue marker: current selected difference

ASCII area is also highlighted for differing bytes.

---

## 7) Navigation

- Buttons: first / prev / next / last diff
- Keyboard:
  - `F7`: next diff
  - `Shift+F7`: previous diff
  - `Arrow Right/Down`, `PageDown`: next diff
  - `Arrow Left/Up`, `PageUp`: previous diff

---

## 8) Only Differences Mode

When **Only differences** is enabled:
- rows with no byte difference are hidden
- rows with at least one differing byte remain

---

## 9) Bit Change Statistics

Shown as:

`Bit changes: 0→1: N bits    1→0: M bits    Total: T`

Counts are computed only where both sides have bytes and values differ, within active range.

---

## 10) Reload and Close

- **Reload**: re-read the same file from disk
- **Close (✕)**: clear one side and keep the other side visible

Useful for iterative firmware rebuild and re-compare.

---

## 11) Common Errors

- **Unsupported file type**: use `.hex/.ihex/.ihx/.bin`
- **Invalid BIN offset**: enter decimal or hex (`0x...`)
- **Invalid range**: use hex values; ensure `stop > start`
- **Load failed**: file missing, access issue, or malformed HEX

---

## 12) Tips

- Use drag-and-drop for fast compare cycles.
- Use range filtering to focus on bootloader/app regions.
- Use **Only differences** for large sparse images.
- Click/drag mini-map on right to jump quickly across diff lines.