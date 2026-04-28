# Merge Tool — 用户指南

---

## 目录

1. [概述](#overview)
2. [系统要求](#requirements)
3. [启动程序](#starting)
4. [输入文件表格](#table)
5. [添加文件](#adding)
6. [文件类型与默认值](#filetypes)
7. [调整顺序](#reorder)
8. [输出设置](#output)
9. [执行合并](#merging)
10. [警告信息](#warnings)
11. [使用技巧](#tips)

---

## 1. 概述 <a name="overview"></a>

Merge Tool 用于将多个 Intel HEX 和/或 BIN 文件合并为一个输出文件。  
同一个输入文件可以用不同偏移或不同数据块范围重复添加。  
输出可保存为 Intel HEX 或二进制格式。

---

## 2. 系统要求 <a name="requirements"></a>

- Windows 7 或更高版本（建议 64 位）
- Python 3.8+，并安装 `wxPython`、`intelhex`，或直接使用已编译的 `merge_tool.exe`

```bash
pip install wxPython intelhex
```

---

## 3. 启动程序 <a name="starting"></a>

源码运行：

```bash
python merge_tool.py
```

若使用编译版本，双击 `merge_tool.exe` 即可。

---

## 4. 输入文件表格 <a name="table"></a>

| 列名 | 说明 |
|---|---|
| **Use** | 勾选表示参与合并；取消勾选表示跳过。 |
| **Type** | `auto`、`hex`、`bin`；`auto` 根据扩展名识别。 |
| **File** | 输入文件完整路径，长路径会在单元格内换行。 |
| **Target Offset** | 合并输出中的目标基地址。HEX 自动从文件读取；BIN 默认 `0x0`。 |
| **Block Start** | 源文件内读取起始偏移，默认 `0x0`。 |
| **Block Length** | 读取字节数。BIN 默认从 Block Start 读到文件末尾。 |

---

## 5. 添加文件 <a name="adding"></a>

### A. 浏览按钮
1. 选中一行（或点击 **Add Row** 新增一行）。
2. 点击 **Browse File…**。
3. 选择文件。

### B. 拖放到表格
- 将文件拖放到指定行。
- 文件会插入该行位置。

### C. 拖放到窗口/日志区域
- 拖放到网格外区域。
- 文件会追加到表格末尾。

---

## 6. 文件类型与默认值 <a name="filetypes"></a>

### Intel HEX (`.hex`, `.ihx`, `.ihex`)
- 地址来自 HEX 文件本身。
- Offset/Start/Length 仅用于显示参考。
- 合并时始终按 HEX 记录地址写入。

### 二进制 BIN (`.bin`)
- 文件中不含地址信息。
- `Target Offset` 指定写入目标地址。
- `Block Start` 与 `Block Length` 用于选择部分数据。

| 字段 | HEX 默认值 | BIN 默认值 |
|---|---|---|
| Target Offset | 自动（来自文件） | `0x0` |
| Block Start | 自动（来自文件） | `0x0` |
| Block Length | 自动（字节数） | 从 Block Start 到文件末尾 |

数值格式支持：十进制（`65536`）、十六进制（`0x10000`）或 `h` 后缀十六进制（`10000h`）。

---

## 7. 调整顺序 <a name="reorder"></a>

合并顺序为自上而下。

- 使用 **Move Up** / **Move Down** 调整顺序。
- 地址重叠时，靠后的行会覆盖靠前行（确认后执行）。

---

## 8. 输出设置 <a name="output"></a>

### Merge Target（必填）
- 通过 **Browse…** 或拖放到目标框设置输出路径。
- `.hex/.ihx/.ihex` 输出 HEX。
- 其他扩展名（如 `.bin`）输出二进制。

### BIN Start Address（仅二进制输出）
- 二进制输出写入的最低地址。
- 留空时自动使用合并数据最小地址。

### Fill Byte（仅二进制输出）
- 数据空洞填充值，默认 `0xFF`。

---

## 9. 执行合并 <a name="merging"></a>

1. 添加并配置输入行。
2. 设置输出路径。
3. 点击 **Merge**。
4. 查看日志摘要。
5. 弹出成功提示后完成。

---

## 10. 警告信息 <a name="warnings"></a>

| 警告 | 含义 | 处理方式 |
|---|---|---|
| 地址重叠 | 多行写入同一地址 | 继续覆盖或取消 |
| 输出文件已有数据 | 目标文件存在且非空 | 覆盖或取消 |
| 文件未找到 | 输入路径无效 | 修正路径或禁用该行 |
| 数据块超出文件大小 | Start + Length 非法 | 修正块参数 |

---

## 11. 使用技巧 <a name="tips"></a>

- 同一文件可重复添加多次。
- 用 **Use** 复选框临时禁用某行。
- 可拉宽 **File** 列提高可读性。
- 构建命令：

```bash
python -m PyInstaller build.spec --clean
```

---

*© 2026 wxpython_intelhex_viewer project*