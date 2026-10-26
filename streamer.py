import time
import io
import threading
import ctypes
from PIL import Image
import mss
from pynput.mouse import Controller as MouseController, Button
from pynput.keyboard import Controller as KeyboardController, Key
from network_protocol import send_packet, recv_packet
from config import DEFAULT_JPEG_QUALITY

# Enable DPI awareness on Windows for exact coordinate mapping
try:
    ctypes.windll.user32.SetProcessDPIAware()
except Exception:
    pass

SPECIAL_KEYS_MAP = {
    "backspace": Key.backspace,
    "enter": Key.enter,
    "return": Key.enter,
    "tab": Key.tab,
    "space": Key.space,
    "shift": Key.shift,
    "shift_l": Key.shift_l,
    "shift_r": Key.shift_r,
    "ctrl": Key.ctrl,
    "ctrl_l": Key.ctrl_l,
    "ctrl_r": Key.ctrl_r,
    "alt": Key.alt,
    "alt_l": Key.alt_l,
    "alt_r": Key.alt_r,
    "escape": Key.esc,
    "up": Key.up,
    "down": Key.down,
    "left": Key.left,
    "right": Key.right,
    "delete": Key.delete,
    "home": Key.home,
    "end": Key.end,
    "page_up": Key.page_up,
    "page_down": Key.page_down,
    "caps_lock": Key.caps_lock,
}

class HostStreamer:
    """Handles capturing the host screen and receiving remote mouse/keyboard inputs"""
    def __init__(self, sock, on_disconnect=None):
        self.sock = sock
        self.on_disconnect = on_disconnect
        self.running = False
        self.mouse = MouseController()
        self.keyboard = KeyboardController()
        
        # Get primary screen size
        with mss.mss() as sct:
            self.monitor = sct.monitors[1]
            self.screen_w = self.monitor["width"]
            self.screen_h = self.monitor["height"]
            
        self.stream_thread = None
        self.input_thread = None

    def start(self):
        self.running = True
        self.stream_thread = threading.Thread(target=self._stream_loop, daemon=True)
        self.input_thread = threading.Thread(target=self._input_loop, daemon=True)
        self.stream_thread.start()
        self.input_thread.start()

    def stop(self):
        self.running = False
        try:
            self.sock.close()
        except Exception:
            pass
        if self.on_disconnect:
            self.on_disconnect()

    def _stream_loop(self):
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            while self.running:
                start_time = time.time()
                try:
                    # Capture screen
                    sct_img = sct.grab(monitor)
                    # Convert to PIL RGB
                    img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                    
                    # Compress to JPEG in memory
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=DEFAULT_JPEG_QUALITY, optimize=False)
                    jpeg_bytes = buf.getvalue()
                    
                    header = {
                        "type": "FRAME",
                        "w": monitor["width"],
                        "h": monitor["height"],
                        "ts": start_time
                    }
                    
                    if not send_packet(self.sock, header, jpeg_bytes):
                        break
                        
                except Exception as e:
                    break
                    
                # Regulate to ~25-30 FPS to prevent CPU hogging and buffer saturation
                elapsed = time.time() - start_time
                target_delay = 1.0 / 30.0
                if elapsed < target_delay:
                    time.sleep(target_delay - elapsed)
                    
        self.stop()

    def _input_loop(self):
        while self.running:
            header, _ = recv_packet(self.sock)
            if header is None:
                break
                
            msg_type = header.get("type")
            if msg_type == "MOUSE_MOVE":
                nx = header.get("nx", 0)
                ny = header.get("ny", 0)
                actual_x = int(nx * self.screen_w)
                actual_y = int(ny * self.screen_h)
                try:
                    self.mouse.position = (actual_x, actual_y)
                except Exception:
                    pass

            elif msg_type == "MOUSE_CLICK":
                btn_name = header.get("btn", "left")
                pressed = header.get("pressed", True)
                btn = Button.left
                if btn_name == "right":
                    btn = Button.right
                elif btn_name == "middle":
                    btn = Button.middle
                    
                try:
                    if pressed:
                        self.mouse.press(btn)
                    else:
                        self.mouse.release(btn)
                except Exception:
                    pass

            elif msg_type == "MOUSE_SCROLL":
                dy = header.get("dy", 0)
                try:
                    self.mouse.scroll(0, dy)
                except Exception:
                    pass

            elif msg_type == "KEY_EVENT":
                key_str = header.get("key", "")
                pressed = header.get("pressed", True)
                
                key_obj = SPECIAL_KEYS_MAP.get(key_str.lower(), key_str)
                try:
                    if pressed:
                        self.keyboard.press(key_obj)
                    else:
                        self.keyboard.release(key_obj)
                except Exception:
                    pass
                    
        self.stop()
