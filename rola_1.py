import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import serial
import serial.tools.list_ports
import threading
import time
from queue import Queue, Empty


class LoRaATUI:
    def __init__(self, root):
        self.root = root
        self.root.title("LoRa AT UART Tool")
        self.root.geometry("900x620")

        self.ser = None
        self.rx_thread = None
        self.rx_running = False
        self.log_queue = Queue()

        self.build_ui()
        self.refresh_ports()
        self.root.after(100, self.process_log_queue)

    def build_ui(self):
        top_frame = ttk.LabelFrame(self.root, text="Serial Setting")
        top_frame.pack(fill="x", padx=10, pady=10)

        ttk.Label(top_frame, text="Port").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.port_combo = ttk.Combobox(top_frame, width=30, state="readonly")
        self.port_combo.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        self.refresh_btn = ttk.Button(top_frame, text="Refresh", command=self.refresh_ports)
        self.refresh_btn.grid(row=0, column=2, padx=5, pady=5)

        ttk.Label(top_frame, text="Baudrate").grid(row=0, column=3, padx=5, pady=5, sticky="w")
        self.baud_entry = ttk.Entry(top_frame, width=12)
        self.baud_entry.grid(row=0, column=4, padx=5, pady=5, sticky="w")
        self.baud_entry.insert(0, "38400")

        ttk.Label(top_frame, text="Data Bits").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.databits_combo = ttk.Combobox(top_frame, width=10, state="readonly",
                                           values=["8", "7", "6", "5"])
        self.databits_combo.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        self.databits_combo.set("8")

        ttk.Label(top_frame, text="Parity").grid(row=1, column=2, padx=5, pady=5, sticky="w")
        self.parity_combo = ttk.Combobox(top_frame, width=10, state="readonly",
                                         values=["N", "E", "O"])
        self.parity_combo.grid(row=1, column=3, padx=5, pady=5, sticky="w")
        self.parity_combo.set("N")

        ttk.Label(top_frame, text="Stop Bits").grid(row=1, column=4, padx=5, pady=5, sticky="w")
        self.stopbits_combo = ttk.Combobox(top_frame, width=10, state="readonly",
                                           values=["1", "1.5", "2"])
        self.stopbits_combo.grid(row=1, column=5, padx=5, pady=5, sticky="w")
        self.stopbits_combo.set("1")

        self.connect_btn = ttk.Button(top_frame, text="Connect", command=self.connect_serial)
        self.connect_btn.grid(row=0, column=5, padx=5, pady=5)

        self.disconnect_btn = ttk.Button(top_frame, text="Disconnect", command=self.disconnect_serial, state="disabled")
        self.disconnect_btn.grid(row=0, column=6, padx=5, pady=5)

        self.status_var = tk.StringVar(value="Disconnected")
        self.status_label = ttk.Label(top_frame, textvariable=self.status_var, foreground="red")
        self.status_label.grid(row=1, column=6, padx=5, pady=5)

        send_frame = ttk.LabelFrame(self.root, text="Send")
        send_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(send_frame, text="Payload").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.msg_entry = ttk.Entry(send_frame, width=70)
        self.msg_entry.grid(row=0, column=1, padx=5, pady=5, sticky="we")
        self.msg_entry.bind("<Return>", lambda event: self.send_payload())

        self.send_btn = ttk.Button(send_frame, text="Send", command=self.send_payload, state="disabled")
        self.send_btn.grid(row=0, column=2, padx=5, pady=5)

        ttk.Label(send_frame, text="Custom AT").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.at_entry = ttk.Entry(send_frame, width=70)
        self.at_entry.grid(row=1, column=1, padx=5, pady=5, sticky="we")
        self.at_entry.bind("<Return>", lambda event: self.send_custom_at())

        self.at_send_btn = ttk.Button(send_frame, text="Send AT", command=self.send_custom_at, state="disabled")
        self.at_send_btn.grid(row=1, column=2, padx=5, pady=5)

        send_frame.columnconfigure(1, weight=1)

        option_frame = ttk.LabelFrame(self.root, text="AT Command Option")
        option_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(option_frame, text="AT Prefix").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.at_prefix_entry = ttk.Entry(option_frame, width=20)
        self.at_prefix_entry.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        self.at_prefix_entry.insert(0, "AT+SEND=")

        ttk.Label(option_frame, text="Separator").grid(row=0, column=2, padx=5, pady=5, sticky="w")
        self.sep_entry = ttk.Entry(option_frame, width=10)
        self.sep_entry.grid(row=0, column=3, padx=5, pady=5, sticky="w")
        self.sep_entry.insert(0, ",")

        ttk.Label(option_frame, text="Line End").grid(row=0, column=4, padx=5, pady=5, sticky="w")
        self.line_end_combo = ttk.Combobox(option_frame, width=10, state="readonly",
                                           values=[r"\r\n", r"\r", r"\n", "None"])
        self.line_end_combo.grid(row=0, column=5, padx=5, pady=5, sticky="w")
        self.line_end_combo.set(r"\r\n")

        self.length_as_bytes_var = tk.BooleanVar(value=True)
        self.length_check = ttk.Checkbutton(
            option_frame,
            text="Length = UTF-8 byte length",
            variable=self.length_as_bytes_var
        )
        self.length_check.grid(row=0, column=6, padx=10, pady=5, sticky="w")

        log_frame = ttk.LabelFrame(self.root, text="Log")
        log_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.log_text = scrolledtext.ScrolledText(log_frame, wrap="word", state="disabled", font=("Consolas", 10))
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)

        bottom_frame = ttk.Frame(self.root)
        bottom_frame.pack(fill="x", padx=10, pady=(0, 10))

        self.clear_btn = ttk.Button(bottom_frame, text="Clear Log", command=self.clear_log)
        self.clear_btn.pack(side="left", padx=5)

        self.test_at_btn = ttk.Button(bottom_frame, text="Send AT", command=self.send_test_at, state="disabled")
        self.test_at_btn.pack(side="left", padx=5)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def refresh_ports(self):
        ports = serial.tools.list_ports.comports()
        port_list = [p.device for p in ports]
        self.port_combo["values"] = port_list

        if port_list:
            current = self.port_combo.get()
            if current not in port_list:
                self.port_combo.set(port_list[0])
        else:
            self.port_combo.set("")

        self.write_log("[INFO] Port list refreshed")

    def get_serial_params(self):
        port = self.port_combo.get().strip()
        if not port:
            raise ValueError("포트를 선택하세요.")

        baudrate = int(self.baud_entry.get().strip())

        databits_map = {
            "8": serial.EIGHTBITS,
            "7": serial.SEVENBITS,
            "6": serial.SIXBITS,
            "5": serial.FIVEBITS,
        }
        parity_map = {
            "N": serial.PARITY_NONE,
            "E": serial.PARITY_EVEN,
            "O": serial.PARITY_ODD,
        }
        stopbits_map = {
            "1": serial.STOPBITS_ONE,
            "1.5": serial.STOPBITS_ONE_POINT_FIVE,
            "2": serial.STOPBITS_TWO,
        }

        bytesize = databits_map[self.databits_combo.get()]
        parity = parity_map[self.parity_combo.get()]
        stopbits = stopbits_map[self.stopbits_combo.get()]

        return port, baudrate, bytesize, parity, stopbits

    def connect_serial(self):
        if self.ser and self.ser.is_open:
            messagebox.showinfo("Info", "이미 연결되어 있습니다.")
            return

        try:
            port, baudrate, bytesize, parity, stopbits = self.get_serial_params()

            self.ser = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=bytesize,
                parity=parity,
                stopbits=stopbits,
                timeout=0.1
            )

            time.sleep(0.3)

            self.rx_running = True
            self.rx_thread = threading.Thread(target=self.receive_loop, daemon=True)
            self.rx_thread.start()

            self.status_var.set(f"Connected: {port}")
            self.status_label.configure(foreground="green")

            self.connect_btn.config(state="disabled")
            self.disconnect_btn.config(state="normal")
            self.send_btn.config(state="normal")
            self.at_send_btn.config(state="normal")
            self.test_at_btn.config(state="normal")

            self.write_log(f"[INFO] Connected to {port} @ {baudrate} bps")

        except Exception as e:
            messagebox.showerror("Connection Error", str(e))
            self.write_log(f"[ERROR] Connection failed: {e}")

    def disconnect_serial(self):
        self.rx_running = False

        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
                self.write_log("[INFO] Serial disconnected")
        except Exception as e:
            self.write_log(f"[ERROR] Disconnect failed: {e}")

        self.ser = None
        self.status_var.set("Disconnected")
        self.status_label.configure(foreground="red")

        self.connect_btn.config(state="normal")
        self.disconnect_btn.config(state="disabled")
        self.send_btn.config(state="disabled")
        self.at_send_btn.config(state="disabled")
        self.test_at_btn.config(state="disabled")

    def receive_loop(self):
        buffer = b""

        while self.rx_running:
            try:
                if self.ser and self.ser.is_open:
                    data = self.ser.read(self.ser.in_waiting or 1)
                    if data:
                        buffer += data

                        while b"\n" in buffer:
                            line, buffer = buffer.split(b"\n", 1)
                            text = line.decode("utf-8", errors="replace").strip()
                            if text:
                                self.log_queue.put(f"[RX] {text}")

                        # 줄바꿈 없이 들어오는 데이터 보호용
                        if len(buffer) > 1024:
                            text = buffer.decode("utf-8", errors="replace").strip()
                            if text:
                                self.log_queue.put(f"[RX-RAW] {text}")
                            buffer = b""
                else:
                    time.sleep(0.1)

            except Exception as e:
                self.log_queue.put(f"[ERROR] Receive error: {e}")
                break

    def build_send_command(self, payload: str) -> str:
        prefix = self.at_prefix_entry.get().strip()
        sep = self.sep_entry.get()

        if self.length_as_bytes_var.get():
            length = len(payload.encode("utf-8"))
        else:
            length = len(payload)

        cmd = f"{prefix}{length}{sep}{payload}"
        return cmd

    def get_line_end(self) -> str:
        mode = self.line_end_combo.get()
        if mode == r"\r\n":
            return "\r\n"
        if mode == r"\r":
            return "\r"
        if mode == r"\n":
            return "\n"
        return ""

    def send_payload(self):
        if not (self.ser and self.ser.is_open):
            messagebox.showwarning("Warning", "먼저 포트를 연결하세요.")
            return

        payload = self.msg_entry.get()
        if not payload:
            messagebox.showwarning("Warning", "보낼 데이터를 입력하세요.")
            return

        try:
            cmd = self.build_send_command(payload) + self.get_line_end()
            self.ser.write(cmd.encode("utf-8"))
            self.write_log(f"[TX] {cmd.rstrip()}")
            self.msg_entry.delete(0, tk.END)
        except Exception as e:
            self.write_log(f"[ERROR] Send failed: {e}")
            messagebox.showerror("Send Error", str(e))

    def send_custom_at(self):
        if not (self.ser and self.ser.is_open):
            messagebox.showwarning("Warning", "먼저 포트를 연결하세요.")
            return

        cmd = self.at_entry.get().strip()
        if not cmd:
            messagebox.showwarning("Warning", "AT 명령을 입력하세요.")
            return

        try:
            full_cmd = cmd + self.get_line_end()
            self.ser.write(full_cmd.encode("utf-8"))
            self.write_log(f"[TX-AT] {cmd}")
            self.at_entry.delete(0, tk.END)
        except Exception as e:
            self.write_log(f"[ERROR] AT send failed: {e}")
            messagebox.showerror("AT Send Error", str(e))

    def send_test_at(self):
        if not (self.ser and self.ser.is_open):
            return

        try:
            cmd = "AT" + self.get_line_end()
            self.ser.write(cmd.encode("utf-8"))
            self.write_log("[TX-AT] AT")
        except Exception as e:
            self.write_log(f"[ERROR] AT test failed: {e}")

    def process_log_queue(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.write_log(msg)
        except Empty:
            pass

        self.root.after(100, self.process_log_queue)

    def write_log(self, text):
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, f"[{timestamp}] {text}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")

    def clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.config(state="disabled")

    def on_close(self):
        self.disconnect_serial()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = LoRaATUI(root)
    root.mainloop()