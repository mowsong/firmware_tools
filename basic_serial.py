import os
import time
import queue
import threading
from typing import Optional

from version import __version_serial__ as __version__

import wx
import serial
from serial.tools import list_ports
from wx import stc

# Plotting imports
import matplotlib
matplotlib.use('WXAgg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
import matplotlib.pyplot as plt

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
        self.on_plot_data = None

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
                    raw_data = self._ser.read(waiting)
                    # Send raw bytes to plot parser
                    if self.on_plot_data:
                        self.on_plot_data(raw_data)
                    # Decode for terminal display
                    decoded_data = raw_data.decode(errors="replace")
                    self.on_data(decoded_data)
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
        super().__init__(parent=None, title=f"Basic Serial v{__version__}", size=(860, 600))
        self.SetMinSize((600, 450))

        # Initialize attributes first
        self.next_chunk_starts_with_newline = False
        self._max_display_lines = 100000
        self._autoscroll = True
        self._display_lock = threading.Lock()
        self.worker: Optional[SerialWorker] = None

        # Add a status bar for error messages
        self.statusBar = self.CreateStatusBar(2)
        self.statusBar.SetStatusWidths([-1, 120])
        self.statusBar.SetStatusText("Ready", 0)
        self.statusBar.SetStatusText("Errors: 0", 1)

        root_panel = wx.Panel(self)
        root_sizer = wx.BoxSizer(wx.VERTICAL)

        # Create a notebook for tabs
        self.notebook = wx.Notebook(root_panel)

        # Create Terminal Tab
        terminal_panel = self.create_terminal_tab(self.notebook)
        self.notebook.AddPage(terminal_panel, "Terminal")

        # Create Plot Tab
        plot_panel = self.create_plot_tab(self.notebook)
        self.notebook.AddPage(plot_panel, "Plot")

        root_sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 5)
        root_panel.SetSizer(root_sizer)

        # add icon
        icon = wx.Icon(os.path.join(ICON_DIR, "basic_serial.ico"), wx.BITMAP_TYPE_ICO)
        self.SetIcon(icon)
        
        self.refresh_ports()
        self.port_refresh_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, lambda event: self.refresh_ports(), self.port_refresh_timer)
        self.port_refresh_timer.Start(2000)

        # baudrate custom input dialog
        self.baud_choice.Bind(wx.EVT_CHOICE, self.on_baud_choice)
        self.max_lines_ctrl.Bind(wx.EVT_SPINCTRL, self.on_max_lines_changed)
        self.received_display.Bind(stc.EVT_STC_UPDATEUI, self.on_stc_update_ui)
        self.received_display.Bind(stc.EVT_STC_DOUBLECLICK, self.on_stc_double_click)
        self.connect_btn.Bind(wx.EVT_BUTTON, self.on_connect)
        self.disconnect_btn.Bind(wx.EVT_BUTTON, self.on_disconnect)
        self.send_btn.Bind(wx.EVT_BUTTON, self.on_send)
        self.clear_btn.Bind(wx.EVT_BUTTON, self.on_clear)
        self.Bind(wx.EVT_CLOSE, self.on_close)

        # Defer the initial plot layout until the frame is fully sized and shown
        self.Bind(wx.EVT_SHOW, self.on_show_frame, self)

    def on_show_frame(self, event):
        if event.IsShown():
            # Call tight_layout once after the frame is shown to ensure correct initial sizing
            # Add some padding to prevent widgets from overlapping the x-axis.
            self.figure.subplots_adjust(bottom=0.15)
            self.figure.tight_layout(rect=[0, 0.05, 1, 1])
            # Unbind the event so it doesn't fire again
            self.Unbind(wx.EVT_SHOW, self)
        event.Skip()

    def create_terminal_tab(self, parent):
        panel = wx.Panel(parent)
        root = wx.BoxSizer(wx.VERTICAL)
        
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
        self.received_display = stc.StyledTextCtrl(panel)
        self._configure_stc()
        right_col.Add(self.received_display, 1, wx.EXPAND | wx.BOTTOM, 8)

        clear_row = wx.BoxSizer(wx.HORIZONTAL)
        clear_row.Add(wx.StaticText(panel, label="Max Lines:"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.max_lines_ctrl = wx.SpinCtrl(panel, value=str(self._max_display_lines), min=100, max=1000000)
        self.max_lines_ctrl.SetToolTip("Maximum number of lines to keep in the display.")
        clear_row.Add(self.max_lines_ctrl, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
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
        right_col.Add(send_row, 0, wx.EXPAND | wx.BOTTOM, 8)

        # Add 4 more send inputs
        self.extra_send_inputs = []
        for i in range(4):
            send_row_extra = wx.BoxSizer(wx.HORIZONTAL)
            text_ctrl = wx.TextCtrl(panel)
            send_btn_extra = wx.Button(panel, label="Send")
            
            send_row_extra.Add(text_ctrl, 1, wx.EXPAND | wx.RIGHT, 8)
            send_row_extra.Add(send_btn_extra, 0)
            
            right_col.Add(send_row_extra, 0, wx.EXPAND | wx.BOTTOM, 4)
            
            self.extra_send_inputs.append((text_ctrl, send_btn_extra))
            send_btn_extra.Bind(wx.EVT_BUTTON, lambda event, tc=text_ctrl: self.on_send_extra(event, tc))

        # Add both columns to main row
        content_row.Add(left_col, 0, wx.EXPAND | wx.RIGHT, 12)
        content_row.Add(right_col, 1, wx.EXPAND)

        root.Add(content_row, 1, wx.ALL | wx.EXPAND, 10)
        panel.SetSizer(root)
        return panel

    def create_plot_tab(self, parent):
        panel = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Plotting attributes
        self._plot_data = [] # List of lists for multi-line plots
        self._plot_buffer = b""
        self._plot_max_points = 200
        self._plot_lock = threading.Lock()
        self._plotting_enabled = False
        self._use_fixed_y_axis = False
        self._y_min = 0.0
        self._y_max = 5.0
        self._plot_lines = [] # Store matplotlib line objects
        self._plot_format_string = "%d"
        self._plot_error_count = 0
        # Define a persistent color cycle
        self._plot_colors = plt.rcParams['axes.prop_cycle'].by_key()['color']

        # Matplotlib Figure
        self.figure = Figure()
        self.axes = self.figure.add_subplot(111)
        # Set a persistent color cycle on the axes
        self.axes.set_prop_cycle(color=self._plot_colors)
        self.axes.set_title("Live Data Plot")
        self.axes.set_xlabel("Time (samples)")
        self.axes.set_ylabel("Value")
        self.axes.grid(True)
        self.axes.margins(x=0) # Set tight margins for the x-axis
        # self.plot_line, = self.axes.plot(self._plot_data) # Removed, will be managed dynamically
        # self.figure.tight_layout() # Defer this call until the frame is shown

        self.canvas = FigureCanvas(panel, -1, self.figure)
        self.canvas.SetMinSize(wx.Size(-1, 200)) # Set a minimum height of 200 pixels
        
        # Controls
        controls_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Left side controls (plotting, clear, points)
        left_controls_sizer = wx.BoxSizer(wx.VERTICAL)
        
        top_controls_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.enable_plotting_checkbox = wx.CheckBox(panel, label="Enable Plotting")
        self.enable_plotting_checkbox.SetValue(self._plotting_enabled)
        self.enable_plotting_checkbox.Bind(wx.EVT_CHECKBOX, self.on_toggle_plotting)

        self.plot_clear_btn = wx.Button(panel, label="Clear Plot")
        self.plot_clear_btn.Bind(wx.EVT_BUTTON, self.on_clear_plot)
        
        max_points_label = wx.StaticText(panel, label="Max Points:")
        self.max_points_spin = wx.SpinCtrl(panel, value=str(self._plot_max_points), min=10, max=5000)
        self.max_points_spin.Bind(wx.EVT_SPINCTRL, self.on_max_points_changed)

        top_controls_sizer.Add(self.enable_plotting_checkbox, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 15)
        top_controls_sizer.Add(self.plot_clear_btn, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        top_controls_sizer.Add(max_points_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        top_controls_sizer.Add(self.max_points_spin, 0, wx.ALIGN_CENTER_VERTICAL)

        # Y-Axis controls
        y_axis_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.fixed_y_axis_checkbox = wx.CheckBox(panel, label="Use Fixed Y-Axis")
        self.fixed_y_axis_checkbox.Bind(wx.EVT_CHECKBOX, self.on_toggle_fixed_y_axis)

        y_min_label = wx.StaticText(panel, label="Min:")
        self.y_min_ctrl = wx.TextCtrl(panel, value=str(self._y_min), size=(50,-1))
        self.y_min_ctrl.Enable(False)
        self.y_min_ctrl.Bind(wx.EVT_TEXT, self.on_y_limit_changed)

        y_max_label = wx.StaticText(panel, label="Max:")
        self.y_max_ctrl = wx.TextCtrl(panel, value=str(self._y_max), size=(50,-1))
        self.y_max_ctrl.Enable(False)
        self.y_max_ctrl.Bind(wx.EVT_TEXT, self.on_y_limit_changed)

        y_axis_sizer.Add(self.fixed_y_axis_checkbox, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        y_axis_sizer.Add(y_min_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        y_axis_sizer.Add(self.y_min_ctrl, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        y_axis_sizer.Add(y_max_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        y_axis_sizer.Add(self.y_max_ctrl, 0, wx.ALIGN_CENTER_VERTICAL)

        # Format string control
        format_sizer = wx.BoxSizer(wx.HORIZONTAL)
        format_label = wx.StaticText(panel, label="Data Format:")
        self.format_ctrl = wx.TextCtrl(panel, value=self._plot_format_string)
        self.format_ctrl.SetToolTip("C-style format string (e.g., 'A:%d, B:%f'). Delimiters: space, ',', ':'. Dataset ends with newline or ';'.")
        self.format_ctrl.Bind(wx.EVT_TEXT, self.on_format_changed)
        format_sizer.Add(format_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        format_sizer.Add(self.format_ctrl, 1, wx.EXPAND)

        left_controls_sizer.Add(top_controls_sizer, 0, wx.EXPAND | wx.BOTTOM, 5)
        left_controls_sizer.Add(y_axis_sizer, 0, wx.EXPAND | wx.BOTTOM, 5)
        left_controls_sizer.Add(format_sizer, 0, wx.EXPAND)

        # Right side controls (plot line selection)
        right_controls_sizer = wx.BoxSizer(wx.VERTICAL)
        self.plot_lines_checklist = wx.CheckListBox(panel, choices=[])
        self.plot_lines_checklist.SetToolTip("Select which data series to plot.")
        right_controls_sizer.Add(wx.StaticText(panel, label="Plot Series:"), 0, wx.BOTTOM, 4)
        right_controls_sizer.Add(self.plot_lines_checklist, 1, wx.EXPAND)

        controls_sizer.Add(left_controls_sizer, 1, wx.EXPAND | wx.RIGHT, 10)
        controls_sizer.Add(right_controls_sizer, 0, wx.EXPAND | wx.LEFT, 10)

        sizer.Add(self.canvas, 1, wx.EXPAND | wx.ALL, 5)
        sizer.Add(controls_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
        
        panel.SetSizer(sizer)

        # Timer for plot updates
        self.plot_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.update_plot, self.plot_timer)
        self.plot_timer.Start(100) # Update plot 10 times per second

        return panel

    def on_format_changed(self, event):
        self._plot_format_string = self.format_ctrl.GetValue()
        # Clear data as the format has changed, and force a full reset of lines
        self.on_clear_plot(event, full_reset=True)

    def on_toggle_plotting(self, event):
        self._plotting_enabled = self.enable_plotting_checkbox.GetValue()
        if not self._plotting_enabled:
            # When disabling, clear the plot for immediate feedback but don't reset lines
            self.on_clear_plot(event, full_reset=False)
        else:
            # Reset error count when enabling
            self._plot_error_count = 0
            self.statusBar.SetStatusText("Errors: 0", 1)
            self.statusBar.SetStatusText("Plotting enabled", 0)

    def on_toggle_fixed_y_axis(self, event):
        self._use_fixed_y_axis = self.fixed_y_axis_checkbox.GetValue()
        self.y_min_ctrl.Enable(self._use_fixed_y_axis)
        self.y_max_ctrl.Enable(self._use_fixed_y_axis)
        # Trigger a plot update to apply the new scaling
        self.update_plot(None)

    def on_y_limit_changed(self, event):
        try:
            self._y_min = float(self.y_min_ctrl.GetValue())
            self._y_max = float(self.y_max_ctrl.GetValue())
            if self._use_fixed_y_axis:
                self.update_plot(None) # Update plot if limits change
        except ValueError:
            # Ignore invalid float values for now
            pass

    def on_max_points_changed(self, event):
        self._plot_max_points = self.max_points_spin.GetValue()
        # Trim data if necessary
        with self._plot_lock:
            for data_series in self._plot_data:
                if len(data_series) > self._plot_max_points:
                    # Trim from the left
                    del data_series[:len(data_series) - self._plot_max_points]

    def on_clear_plot(self, event, full_reset=False):
        with self._plot_lock:
            self._plot_data.clear()
            self._plot_buffer = b"" # Also clear the byte buffer
            
            # If a full reset is requested (e.g., format change), remove the lines completely.
            if full_reset:
                self.plot_lines_checklist.Set([])
                for line in self._plot_lines:
                    line.remove()
                self._plot_lines.clear()
            else:
                # Otherwise, just clear the data from existing lines to preserve colors.
                for line in self._plot_lines:
                    line.set_data([], [])

        # Remove legend if it exists
        if self.axes.get_legend():
            self.axes.get_legend().remove()

        self.axes.relim()
        self.axes.autoscale_view()
        # Also reset the x-axis limit on clear
        self.axes.set_xlim(0, self._plot_max_points)
        self.canvas.draw()

    def _parse_plot_data(self, raw_data: bytes):
        if not self._plotting_enabled:
            return

        self._plot_buffer += raw_data
        
        while True:
            # Find any valid dataset delimiter
            end_pos = -1
            for ending in [b'\n', b'\r', b';']:
                pos = self._plot_buffer.find(ending)
                if pos != -1:
                    if end_pos == -1 or pos < end_pos:
                        end_pos = pos
            
            if end_pos == -1:
                break # No complete dataset found

            line_bytes = self._plot_buffer[:end_pos].strip()
            self._plot_buffer = self._plot_buffer[end_pos+1:]

            if line_bytes:
                try:
                    # Replace data delimiters with a standard one (space) for sscanf
                    line_str = line_bytes.decode(errors='ignore')
                    for delim in [',', ':']:
                        line_str = line_str.replace(delim, ' ')
                    
                    # Use a simple sscanf-like parser
                    values = []
                    parts = self._plot_format_string.split()
                    data_parts = line_str.split()
                    
                    if len(parts) > len(data_parts):
                        raise ValueError("Not enough data parts for format")

                    p_idx, d_idx = 0, 0
                    while p_idx < len(parts) and d_idx < len(data_parts):
                        if '%' in parts[p_idx]:
                            try:
                                if 'd' in parts[p_idx] or 'i' in parts[p_idx]:
                                    values.append(int(data_parts[d_idx]))
                                elif 'f' in parts[p_idx] or 'g' in parts[p_idx] or 'e' in parts[p_idx]:
                                    values.append(float(data_parts[d_idx]))
                                else: # Just a literal match
                                    if parts[p_idx] != data_parts[d_idx]:
                                        raise ValueError("Literal mismatch")
                                d_idx += 1
                            except (ValueError, IndexError):
                                d_idx +=1 # Skip non-matching data part
                                continue
                        else: # Literal text
                            if parts[p_idx] == data_parts[d_idx]:
                                d_idx += 1
                        p_idx += 1

                    if not values:
                        raise ValueError("No values parsed")

                    with self._plot_lock:
                        num_series = len(values)
                        # Initialize data lists and plot lines if this is the first data or format changed
                        if num_series != len(self._plot_data):
                            self._plot_data = [[] for _ in range(num_series)]
                            wx.CallAfter(self._update_plot_checklist, num_series)

                        for i in range(num_series):
                            self._plot_data[i].append(values[i])
                            if len(self._plot_data[i]) > self._plot_max_points:
                                self._plot_data[i].pop(0)

                except Exception as e:
                    self._plot_error_count += 1
                    wx.CallAfter(self.statusBar.SetStatusText, f"Parse error: {e}", 0)
                    wx.CallAfter(self.statusBar.SetStatusText, f"Errors: {self._plot_error_count}", 1)
    
    def _update_plot_checklist(self, num_series):
        """Update the checklist box for plot series. Must be called from main thread."""
        choices = [f"Series {i+1}" for i in range(num_series)]
        self.plot_lines_checklist.Set(choices)
        # Check all by default
        for i in range(num_series):
            self.plot_lines_checklist.Check(i)

    def update_plot(self, event):
        if not self._plotting_enabled:
            return

        with self._plot_lock:
            if not self._plot_data or not any(self._plot_data):
                if self._plot_lines:
                    for line in self._plot_lines:
                        line.set_data([], [])
                    if self.axes.get_legend():
                        self.axes.get_legend().remove()
                    self.canvas.draw()
                return
            
            # Ensure we have line objects for each data series
            num_series = len(self._plot_data)
            while len(self._plot_lines) < num_series:
                series_index = len(self._plot_lines)
                # The color is now handled automatically by the axes' property cycle
                line, = self.axes.plot([], [], label=f"Series {series_index + 1}")
                self._plot_lines.append(line)
            
            # Hide lines beyond the current number of series
            for i in range(num_series, len(self._plot_lines)):
                self._plot_lines[i].set_data([], [])

            checked_items = self.plot_lines_checklist.GetCheckedItems()
            active_y_data = []

            for i in range(num_series):
                line = self._plot_lines[i]
                if i in checked_items:
                    y_data = self._plot_data[i]
                    x_data = range(len(y_data))
                    line.set_data(x_data, y_data)
                    if y_data:
                        active_y_data.extend(y_data)
                else:
                    line.set_data([], [])
            
            self.axes.relim()
            if self._use_fixed_y_axis:
                # Use fixed limits, ensuring min < max
                min_val = min(self._y_min, self._y_max)
                max_val = max(self._y_min, self._y_max)
                if min_val == max_val: # Add padding if limits are identical
                    min_val -= 1
                    max_val += 1
                self.axes.set_ylim(min_val, max_val)
                self.axes.autoscale_view(scalex=True, scaley=False)
            else:
                # Autoscale with headroom and floor based on active data
                if active_y_data:
                    min_val = min(active_y_data)
                    max_val = max(active_y_data)
                    
                    # Add 10% padding, or a minimum of 1 unit if range is zero
                    data_range = max_val - min_val
                    if data_range == 0:
                        padding = 1
                    else:
                        padding = data_range * 0.1
                    
                    self.axes.set_ylim(min_val - padding, max_val + padding)
                
                self.axes.autoscale_view(scalex=True, scaley=False) # Only autoscale X
        
        # Set a fixed x-axis range from 0 to max_points to prevent resizing.
        self.axes.set_xlim(0, self._plot_max_points)

        # Place legend inside the plot on the upper right, with transparency
        self.axes.legend(loc='upper right', framealpha=0.5)
        # Adjust layout to use the full area, leaving space at the bottom.
        self.figure.tight_layout(rect=[0, 0.05, 1, 1])

        self.canvas.draw()
        self.canvas.flush_events()

    def _configure_stc(self):
        """Basic configuration for the StyledTextCtrl."""
        self.received_display.SetReadOnly(True)
        self.received_display.SetWrapMode(stc.STC_WRAP_WORD)
        
        # Set font and background color to match a typical terminal
        font = wx.Font(10, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.received_display.StyleSetFont(stc.STC_STYLE_DEFAULT, font)
        self.received_display.StyleSetBackground(stc.STC_STYLE_DEFAULT, wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW))
        self.received_display.StyleSetForeground(stc.STC_STYLE_DEFAULT, wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOWTEXT))
        self.received_display.StyleClearAll() # Apply the default style

        # No line numbers margin
        self.received_display.SetMarginWidth(0, 0)
        self.received_display.SetMarginWidth(1, 0)

        # Disable folding margin
        self.received_display.SetMarginWidth(2, 0)

        # Set caret to be invisible since it's read-only
        self.received_display.SetCaretStyle(stc.STC_CARETSTYLE_INVISIBLE)

    def on_stc_update_ui(self, event):
        """Handle UI updates on the StyledTextCtrl, primarily for scrolling."""
        # If the user scrolls up, disable autoscroll.
        if event.GetUpdated() & stc.STC_UPDATE_V_SCROLL:
            scroll_pos = self.received_display.GetScrollPos(wx.VERTICAL)
            scroll_range = self.received_display.GetScrollRange(wx.VERTICAL)
            thumb_size = self.received_display.GetScrollThumb(wx.VERTICAL)
            is_at_bottom = (scroll_pos >= scroll_range - thumb_size - 5)

            if not is_at_bottom:
                self._autoscroll = False
        
        event.Skip()

    def on_stc_double_click(self, event):
        """Re-enable autoscroll and jump to the bottom on double-click."""
        self._autoscroll = True
        # Go to the end to immediately show the latest content
        self.received_display.GotoPos(self.received_display.GetLength())
        event.Skip()

    def on_max_lines_changed(self, event) -> None:
        self._max_display_lines = self.max_lines_ctrl.GetValue()
        # Immediately trim if the current content exceeds the new limit
        self._trim_display()

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

    def _trim_display(self):
        """Removes lines from the beginning of the display if it exceeds the max line count."""
        with self._display_lock:
            line_count = self.received_display.GetLineCount()
            if line_count > self._max_display_lines:
                lines_to_remove = line_count - self._max_display_lines
                
                # Find the character position to remove up to
                pos_to_remove = self.received_display.PositionFromLine(lines_to_remove)
                
                self.received_display.SetReadOnly(False)
                self.received_display.DeleteRange(0, pos_to_remove)
                self.received_display.SetReadOnly(True)

    def _append_received(self, text: str) -> None:
        # handle the '\r\n' and '\r' line endings by replacing them with '\n' for consistent display
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        if self.next_chunk_starts_with_newline and text.startswith("\n"):
            text = text[1:]
        
        self.next_chunk_starts_with_newline = text.endswith("\n")
        
        with self._display_lock:
            # To avoid flicker, check if the user is scrolled to the bottom
            autoscroll = self._autoscroll

            self.received_display.SetReadOnly(False)
            self.received_display.AppendText(text)
            
            # Trim the display if it's over the limit
            # Note: _trim_display acquires its own lock, but since this is the same thread, it's a re-entrant call.
            # To be cleaner, let's call a non-locking version or handle it inline.
            line_count = self.received_display.GetLineCount()
            if line_count > self._max_display_lines:
                lines_to_remove = line_count - self._max_display_lines
                pos_to_remove = self.received_display.PositionFromLine(lines_to_remove)
                self.received_display.DeleteRange(0, pos_to_remove)
            
            if autoscroll:
                self.received_display.GotoPos(self.received_display.GetLength())

            self.received_display.SetReadOnly(True)

    def _show_error(self, text: str) -> None:
        with self._display_lock:
            self.received_display.SetReadOnly(False)
            self.received_display.AppendText(f"ERROR: {text}\n")
            self.received_display.GotoPos(self.received_display.GetLength())
            self.received_display.SetReadOnly(True)

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
        self.worker.on_plot_data = self._parse_plot_data
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

    def on_send_extra(self, _event, text_ctrl: wx.TextCtrl) -> None:
        text = text_ctrl.GetValue()
        if self.send_newline_checkbox.GetValue():
            text += "\n"
        if self.worker:
            self.worker.write_data(text)
        else:
            self._show_error("Serial port is not connected")

    def on_clear(self, _event) -> None:
        with self._display_lock:
            self.received_display.SetReadOnly(False)
            self.received_display.ClearAll()
            self.received_display.SetReadOnly(True)

    def on_close(self, event) -> None:
        if self.worker:
            self.worker.stop()
            self.worker = None
        if self.port_refresh_timer:
            self.port_refresh_timer.Stop()
            self.port_refresh_timer = None
        if self.plot_timer:
            self.plot_timer.Stop()
            self.plot_timer = None
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