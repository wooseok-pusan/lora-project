import serial
import threading
import time
import board
import busio
from adafruit_pn532.i2c import PN532_I2C
from queue import Queue, Empty

class LoRaNFCSender:
    def __init__(self):
        # --- 설정값 ---
        self.LORA_PORT = '/dev/ttyUSB0'
        self.LORA_BAUD = 38400
        self.NFC_ADDR = 0x24
        
        self.ser = None
        self.nfc = None
        self.running = True
        self.log_queue = Queue()

    def write_log(self, text):
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] {text}")

    def init_hardware(self):
        try:
            # 1. LoRa 초기화
            self.ser = serial.Serial(self.LORA_PORT, self.LORA_BAUD, timeout=1)
            self.write_log(f"[INFO] LoRa Connected: {self.LORA_PORT}")

            # 2. NFC 초기화
            i2c = busio.I2C(board.SCL, board.SDA)
            self.nfc = PN532_I2C(i2c, debug=False, address=self.NFC_ADDR)
            self.nfc.SAM_configuration()
            self.write_log("[INFO] NFC PN532 Initialized")
            return True
        except Exception as e:
            self.write_log(f"[ERROR] Initialization failed: {e}")
            return False

    def nfc_scan_loop(self):
        """백그라운드에서 NFC를 감시하는 루프"""
        self.write_log("[SYSTEM] Scanning for NFC tags...")
        last_uid = None
        
        while self.running:
            try:
                # 0.5초 동안 카드 대기
                uid = self.nfc.read_passive_target(timeout=0.5)
                
                if uid is None:
                    last_uid = None
                    continue

                if uid == last_uid:
                    time.sleep(0.1)
                    continue

                # 신규 카드 감지
                last_uid = uid
                uid_hex = bytes(uid).hex().upper()
                self.write_log(f"[NFC] Tag Detected: {uid_hex}")

                # LoRa로 AT 커맨드 전송
                self.send_at_command(uid_hex)

            except Exception as e:
                self.write_log(f"[ERROR] NFC Loop error: {e}")
                time.sleep(1)

    def send_at_command(self, payload):
        """사용자님의 AT 커맨드 형식 적용: AT+SEND=[데이터]"""
        try:
            # 보낼 명령어 구성 (\r\n 포함)
            full_cmd = f"AT+SEND=[{payload}]\r\n"
            self.ser.write(full_cmd.encode("utf-8"))
            self.write_log(f"[TX] {full_cmd.strip()}")

            # 응답 확인 (ACK)
            time.sleep(0.2)
            if self.ser.in_waiting > 0:
                resp = self.ser.readline().decode(errors='ignore').strip()
                self.write_log(f"[RX] {resp}")

        except Exception as e:
            self.write_log(f"[ERROR] Send failed: {e}")

    def run(self):
        if self.init_hardware():
            # NFC 스캔을 별도 쓰레드에서 실행 (확장성 고려)
            nfc_thread = threading.Thread(target=self.nfc_scan_loop, daemon=True)
            nfc_thread.start()

            try:
                while True:
                    time.sleep(1) # 메인 루프 유지
            except KeyboardInterrupt:
                self.write_log("[SYSTEM] Shutting down...")
                self.running = False
                if self.ser: self.ser.close()

if __name__ == "__main__":
    app = LoRaNFCSender()
    app.run()
    
