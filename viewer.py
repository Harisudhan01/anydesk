import io
import time
import threading
import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageTk
from network_protocol import send_packet, recv_packet

class RemoteViewerWindow(ctk.CTkToplevel):
    """Window showing the remote computer's desktop with full interactive control"""
    def __init__(self, parent, sock, target_id, on_close=None):
        super().__init__(parent)
        self.sock = sock
        self.target_id = target_id
        self.on_close = on_close
        
        self.title(f"PyDesk - Remote Desktop [{target_id}]")
        self.geometry("1100x700")
        self.protocol("WM_DELETE_WINDOW", self.close_session)
        
        self.running = True
        self.last_frame_pil = None
        self.tk_img = None
        self.img_pos_x = 0
        self.img_pos_y = 0
        self.img_disp_w = 1
        self.img_disp_h = 1
        self.is_fullscreen = False
        
        self.frame_count = 0
        self.fps_timer = time.time()
        self.current_fps = 0
        
        self._build_ui()
        self._bind_events()
        
        # Start receive loop in separate thread
        self.rx_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self.rx_thread.start()

    def _build_ui(self):
        # Top toolbar
        self.toolbar = ctk.CTkFrame(self, height=45, corner_radius=0, fg_color="#1e1e24")
        self.toolbar.pack(fill="x", side="top")
        
        self.lbl_id = ctk.CTkLabel(
            self.toolbar, 
            text=f"💻 Remote Desk: {self.target_id}", 
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#e0e0e0"
        )
        self.lbl_id.pack(side="left", padx=15)
        
        self.lbl_stats = ctk.CTkLabel(
            self.toolbar,
            text="FPS: -- | Connected",
            font=ctk.CTkFont(size=12),
            text_color="#00c853"
        )
        self.lbl_stats.pack(side="left", padx=10)
        
        self.btn_disconnect = ctk.CTkButton(
            self.toolbar,
            text="Disconnect",
            command=self.close_session,
            fg_color="#d32f2f",
            hover_color="#b71c1c",
            width=100,
            height=28
        )
        self.btn_disconnect.pack(side="right", padx=15)

        self.btn_fullscreen = ctk.CTkButton(
            self.toolbar,
            text="Fullscreen",
            command=self.toggle_fullscreen,
            fg_color="#37474f",
            hover_color="#455a64",
            width=90,
            height=28
        )
        self.btn_fullscreen.pack(side="right", padx=5)

        # Canvas for rendering remote screen
        self.canvas = tk.Canvas(self, bg="#0d0d11", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

    def _bind_events(self):
        # Window resize event to adapt scale
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        
        # Mouse events
        self.canvas.bind("<Motion>", self._on_mouse_move)
        self.canvas.bind("<B1-Motion>", self._on_mouse_move)
        self.canvas.bind("<B3-Motion>", self._on_mouse_move)
        
        self.canvas.bind("<Button-1>", lambda e: self._on_mouse_click(e, "left", True))
        self.canvas.bind("<ButtonRelease-1>", lambda e: self._on_mouse_click(e, "left", False))
        
        self.canvas.bind("<Button-3>", lambda e: self._on_mouse_click(e, "right", True))
        self.canvas.bind("<ButtonRelease-3>", lambda e: self._on_mouse_click(e, "right", False))

        self.canvas.bind("<Button-2>", lambda e: self._on_mouse_click(e, "middle", True))
        self.canvas.bind("<ButtonRelease-2>", lambda e: self._on_mouse_click(e, "middle", False))
        
        self.canvas.bind("<MouseWheel>", self._on_mouse_scroll)
        
        # Keyboard events - require canvas focus
        self.canvas.focus_set()
        self.canvas.bind("<Button-1>", lambda e: self.canvas.focus_set(), add="+")
        self.bind("<KeyPress>", lambda e: self._on_key_event(e, True))
        self.bind("<KeyRelease>", lambda e: self._on_key_event(e, False))

    def toggle_fullscreen(self):
        self.is_fullscreen = not self.is_fullscreen
        self.attributes("-fullscreen", self.is_fullscreen)
        self.btn_fullscreen.configure(text="Windowed" if self.is_fullscreen else "Fullscreen")

    def _get_normalized_coords(self, event_x, event_y):
        """Translates canvas mouse coordinates into 0.0 - 1.0 relative screen coordinates"""
        if self.img_disp_w <= 0 or self.img_disp_h <= 0:
            return None, None
        
        rel_x = event_x - self.img_pos_x
        rel_y = event_y - self.img_pos_y
        
        if 0 <= rel_x <= self.img_disp_w and 0 <= rel_y <= self.img_disp_h:
            nx = rel_x / float(self.img_disp_w)
            ny = rel_y / float(self.img_disp_h)
            return nx, ny
        return None, None

    def _on_mouse_move(self, event):
        nx, ny = self._get_normalized_coords(event.x, event.y)
        if nx is not None and self.running:
            send_packet(self.sock, {"type": "MOUSE_MOVE", "nx": nx, "ny": ny})

    def _on_mouse_click(self, event, button, pressed):
        nx, ny = self._get_normalized_coords(event.x, event.y)
        if nx is not None and self.running:
            send_packet(self.sock, {"type": "MOUSE_MOVE", "nx": nx, "ny": ny})
            send_packet(self.sock, {"type": "MOUSE_CLICK", "btn": button, "pressed": pressed})

    def _on_mouse_scroll(self, event):
        # Windows event.delta is typically +/- 120
        dy = 1 if event.delta > 0 else -1
        if self.running:
            send_packet(self.sock, {"type": "MOUSE_SCROLL", "dy": dy})

    def _on_key_event(self, event, pressed):
        if not self.running:
            return
        keysym = event.keysym
        send_packet(self.sock, {"type": "KEY_EVENT", "key": keysym, "pressed": pressed})

    def _on_canvas_resize(self, event):
        if self.last_frame_pil:
            self._render_frame(self.last_frame_pil)

    def _render_frame(self, pil_img):
        can_w = self.canvas.winfo_width()
        can_h = self.canvas.winfo_height()
        if can_w <= 10 or can_h <= 10:
            return

        orig_w, orig_h = pil_img.size
        ratio = min(can_w / orig_w, can_h / orig_h)
        new_w = max(1, int(orig_w * ratio))
        new_h = max(1, int(orig_h * ratio))

        # Scale image
        resized_img = pil_img.resize((new_w, new_h), Image.Resampling.BILINEAR)
        self.tk_img = ImageTk.PhotoImage(resized_img)

        # Center in canvas
        self.img_pos_x = (can_w - new_w) // 2
        self.img_pos_y = (can_h - new_h) // 2
        self.img_disp_w = new_w
        self.img_disp_h = new_h

        self.canvas.delete("all")
        self.canvas.create_image(self.img_pos_x, self.img_pos_y, anchor="nw", image=self.tk_img)

    def _recv_loop(self):
        while self.running:
            header, payload = recv_packet(self.sock)
            if header is None:
                break
                
            msg_type = header.get("type")
            if msg_type == "FRAME":
                try:
                    pil_img = Image.open(io.BytesIO(payload))
                    self.last_frame_pil = pil_img
                    
                    # Schedule UI update on main thread
                    self.after(0, lambda img=pil_img: self._render_frame(img))
                    
                    # Stats tracking
                    self.frame_count += 1
                    now = time.time()
                    if now - self.fps_timer >= 1.0:
                        self.current_fps = self.frame_count
                        self.frame_count = 0
                        self.fps_timer = now
                        self.after(0, lambda: self.lbl_stats.configure(text=f"FPS: {self.current_fps} | Connected"))
                except Exception:
                    pass
                    
        self.after(0, self.close_session)

    def close_session(self):
        if not self.running:
            return
        self.running = False
        try:
            self.sock.close()
        except Exception:
            pass
        if self.on_close:
            self.on_close()
        try:
            self.destroy()
        except Exception:
            pass
