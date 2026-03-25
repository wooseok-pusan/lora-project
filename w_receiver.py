import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
import serial
import serial.tools.list_ports
import threading
import time
import re
from datetime import datetime
from queue import Queue, Empty

# =============================================
# 1. 사용자 데이터베이스
# =============================================
USER_DB = {
    "7474E2B6": {"name": "이훈열", "type": "기존"}, 
    "53AF971D": {"name": "신상규", "type": "기존"}, 
    "54DC9AB6": {"name": "황다빈", "type": "기존"}, 
    "438BD91D": {"name": "서우석", "type": "기존"}, 
    "8BADBD19": {"name": "송수은", "type": "기존"}, 
    "04CBA2FE": {"name": "김민혁", "type": "기존"}, 
}

BG_BLACK = "#000000"
BG_PANEL = "#1A1A1A"
TEXT_LIME = "#32CD32"
ERROR_RED = "#FF0000"
NEW_USER_COLOR = "#FFD700" # 신규 등록자 강조색 (골드)

class HighContrastLoRaUI:
    def __init__(self, root):
        self.root = root
        self.root.title("PREMIUM ACCESS CONTROL SYSTEM v4.1")
        self.root.geometry("1200x850") 
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

        mid_frame = tk.Frame(self.root, bg=BG_BLACK)
        mid_frame.pack(expand=True, fill="both", padx=20)

        self.tree = ttk.Treeview(mid_frame, columns=("No", "Time", "Name", "UID", "RSSI", "SNR"), show="headings")
        
        # --- 시각적 구분을 위한 태그 설정 ---
        self.tree.tag_configure('new_user', foreground=NEW_USER_COLOR, background="#221A00") # 신규: 금색 글씨
        self.tree.tag_configure('old_user', foreground="white") # 기존: 흰색 글씨

        cols = {"No": 60, "Time": 150, "Name": 180, "UID": 200, "RSSI": 120, "SNR": 120}
        for col, width in cols.items():
            self.tree.heading(col, text=col)
            self.tree.column(col, width=width, anchor="center")

        self.tree.pack(expand=True, fill="both")

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
                
                match = re.search(r"RSSI:([-]?\d+),SNR:\s*(\d+),.*\[([A-Z0-9]+)\]", line)
                if match:
                    rssi = match.group(1)
                    snr = match.group(2)
                    uid = match.group(3)
                    self.add_to_table(uid, rssi, snr)
        except Empty: pass
        self.root.after(100, self.process_log_queue)

    def add_to_table(self, uid, rssi, snr):
        # 1. 미등록 카드 감지 및 알림
        if uid not in USER_DB:
            # 경고 메시지 먼저 띄우기
            messagebox.showwarning("미등록 카드", f"등록되지 않은 카드입니다! (UID: {uid})\n등록 절차를 진행합니다.")
            
            # 이름 입력받기
            new_name = simpledialog.askstring("신규 등록", "사용자 이름을 입력하세요:", parent=self.root)
            
            if new_name:
                USER_DB[uid] = {"name": new_name, "type": "신규"} # '신규' 타입 지정
            else:
                USER_DB[uid] = {"name": "미등록", "type": "신규"}

        # 2. 데이터 표시 (타입에 따라 태그 부여)
        self.access_count += 1
        now = datetime.now().strftime("%H:%M:%S")
        user = USER_DB[uid]
        
        # 유저 타입에 따라 적용할 태그 결정
        user_tag = 'new_user' if user.get("type") == "신규" else 'old_user'
        
        self.tree.insert("", 0, values=(
            self.access_count, 
            now, 
            user['name'], 
            uid, 
            rssi + " dBm",
            snr
        ), tags=(user_tag,)) # 태그 적용
        
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