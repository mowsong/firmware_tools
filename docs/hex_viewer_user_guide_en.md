# Intel HEX Viewer — User Guide

---

## Table of Contents

1. [Overview](#overview)
2. [Requirements](#requirements)
3. [Starting the Program](#starting)
4. [Main Interface](#ui)
5. [Opening a File](#opening)
6. [Viewing Data](#viewing)
7. [Go To Address](#goto)
8. [Refresh](#refresh)
9. [CRC Functions](#crc)
10. [Keyboard Shortcuts](#keyboard)
11. [Tips](#tips)

---

## 1. Overview <a name="overview"></a>

Intel HEX Viewer displays the contents of Intel HEX and binary files in a
hex dump table. Each row shows 16 bytes with address, grouped hex values,
and ASCII representation.

It also provides:
- Byte grouping (1 / 2 / 4 bytes)
- Endianness selection for multi-byte groups
- Go To Address
- File and data CRC32
- Block-aligned CRC16

---

## 2. Requirements <a name="requirements"></a>

- Windows 7 or later (64-bit recommended)
- Python 3.8+ with `wxPython`, `intelhex`, `crcmod` installed,
  or use the pre-built `hex_viewer.exe`

```bash
pip install wxPython intelhex crcmod
```

---

## 3. Starting the Program <a name="starting"></a>

From source:

```bash
python hex_viewer.py
```

Or double-click `hex_viewer.exe`.

---

## 4. Main Interface <a name="ui"></a>

### Toolbar Row 1

| Control | Description |
|---|---|
| **Open...** | Open a HEX or BIN file via dialog |
| **Refresh** | Reload from disk (skips if file unchanged) |
| **1 byte / 2 bytes / 4 bytes** | Byte grouping for hex columns |
| **Little-endian / Big-endian** | Byte order for 2/4-byte groups |
| **Data CRC32** | CRC32 over data bytes only |
| **File CRC32** | CRC32 over the raw file bytes |

### Toolbar Row 2 — Block-aligned CRC16

| Control | Description |
|---|---|
| **Start** | Start address (inclusive), must be a multiple of block size |
| **Stop** | Stop address (exclusive) |
| **Block size** | Alignment block size (default `0x100`) |
| **Pad** | Fill byte for missing addresses (default `0xFF`) |
| **Block-aligned CRC16** | Compute and display CRC16 |

### Hex Table

Each row: `AAAAAAAA: xx xx ... xx  ASCII`

- `AAAAAAAA` — row base address (formatted as `AAAA_AAAA`)
- `xx` — byte value in hex (or `..` if no data at that address)
- `ASCII` — printable characters, `.` for non-printable or missing

### Status Bar
Shows current file path or action result.

---

## 5. Opening a File <a name="opening"></a>

### Via Button
Click **Open...** and select a `.hex`, `.ihex`, `.ihx`, or `.bin` file.

### Via Drag and Drop
Drag any supported file and drop anywhere on the window.

### BIN Offset
When opening a `.bin` file, the tool asks for a **load offset**
(decimal or hex, e.g. `0x8000`).  
This maps the first byte of the file to that memory address.

---

## 6. Viewing Data <a name="viewing"></a>

### Byte Grouping
Select **1 byte**, **2 bytes**, or **4 bytes** from the dropdown.  
In 1-byte mode the endianness selector is disabled.

### Endianness
Active only for 2-byte or 4-byte grouping.

- **Little-endian**: bytes are reversed before display (common for ARM/x86)
- **Big-endian**: bytes are shown in file order

### Missing Bytes
Addresses with no data show as `..` in hex and a space in ASCII.
This is normal for sparse HEX files.

---

## 7. Go To Address <a name="goto"></a>

Type a target address in the **Go To** combo box and press Enter
(or click the button).

- Accepts decimal (`65536`) or hex (`0x10000`)
- The view scrolls and selects the corresponding row
- Last 20 addresses are kept in the history dropdown

---

## 8. Refresh <a name="refresh"></a>

Press **Refresh** or `F5` to reload the current file from disk.

- If the raw file bytes have not changed (CRC32 match), the reload is
  skipped and a "No changes" message is shown briefly.
- If the file has changed, it is re-parsed and the table is updated.
- For BIN files, the previously entered offset is reused automatically.

---

## 9. CRC Functions <a name="crc"></a>

### Data CRC32
Computed over all data bytes present in the HEX/BIN file,
in address order. Shown in toolbar row 1.

### File CRC32
Computed over the raw bytes of the file as stored on disk.
Shown in toolbar row 1.

### Block-aligned CRC16
CRC16 (CRC-CCITT / polynomial `0x11021`) over a selected address range,
padded to a block boundary.

**Steps:**
1. Enter **Start** (must be a multiple of block size).
2. Enter **Stop** (exclusive, must be > start).
3. Enter **Block size** (default `0x100`).
4. Enter **Pad** byte for missing addresses (default `0xFF`).
5. Click **Block-aligned CRC16**.
6. Result is shown as: `0xABCD (0xSTART-0xEND)`

**Notes:**
- Start/Stop are auto-filled when a file is loaded (snapped to block
  boundaries of the file's actual data range).
- Stop is the address one past the last data byte.

---

## 10. Keyboard Shortcuts <a name="keyboard"></a>

| Key | Action |
|---|---|
| `F5` | Refresh file from disk |

---

## 11. Tips <a name="tips"></a>

- Drag a file directly onto the window for the fastest open.
- Use 2-byte or 4-byte grouping to read word/dword values naturally.
- The **Data CRC32** and **File CRC32** differ for HEX files because
  HEX files contain record overhead bytes not counted in Data CRC32.
- For BIN files both CRC32 values are the same.
- Use **Block-aligned CRC16** to reproduce embedded firmware CRCs that
  pad to flash page boundaries.

---

*© 2026 wxpython_intelhex_viewer project*