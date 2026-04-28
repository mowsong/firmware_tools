# Intel HEX 查看器 — 用户指南

---

## 目录

1. [概述](#overview)
2. [系统要求](#requirements)
3. [启动程序](#starting)
4. [主界面说明](#ui)
5. [打开文件](#opening)
6. [查看数据](#viewing)
7. [跳转地址](#goto)
8. [刷新](#refresh)
9. [CRC 功能](#crc)
10. [键盘快捷键](#keyboard)
11. [使用技巧](#tips)

---

## 1. 概述 <a name="overview"></a>

Intel HEX 查看器以 Hex Dump 表格形式显示 Intel HEX 和二进制文件的内容。
每行显示 16 个字节，包含地址、十六进制值和 ASCII 表示。

功能包括：
- 字节分组（1 / 2 / 4 字节）
- 多字节分组的字节序选择
- 跳转到指定地址
- 文件 CRC32 与数据 CRC32
- 块对齐 CRC16 计算

---

## 2. 系统要求 <a name="requirements"></a>

- Windows 7 或更高版本（建议 64 位）
- Python 3.8+，并安装 `wxPython`、`intelhex`、`crcmod`，
  或直接使用已编译的 `hex_viewer.exe`

```bash
pip install wxPython intelhex crcmod
```

---

## 3. 启动程序 <a name="starting"></a>

源码运行：

```bash
python hex_viewer.py
```

或双击 `hex_viewer.exe`。

---

## 4. 主界面说明 <a name="ui"></a>

### 工具栏第一行

| 控件 | 说明 |
|---|---|
| **Open...** | 通过对话框打开 HEX 或 BIN 文件 |
| **Refresh** | 从磁盘重新加载（文件未变化时跳过） |
| **1 byte / 2 bytes / 4 bytes** | 十六进制列的字节分组 |
| **Little-endian / Big-endian** | 2/4 字节分组的字节序 |
| **Data CRC32** | 仅对数据字节计算的 CRC32 |
| **File CRC32** | 对原始文件字节计算的 CRC32 |

### 工具栏第二行 — 块对齐 CRC16

| 控件 | 说明 |
|---|---|
| **Start** | 起始地址（含），必须是块大小的整数倍 |
| **Stop** | 结束地址（不含） |
| **Block size** | 块对齐大小（默认 `0x100`） |
| **Pad** | 缺失地址的填充字节（默认 `0xFF`） |
| **Block-aligned CRC16** | 计算并显示 CRC16 |

### 十六进制表格

每行格式：`AAAAAAAA: xx xx ... xx  ASCII`

- `AAAAAAAA` — 行基地址（显示为 `AAAA_AAAA` 格式）
- `xx` — 字节十六进制值（无数据则显示 `..`）
- `ASCII` — 可打印字符，不可打印或无数据显示 `.`

### 状态栏
显示当前文件路径或操作结果。

---

## 5. 打开文件 <a name="opening"></a>

### 通过按钮
点击 **Open...** 并选择 `.hex`、`.ihex`、`.ihx` 或 `.bin` 文件。

### 通过拖放
将支持的文件拖放到窗口的任意位置。

### BIN 偏移输入
打开 `.bin` 文件时，工具会弹窗要求输入**加载偏移**
（十进制或十六进制，如 `0x8000`）。
该偏移将文件第一个字节映射到对应的内存地址。

---

## 6. 查看数据 <a name="viewing"></a>

### 字节分组
从下拉框选择 **1 byte**、**2 bytes** 或 **4 bytes**。
1 字节模式下字节序选择器不可用。

### 字节序
仅在 2 字节或 4 字节分组时有效。

- **Little-endian（小端）**：字节反序后显示（适用于 ARM/x86）
- **Big-endian（大端）**：按文件顺序显示字节

### 缺失字节
无数据的地址在十六进制列显示为 `..`，ASCII 列显示为空格。
这对稀疏 HEX 文件是正常现象。

---

## 7. 跳转地址 <a name="goto"></a>

在 **Go To** 组合框中输入目标地址并按回车（或点击按钮）。

- 支持十进制（`65536`）或十六进制（`0x10000`）
- 视图滚动并选中对应行
- 最近 20 个地址保存在历史下拉列表中

---

## 8. 刷新 <a name="refresh"></a>

按 **Refresh** 按钮或 `F5` 从磁盘重新加载当前文件。

- 若原始文件字节未变化（CRC32 匹配），跳过重载并短暂显示"无变化"提示。
- 若文件已更改，重新解析并更新表格。
- BIN 文件自动复用上次输入的偏移地址。

---

## 9. CRC 功能 <a name="crc"></a>

### Data CRC32（数据 CRC32）
按地址顺序对 HEX/BIN 文件中所有数据字节计算 CRC32，
显示在工具栏第一行。

### File CRC32（文件 CRC32）
对磁盘上文件的原始字节计算 CRC32，
显示在工具栏第一行。

### 块对齐 CRC16
使用 CRC16-CCITT（多项式 `0x11021`）对指定地址范围计算 CRC16，
并将末尾填充到块边界。

**操作步骤：**
1. 输入 **Start**（必须是块大小的整数倍）。
2. 输入 **Stop**（不含，必须大于 Start）。
3. 输入 **Block size**（默认 `0x100`）。
4. 输入缺失地址的 **Pad** 字节（默认 `0xFF`）。
5. 点击 **Block-aligned CRC16**。
6. 结果格式：`0xABCD (0xSTART-0xEND)`

**说明：**
- 加载文件后 Start/Stop 会自动填充（对齐到文件实际数据范围的块边界）。
- Stop 为最后一个数据字节地址加一。

---

## 10. 键盘快捷键 <a name="keyboard"></a>

| 按键 | 功能 |
|---|---|
| `F5` | 从磁盘刷新文件 |

---

## 11. 使用技巧 <a name="tips"></a>

- 直接将文件拖放到窗口是最快的打开方式。
- 使用 2 字节或 4 字节分组可以更直观地读取字/双字数值。
- HEX 文件的 **Data CRC32** 与 **File CRC32** 不同，
  因为文件 CRC32 包含了 HEX 记录的格式开销字节。
- BIN 文件的两个 CRC32 值相同。
- 使用**块对齐 CRC16** 可以重现固件中按 Flash 页边界填充后计算的嵌入式 CRC。

---

*© 2026 wxpython_intelhex_viewer project*