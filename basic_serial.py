import os
import time
import queue
import threading
from typing import Optional

from version import __version_serial__ as __version__

import wx
import serial
from serial.tools import list_ports

ICON_DIR = os.path.join(os.path.dirname(__file__), "icons")

class SerialWorker(threading.Thread):
    def __init__(self, on_data, on_error):
        super().__init__(daemon=True)
        self.on_data = on_data
        self.on_error = on_error
        self._running = threading.Event()
        self._running.set()

        self._write_queue: "queue.Queue[bytes]" = queue.Queue()
        self._ser: Optional[serial.Serial] = None

        self._cfg = {
            "port": "",
            "baudrate": 19200,
            "bytesize": serial.EIGHTBITS,
            "parity": serial.PARITY_NONE,
            "stopbits": serial.STOPBITS_ONE,
            "xonxoff": False,
            "rtscts": False,
        }

    def setup_port(
        self,
        port: str,
        baudrate: int,
        bytesize,
        parity,
        stopbits,
        flow_control: str,
    ) -> None:
        self._cfg["port"] = port
        self._cfg["baudrate"] = baudrate
        self._cfg["bytesize"] = bytesize
        self._cfg["parity"] = parity
        self._cfg["stopbits"] = stopbits
        self._cfg["xonxoff"] = flow_control == "Software"
        self._cfg["rtscts"] = flow_control == "Hardware"

    def write_data(self, text: str) -> None:
        if self._ser and self._ser.is_open:
            self._write_queue.put(text.encode())
        else:
            self.on_error("Serial port is not open")

    def stop(self) -> None:
        self._running.clear()
        if self.is_alive():
            self.join(timeout=2.0)

    def run(self) -> None:
        try:
            self._ser = serial.Serial(
                port=self._cfg["port"],
                baudrate=self._cfg["baudrate"],
                bytesize=self._cfg["bytesize"],
                parity=self._cfg["parity"],
                stopbits=self._cfg["stopbits"],
                timeout=0.1,
                xonxoff=self._cfg["xonxoff"],
                rtscts=self._cfg["rtscts"],
            )
        except Exception as e:
            self.on_error(f"Failed to open port: {e}")
            return

        try:
            while self._running.is_set():
                while not self._write_queue.empty():
                    data = self._write_queue.get()
                    self._ser.write(data)
                    self._ser.flush()

                waiting = self._ser.in_waiting
                if waiting:
                    data = self._ser.read(waiting).decode(errors="replace")
                    self.on_data(data)
                else:
                    time.sleep(0.02)
        except Exception as e:
            self.on_error(str(e))
        finally:
            try:
                if self._ser and self._ser.is_open:
                    self._ser.close()
            except Exception:
                pass


