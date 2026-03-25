import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import serial
import serial.tools.list_ports
import threading
import time
import re
from datetime import datetime
from queue import Queue, Empty

# =============================================
# 1. 사용자 데이터베이스 (UID 매칭)
# =============================================
USER_DB = {
    "7474E2B6": {"name": "이훈열", "role": "관리자", "color": "#00E5FF"}, 
    "53AF971D": {"name": "신상규", "role": "관리자", "color": "#00E5FF"}, 
    "54DC9AB6": {"name": "황다빈", "role": "주인",   "color": "#FFD700"}, 
    "438BD91D": {"name": "서우석", "role": "직원",   "color": "#00FF7F"}, 
    "8BADBD19": {"name": "송수은", "role": "직원",   "color": "#00FF7F"}, 
    "04CBA2FE": {"name": "김민혁", "role": "노예",   "color": "#FF69B4"}, 
}

# 고대비 색상 설정
BG_BLACK = "#000000"
BG_PANEL = "#1A1A1A"
TEXT_LIME = "#32CD32"
ERROR_RED = "#FF0000"

class HighContrastLoRaUI:
    def __init__(self, root):
        self.root = root
        self.root.title("PREMIUM ACCESS CONTROL SYSTEM v3.2")
        self.root.geometry("1300x850") # 가로 폭을 조금 더 넓혔습니다.
        self.root.configure(bg=BG_BLACK)

        self.ser = None
        self.rx_running = False
        self.log_queue = Queue()
        self.access_count = 0

        self.setup_styles()
        self.build_ui()
        self.refresh_ports()
        self.root.after(100, self.process_log_queue)

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        
        style.configure("Treeview", 
                        background=BG_PANEL, 
                        foreground="white", 
                        fieldbackground=BG_PANEL, 
                        rowheight=50, 
                        font=("Malgun Gothic", 13, "bold")) 
        
        style.configure("Treeview.Heading", 
                        background="#333333", 
                        foreground="#FFFFFF", 
                        font=("Malgun Gothic", 14, "bold"))

    def build_ui(self):
        # --- 상단 설정 영역 ---
        top_frame = tk.Frame(self.root, bg=BG_BLACK)
        top_frame.pack(fill="x", padx=20, pady=15)

        self.port_combo = ttk.Combobox(top_frame, width=15, font=("Arial", 12))
        self.port_combo.pack(side="left", padx=10)

        self.connect_btn = tk.Button(top_frame, text="시스템 가동", bg="#444", fg="white", 
                                     font=("맑은 고딕", 12, "bold"), width=12, command=self.connect_serial)
        self.connect_btn.pack(side="left", padx=5)

        self.stat_label = tk.Label(top_frame, text="ACCESS: 0", font=("Impact", 45), 
                                   bg=BG_BLACK, fg=TEXT_LIME)
        self.stat_label.pack(side="right", padx=20)

        # --- 메인 기록 표 (SNR 컬럼 추가) ---
        mid_frame = tk.Frame(self.root, bg=BG_BLACK)
        mid_frame.pack(expand=True, fill="both", padx=20)

        self.tree = ttk.Treeview(mid_frame, columns=("No", "Time", "Name", "Role", "UID", "RSSI", "SNR"), show="headings")
        
        # 컬럼 설정 (SNR 추가됨)
        cols = {"No": 60, "Time": 120, "Name": 140, "Role": 110, "UID": 160, "RSSI": 100, "SNR": 100}
        for col, width in cols.items():
            self.tree.heading(col, text=col)
            self.tree.column(col, width=width, anchor="center")

        # 역할별 색상 태그
        self.tree.tag_configure('주인', foreground="#FFD700", background="#222200")
        self.tree.tag_configure('관리자', foreground="#00E5FF", background="#001A1A")
        self.tree.tag_configure('직원', foreground="#00FF7F", background="#001A00")
        self.tree.tag_configure('노예', foreground="#FF69B4", background="#1A001A")
        self.tree.tag_configure('Unknown', foreground="#FF0000", background="#1A0000")

        self.tree.pack(expand=True, fill="both")

        # --- 하단 시스템 콘솔 ---
        bot_frame = tk.LabelFrame(self.root, text=" SYSTEM MONITORING ", bg=BG_BLACK, fg="#888")
        bot_frame.pack(fill="x", padx=20, pady=20)
        
        self.log_text = scrolledtext.ScrolledText(bot_frame, height=10, bg="#050505", fg=TEXT_LIME, 
                                                 font=("Consolas", 11))
        self.log_text.pack(fill="both", padx=5, pady=5)

    def connect_serial(self):
        if self.ser:
            self.ser.close()
            self.ser = None
            self.connect_btn.config(text="시스템 가동", bg="#444")
            return
            
        try:
            self.ser = serial.Serial(self.port_combo.get(), 38400, timeout=0.1)
            self.rx_running = True
            threading.Thread(target=self.receive_loop, daemon=True).start()
            self.connect_btn.config(text="중지(STOP)", bg=ERROR_RED)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def receive_loop(self):
        while self.rx_running:
            if self.ser and self.ser.in_waiting > 0:
                try:
                    line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                    if line: self.log_queue.put(line)
                except: pass
            time.sleep(0.01)

    def process_log_queue(self):
        try:
            while True:
                line = self.log_queue.get_nowait()
                self.write_log(f"> {line}")
                
                # 정규식 수정: RSSI, SNR, UID를 모두 추출
                # 예시 데이터: "RSSI:-043,SNR: 26,[7474E2B6]"
                match = re.search(r"RSSI:([-]?\d+),SNR:\s*(\d+),.*\[([A-Z0-9]+)\]", line)
                if match:
                    rssi = match.group(1)
                    snr = match.group(2)
                    uid = match.group(3)
                    self.add_to_table(uid, rssi, snr)
        except Empty: pass
        self.root.after(100, self.process_log_queue)

    def add_to_table(self, uid, rssi, snr):
        self.access_count += 1
        now = datetime.now().strftime("%H:%M:%S")
        
        user = USER_DB.get(uid, {"name": "미등록", "role": "Unknown"})
        tag = user['role']
        
        # 표에 데이터 추가 (SNR 포함)
        self.tree.insert("", 0, values=(
            self.access_count, 
            now, 
            user['name'], 
            user['role'], 
            uid, 
            rssi + " dBm",
            snr
        ), tags=(tag,))
        
        self.stat_label.config(text=f"ACCESS: {self.access_count}")

    def write_log(self, text):
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, text + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")

    def refresh_ports(self):
        ports = serial.tools.list_ports.comports()
        self.port_combo["values"] = [p.device for p in ports]
        if ports: self.port_combo.set(ports[0].device)

if __name__ == "__main__":
    root = tk.Tk()
    app = HighContrastLoRaUI(root)
    root.mainloop()