class SerialPortFrame(wx.Frame):
    def __init__(self):
        super().__init__(parent=None, title=f"Basic Serial v{__version__}", size=(760, 560))
        self.SetMinSize((500, 400))

        panel = wx.Panel(self)
        root = wx.BoxSizer(wx.VERTICAL)

        # add icon
        icon = wx.Icon(os.path.join(ICON_DIR, "basic_serial.ico"), wx.BITMAP_TYPE_ICO)
        self.SetIcon(icon)

        # ===== Two-column main layout =====
        content_row = wx.BoxSizer(wx.HORIZONTAL)

        # ---------- LEFT COLUMN: serial port controls ----------
        left_col = wx.BoxSizer(wx.VERTICAL)

        grid = wx.FlexGridSizer(rows=6, cols=2, vgap=8, hgap=8)

        self.port_choice = wx.Choice(panel)
        # add a custom baud rate option to the list
        self.baud_choice = wx.Choice(panel, choices=["9600", "19200", "38400", "57600", "115200", "Custom..."])
        self.data_bits_choice = wx.Choice(panel, choices=["5", "6", "7", "8"])
        self.parity_choice = wx.Choice(panel, choices=["None", "Even", "Odd", "Space", "Mark"])
        self.stop_bits_choice = wx.Choice(panel, choices=["1", "1.5", "2"])
        self.flow_control_choice = wx.Choice(panel, choices=["None", "Hardware", "Software"])

        self.baud_choice.SetStringSelection("19200")
        self.data_bits_choice.SetStringSelection("8")
        self.parity_choice.SetSelection(0)
        self.stop_bits_choice.SetSelection(0)
        self.flow_control_choice.SetSelection(0)

        labels = ["Port:", "Baud Rate:", "Data Bits:", "Parity:", "Stop Bits:", "Flow Control:"]
        controls = [
            self.port_choice,
            self.baud_choice,
            self.data_bits_choice,
            self.parity_choice,
            self.stop_bits_choice,
            self.flow_control_choice,
        ]

        for text, ctrl in zip(labels, controls):
            grid.Add(wx.StaticText(panel, label=text), 0, wx.ALIGN_CENTER_VERTICAL)
            grid.Add(ctrl, 1, wx.EXPAND)

        grid.AddGrowableCol(1, 1)
        left_col.Add(grid, 0, wx.EXPAND)

        btn_row = wx.BoxSizer(wx.HORIZONTAL)
        self.connect_btn = wx.Button(panel, label="Connect")
        self.disconnect_btn = wx.Button(panel, label="Disconnect")
        self.disconnect_btn.Enable(False)
        btn_row.Add(self.connect_btn, 0, wx.RIGHT, 8)
        btn_row.Add(self.disconnect_btn, 0)
        left_col.AddSpacer(12)
        left_col.Add(btn_row, 0, wx.EXPAND)
        left_col.AddStretchSpacer(1)

        # ---------- RIGHT COLUMN: receive (top) + send (bottom) ----------
        right_col = wx.BoxSizer(wx.VERTICAL)

        right_col.Add(wx.StaticText(panel, label="Received"), 0, wx.BOTTOM, 4)
        self.received_display = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY)
        right_col.Add(self.received_display, 1, wx.EXPAND | wx.BOTTOM, 8)

        clear_row = wx.BoxSizer(wx.HORIZONTAL)
        clear_row.AddStretchSpacer(1)
        self.clear_btn = wx.Button(panel, label="Clear")
        clear_row.Add(self.clear_btn, 0)
        right_col.Add(clear_row, 0, wx.EXPAND | wx.BOTTOM, 10)

        right_col.Add(wx.StaticText(panel, label="Send"), 0, wx.BOTTOM, 4)
        self.send_input = wx.TextCtrl(panel, style=wx.TE_MULTILINE)
        right_col.Add(self.send_input, 0, wx.EXPAND | wx.BOTTOM, 8)

        send_row = wx.BoxSizer(wx.HORIZONTAL)
        self.send_newline_checkbox = wx.CheckBox(panel, label="Send newline after text")
        send_row.Add(self.send_newline_checkbox, 0, wx.RIGHT, 8)
        send_row.AddStretchSpacer(1)
        self.send_btn = wx.Button(panel, label="Send")
        send_row.Add(self.send_btn, 0)
        right_col.Add(send_row, 0, wx.EXPAND)

        # Add both columns to main row
        content_row.Add(left_col, 0, wx.EXPAND | wx.RIGHT, 12)
        content_row.Add(right_col, 1, wx.EXPAND)

        root.Add(content_row, 1, wx.ALL | wx.EXPAND, 10)
        panel.SetSizer(root)

        self.worker: Optional[SerialWorker] = None
        self.refresh_ports()
        self.port_refresh_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, lambda event: self.refresh_ports(), self.port_refresh_timer)
        self.port_refresh_timer.Start(2000)

        # baudrate custom input dialog
        self.baud_choice.Bind(wx.EVT_CHOICE, self.on_baud_choice)
        self.connect_btn.Bind(wx.EVT_BUTTON, self.on_connect)
        self.disconnect_btn.Bind(wx.EVT_BUTTON, self.on_disconnect)
        self.send_btn.Bind(wx.EVT_BUTTON, self.on_send)
        self.clear_btn.Bind(wx.EVT_BUTTON, self.on_clear)
        self.Bind(wx.EVT_CLOSE, self.on_close)

    def on_baud_choice(self, event) -> None:
        # if "Custom" is selected, show a dialog to enter custom baud rate
        if self.baud_choice.GetStringSelection() == "Custom...":
            dlg = wx.TextEntryDialog(self, "Enter custom baud rate:", "Custom Baud Rate")
            if dlg.ShowModal() == wx.ID_OK:
                custom_baud = dlg.GetValue()
                if custom_baud.isdigit() and int(custom_baud) > 0:
                    # add the custom baud rate to the choice control if it's not already there
                    if custom_baud not in [self.baud_choice.GetString(i) for i in range(self.baud_choice.GetCount())]:
                        # sort first by numeric value, then lexically to handle non-numeric entries
                        self.baud_choice.Append(custom_baud)
                        # sort the baud rates numerically, keeping "Custom..." at the end
                        choices = [self.baud_choice.GetString(i) for i in range(self.baud_choice.GetCount()) if self.baud_choice.GetString(i) != "Custom..."]
                        choices.sort(key=lambda x: int(x))
                        choices.append("Custom...")
                        self.baud_choice.Set(choices)
                    self.baud_choice.SetStringSelection(custom_baud)
                else:
                    wx.MessageBox("Please enter a valid positive integer for baud rate.", "Invalid Input", wx.OK | wx.ICON_ERROR)
                    self.baud_choice.SetSelection(0)  # reset to default selection
            else:
                self.baud_choice.SetSelection(0)  # reset to default selection
        
    def refresh_ports(self) -> None:
        # get currently selected port to try to preserve selection after refresh
        current_port = self.port_choice.GetStringSelection() if self.port_choice.GetCount() > 0 else None
        
        ports = [p.device for p in list_ports.comports()]
        # sort based on com port number if possible (e.g. COM1, COM2, etc.)
        try:
            ports.sort(key=lambda x: int(x[3:]) if x.startswith("COM") and x[3:].isdigit() else float("inf"))
        except Exception:
            pass
        # if ports is not empty and has changed, update the choice control
        if ports != [self.port_choice.GetString(i) for i in range(self.port_choice.GetCount())]:
            self.port_choice.Set(ports)
            # try to restore previous selection
            if current_port in ports:
                self.port_choice.SetStringSelection(current_port)

    def _append_received(self, text: str) -> None:
        self.received_display.AppendText(text)
        # if not text.endswith("\n"):
            # self.received_display.AppendText("\n")

    def _show_error(self, text: str) -> None:
        self.received_display.AppendText(f"ERROR: {text}\n")

    def on_connect(self, _event) -> None:
        if self.port_choice.GetCount() == 0:
            self._show_error("No serial ports found")
            return

        port = self.port_choice.GetStringSelection()
        baud = int(self.baud_choice.GetStringSelection())
        bits_map = {"5": serial.FIVEBITS, "6": serial.SIXBITS, "7": serial.SEVENBITS, "8": serial.EIGHTBITS}
        parity_map = {
            "None": serial.PARITY_NONE,
            "Even": serial.PARITY_EVEN,
            "Odd": serial.PARITY_ODD,
            "Space": serial.PARITY_SPACE,
            "Mark": serial.PARITY_MARK,
        }
        stop_map = {"1": serial.STOPBITS_ONE, "1.5": serial.STOPBITS_ONE_POINT_FIVE, "2": serial.STOPBITS_TWO}

        bits = bits_map[self.data_bits_choice.GetStringSelection()]
        parity = parity_map[self.parity_choice.GetStringSelection()]
        stop = stop_map[self.stop_bits_choice.GetStringSelection()]
        flow = self.flow_control_choice.GetStringSelection()

        self.worker = SerialWorker(
            on_data=lambda s: wx.CallAfter(self._append_received, s),
            on_error=lambda e: wx.CallAfter(self._show_error, e),
        )
        self.worker.setup_port(port, baud, bits, parity, stop, flow)
        self.worker.start()

        self.connect_btn.Enable(False)
        self.disconnect_btn.Enable(True)

    def on_disconnect(self, _event) -> None:
        if self.worker:
            self.worker.stop()
            self.worker = None
        self.connect_btn.Enable(True)
        self.disconnect_btn.Enable(False)

    def on_send(self, _event) -> None:
        text = self.send_input.GetValue()
        # add newline if the checkbox is checked
        if self.send_newline_checkbox.GetValue():
            text += "\n"
        if self.worker:
            self.worker.write_data(text)
        else:
            self._show_error("Serial port is not connected")

    def on_clear(self, _event) -> None:
        self.received_display.Clear()

    def on_close(self, event) -> None:
        if self.worker:
            self.worker.stop()
            self.worker = None
        self.port_refresh_timer.Stop()
        self.port_refresh_timer = None
        event.Skip()


if __name__ == "__main__":
    # enable high dpi
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    app = wx.App(False)
    frame = SerialPortFrame()
    frame.Show()
    app.MainLoop()