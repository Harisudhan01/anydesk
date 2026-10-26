import os
import sys
import time
import socket
import threading
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk

from config import (
    get_or_create_device_id,
    generate_session_password,
    get_local_ip,
    DEFAULT_RELAY_HOST,
    DEFAULT_RELAY_PORT,
    DIRECT_CONNECT_PORT
)
from network_protocol import send_packet, recv_packet
from streamer import HostStreamer
from viewer import RemoteViewerWindow
from relay_server import RelayServer

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class PyDeskApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("PyDesk - Remote Desktop")
        self.geometry("880x560")
        self.resizable(False, False)
        
        # Identity
        self.device_id = get_or_create_device_id()
        self.session_password = generate_session_password()
        self.local_ip = get_local_ip()
        
        # State
        self.relay_host = DEFAULT_RELAY_HOST
        self.relay_port = DEFAULT_RELAY_PORT
        self.relay_control_sock = None
        self.is_registered = False
        self.active_streamer = None
        self.active_viewer = None
        self.local_relay_instance = None
        self.running = True
        
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.on_exit)
        
        # Start background threads
        self.relay_thread = threading.Thread(target=self._maintain_relay_connection, daemon=True)
        self.relay_thread.start()
        
        self.direct_listen_thread = threading.Thread(target=self._direct_listen_loop, daemon=True)
        self.direct_listen_thread.start()

    def _build_ui(self):
        # 1. Top Header
        self.header_frame = ctk.CTkFrame(self, height=70, corner_radius=0, fg_color="#18181f")
        self.header_frame.pack(fill="x", side="top")
        
        self.lbl_title = ctk.CTkLabel(
            self.header_frame,
            text="⚡ PyDesk",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color="#e53935"
        )
        self.lbl_title.pack(side="left", padx=25, pady=18)
        
        self.lbl_tagline = ctk.CTkLabel(
            self.header_frame,
            text="Fast & Secure Remote Desktop",
            font=ctk.CTkFont(size=12),
            text_color="#888899"
        )
        self.lbl_tagline.pack(side="left", pady=22)

        self.status_badge = ctk.CTkLabel(
            self.header_frame,
            text="● Connecting to Relay...",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#ffb300"
        )
        self.status_badge.pack(side="right", padx=25)

        # 2. Main Body Container
        self.body_frame = ctk.CTkFrame(self, fg_color="#101015")
        self.body_frame.pack(fill="both", expand=True, padx=20, pady=15)

        # Left Column: This Desk (Host Info)
        self.left_col = ctk.CTkFrame(self.body_frame, fg_color="#1a1a24", corner_radius=12)
        self.left_col.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(
            self.left_col,
            text="Your Desk",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#ffffff"
        ).pack(anchor="w", padx=20, pady=(20, 5))

        ctk.CTkLabel(
            self.left_col,
            text="Share this address to allow remote control of your PC:",
            font=ctk.CTkFont(size=12),
            text_color="#9e9ea8"
        ).pack(anchor="w", padx=20, pady=(0, 15))

        # ID Box Card
        self.id_card = ctk.CTkFrame(self.left_col, fg_color="#242433", corner_radius=8)
        self.id_card.pack(fill="x", padx=20, pady=5)

        self.lbl_id_display = ctk.CTkLabel(
            self.id_card,
            text=self.device_id,
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color="#00e676"
        )
        self.lbl_id_display.pack(side="left", padx=20, pady=15)

        self.btn_copy_id = ctk.CTkButton(
            self.id_card,
            text="Copy ID",
            width=80,
            height=32,
            fg_color="#37474f",
            hover_color="#455a64",
            command=self._copy_id_to_clipboard
        )
        self.btn_copy_id.pack(side="right", padx=15)

        # Password / Security Card
        self.pwd_card = ctk.CTkFrame(self.left_col, fg_color="#242433", corner_radius=8)
        self.pwd_card.pack(fill="x", padx=20, pady=15)

        ctk.CTkLabel(
            self.pwd_card,
            text="Session Password:",
            font=ctk.CTkFont(size=13),
            text_color="#cfd8dc"
        ).pack(side="left", padx=(15, 5), pady=12)

        self.lbl_pwd = ctk.CTkLabel(
            self.pwd_card,
            text=self.session_password,
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="#ffab00"
        )
        self.lbl_pwd.pack(side="left", padx=5)

        self.btn_refresh_pwd = ctk.CTkButton(
            self.pwd_card,
            text="↻ Refresh",
            width=70,
            height=28,
            fg_color="#263238",
            hover_color="#37474f",
            command=self._refresh_password
        )
        self.btn_refresh_pwd.pack(side="right", padx=15)

        # Local IP Info
        ctk.CTkLabel(
            self.left_col,
            text=f"Direct LAN IP: {self.local_ip}:{DIRECT_CONNECT_PORT}",
            font=ctk.CTkFont(size=11),
            text_color="#607d8b"
        ).pack(anchor="w", padx=20, pady=(5, 10))

        # Right Column: Remote Desk (Connect)
        self.right_col = ctk.CTkFrame(self.body_frame, fg_color="#1a1a24", corner_radius=12)
        self.right_col.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(
            self.right_col,
            text="Remote Desk",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#ffffff"
        ).pack(anchor="w", padx=20, pady=(20, 5))

        ctk.CTkLabel(
            self.right_col,
            text="Enter the 9-digit address or IP of the remote computer:",
            font=ctk.CTkFont(size=12),
            text_color="#9e9ea8"
        ).pack(anchor="w", padx=20, pady=(0, 15))

        self.entry_remote_id = ctk.CTkEntry(
            self.right_col,
            placeholder_text="e.g. 481 920 183 or 192.168.1.10",
            height=45,
            font=ctk.CTkFont(size=15),
            corner_radius=8
        )
        self.entry_remote_id.pack(fill="x", padx=20, pady=(5, 10))

        self.entry_remote_pwd = ctk.CTkEntry(
            self.right_col,
            placeholder_text="Password (Optional)",
            height=38,
            show="*",
            corner_radius=8
        )
        self.entry_remote_pwd.pack(fill="x", padx=20, pady=(0, 15))

        self.btn_connect = ctk.CTkButton(
            self.right_col,
            text="➔ Connect",
            height=45,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color="#e53935",
            hover_color="#c62828",
            corner_radius=8,
            command=self._on_connect_clicked
        )
        self.btn_connect.pack(fill="x", padx=20, pady=5)

        self.lbl_connect_status = ctk.CTkLabel(
            self.right_col,
            text="",
            font=ctk.CTkFont(size=12),
            text_color="#e53935"
        )
        self.lbl_connect_status.pack(padx=20, pady=8)

        # 3. Bottom Settings Drawer / Bar
        self.footer_frame = ctk.CTkFrame(self, height=45, corner_radius=0, fg_color="#18181f")
        self.footer_frame.pack(fill="x", side="bottom")

        self.lbl_server_info = ctk.CTkLabel(
            self.footer_frame,
            text=f"Relay Server: {self.relay_host}:{self.relay_port}",
            font=ctk.CTkFont(size=11),
            text_color="#78909c"
        )
        self.lbl_server_info.pack(side="left", padx=20)

        self.btn_change_server = ctk.CTkButton(
            self.footer_frame,
            text="Change Server",
            width=100,
            height=26,
            fg_color="#263238",
            hover_color="#37474f",
            command=self._open_server_settings
        )
        self.btn_change_server.pack(side="left", padx=5)

        self.btn_toggle_local_server = ctk.CTkButton(
            self.footer_frame,
            text="Host Local Relay",
            width=120,
            height=26,
            fg_color="#1b5e20",
            hover_color="#2e7d32",
            command=self._toggle_local_relay
        )
        self.btn_toggle_local_server.pack(side="right", padx=20)

    def _copy_id_to_clipboard(self):
        self.clipboard_clear()
        self.clipboard_append(self.device_id.replace(" ", ""))
        self.btn_copy_id.configure(text="Copied!")
        self.after(2000, lambda: self.btn_copy_id.configure(text="Copy ID"))

    def _refresh_password(self):
        self.session_password = generate_session_password()
        self.lbl_pwd.configure(text=self.session_password)

    def _open_server_settings(self):
        dialog = ctk.CTkInputDialog(
            text="Enter Relay Server IP / Domain:\n(e.g., 127.0.0.1 or my-relay.example.com)",
            title="Relay Server Configuration"
        )
        new_server = dialog.get_input()
        if new_server and new_server.strip():
            srv = new_server.strip()
            if ":" in srv:
                host, port = srv.split(":", 1)
                self.relay_host = host
                self.relay_port = int(port)
            else:
                self.relay_host = srv
            self.lbl_server_info.configure(text=f"Relay Server: {self.relay_host}:{self.relay_port}")
            # Reconnect relay
            if self.relay_control_sock:
                try:
                    self.relay_control_sock.close()
                except Exception:
                    pass

    def _toggle_local_relay(self):
        """Starts or stops a built-in relay server on this machine"""
        if self.local_relay_instance is None:
            try:
                self.local_relay_instance = RelayServer(host="0.0.0.0", port=DEFAULT_RELAY_PORT)
                threading.Thread(target=self.local_relay_instance.start, daemon=True).start()
                self.btn_toggle_local_server.configure(text="Stop Relay", fg_color="#b71c1c", hover_color="#c62828")
                self.relay_host = "127.0.0.1"
                self.lbl_server_info.configure(text=f"Relay Server: {self.relay_host}:{self.relay_port} (Local)")
                messagebox.showinfo("Local Relay Started", f"Relay Server is now running on port {DEFAULT_RELAY_PORT}!\nOthers on your network/internet can connect via your IP: {self.local_ip}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to start local relay: {e}")
        else:
            self.local_relay_instance.running = False
            self.local_relay_instance = None
            self.btn_toggle_local_server.configure(text="Host Local Relay", fg_color="#1b5e20", hover_color="#2e7d32")

    def _maintain_relay_connection(self):
        """Persistent background worker keeping this machine registered to the Relay Server"""
        while self.running:
            try:
                self.after(0, lambda: self.status_badge.configure(text="● Connecting...", text_color="#ffb300"))
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(10.0)
                s.connect((self.relay_host, self.relay_port))
                s.settimeout(None)
                
                # Register host
                reg_msg = {
                    "type": "REGISTER_HOST",
                    "id": self.device_id,
                    "password": self.session_password
                }
                if not send_packet(s, reg_msg):
                    s.close()
                    time.sleep(3)
                    continue

                resp, _ = recv_packet(s)
                if not resp or resp.get("type") != "REGISTER_OK":
                    s.close()
                    time.sleep(3)
                    continue

                self.relay_control_sock = s
                self.is_registered = True
                self.after(0, lambda: self.status_badge.configure(text="● Ready to Connect", text_color="#00e676"))

                # Listen for incoming requests
                while self.running:
                    hdr, _ = recv_packet(s)
                    if not hdr:
                        break
                    
                    if hdr.get("type") == "INCOMING_PROMPT":
                        session_id = hdr.get("session_id")
                        viewer_addr = hdr.get("viewer_addr", "Remote User")
                        pwd = hdr.get("password", "")
                        
                        # Handle approval prompt on main thread
                        self.after(0, lambda sid=session_id, vaddr=viewer_addr, p=pwd: self._prompt_incoming_request(sid, vaddr, p))

            except Exception:
                pass
            finally:
                self.is_registered = False
                self.after(0, lambda: self.status_badge.configure(text="● Offline (Retrying)", text_color="#e53935"))
                if self.relay_control_sock:
                    try:
                        self.relay_control_sock.close()
                    except Exception:
                        pass
                    self.relay_control_sock = None
                time.sleep(3)

    def _prompt_incoming_request(self, session_id, viewer_addr, supplied_pwd):
        """Asks the user with a dialog to Accept or Decline incoming remote control"""
        # Auto-accept if correct session password supplied
        if supplied_pwd and supplied_pwd.strip().upper() == self.session_password.strip().upper():
            self._connect_host_bridge(session_id, True)
            return

        # Otherwise show prompt dialog
        top = ctk.CTkToplevel(self)
        top.title("Incoming Connection Request")
        top.geometry("420x220")
        top.attributes("-topmost", True)
        top.resizable(False, False)

        ctk.CTkLabel(
            top,
            text="⚠️ Incoming Connection!",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#ffab00"
        ).pack(pady=(20, 5))

        ctk.CTkLabel(
            top,
            text=f"A remote user ({viewer_addr})\nwants to view and control your desktop.",
            font=ctk.CTkFont(size=13),
            text_color="#cfd8dc"
        ).pack(pady=10)

        btn_box = ctk.CTkFrame(top, fg_color="transparent")
        btn_box.pack(pady=15)

        def on_accept():
            top.destroy()
            self._connect_host_bridge(session_id, True)

        def on_decline():
            top.destroy()
            self._connect_host_bridge(session_id, False, "User rejected the request")

        ctk.CTkButton(
            btn_box,
            text="✔ Accept",
            fg_color="#2e7d32",
            hover_color="#1b5e20",
            width=120,
            height=36,
            command=on_accept
        ).pack(side="left", padx=10)

        ctk.CTkButton(
            btn_box,
            text="✖ Decline",
            fg_color="#c62828",
            hover_color="#b71c1c",
            width=120,
            height=36,
            command=on_decline
        ).pack(side="right", padx=10)

    def _connect_host_bridge(self, session_id, accepted, reason=""):
        """Connects a new dedicated data socket to relay server for streaming screen"""
        def worker():
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect((self.relay_host, self.relay_port))
                msg = {
                    "type": "BRIDGE_SESSION_HOST",
                    "session_id": session_id,
                    "accepted": accepted,
                    "reason": reason
                }
                send_packet(s, msg)
                if accepted:
                    # Start host streaming over this socket!
                    self.active_streamer = HostStreamer(s, on_disconnect=self._on_host_stream_ended)
                    self.active_streamer.start()
                    self.after(0, lambda: self.status_badge.configure(text="● Streaming Screen...", text_color="#29b6f6"))
            except Exception as e:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def _on_host_stream_ended(self):
        self.active_streamer = None
        self.after(0, lambda: self.status_badge.configure(text="● Ready to Connect", text_color="#00e676"))

    def _direct_listen_loop(self):
        """Allows direct LAN or port-forwarded connections without relay server"""
        try:
            lsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            lsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            lsock.bind(("0.0.0.0", DIRECT_CONNECT_PORT))
            lsock.listen(5)
            while self.running:
                client_sock, client_addr = lsock.accept()
                if not self.running:
                    break
                # Prompt user for direct connection
                self.after(0, lambda sock=client_sock, addr=client_addr: self._prompt_direct_incoming(sock, addr))
        except Exception:
            pass

    def _prompt_direct_incoming(self, client_sock, client_addr):
        def on_accept():
            top.destroy()
            self.active_streamer = HostStreamer(client_sock, on_disconnect=self._on_host_stream_ended)
            self.active_streamer.start()
            self.status_badge.configure(text="● Direct Streaming...", text_color="#29b6f6")

        def on_decline():
            top.destroy()
            client_sock.close()

        top = ctk.CTkToplevel(self)
        top.title("Direct Connection Request")
        top.geometry("400x200")
        top.attributes("-topmost", True)
        
        ctk.CTkLabel(top, text="⚡ Direct LAN Connection", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(15, 5))
        ctk.CTkLabel(top, text=f"Remote Host {client_addr[0]} wants to connect directly.").pack(pady=10)
        
        btn_box = ctk.CTkFrame(top, fg_color="transparent")
        btn_box.pack(pady=10)
        ctk.CTkButton(btn_box, text="Accept", fg_color="#2e7d32", command=on_accept).pack(side="left", padx=10)
        ctk.CTkButton(btn_box, text="Decline", fg_color="#c62828", command=on_decline).pack(side="right", padx=10)

    def _on_connect_clicked(self):
        target = self.entry_remote_id.get().strip()
        pwd = self.entry_remote_pwd.get().strip()
        
        if not target:
            self.lbl_connect_status.configure(text="Please enter a Remote ID or IP address")
            return

        self.btn_connect.configure(state="disabled", text="Connecting...")
        self.lbl_connect_status.configure(text="Connecting to remote target...", text_color="#ffb300")
        
        threading.Thread(target=self._initiate_client_connection, args=(target, pwd), daemon=True).start()

    def _initiate_client_connection(self, target, pwd):
        clean_target = target.replace(" ", "")
        
        # Check if direct IP address entered (contains dots or colons)
        is_direct_ip = ("." in clean_target and not clean_target.isdigit()) or ":" in clean_target
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(15.0)

        try:
            if is_direct_ip:
                ip = clean_target
                port = DIRECT_CONNECT_PORT
                if ":" in clean_target:
                    ip, p = clean_target.split(":", 1)
                    port = int(p)
                sock.connect((ip, port))
            else:
                # Connect via Relay Server
                sock.connect((self.relay_host, self.relay_port))
                req = {
                    "type": "CONNECT_TARGET",
                    "target_id": clean_target,
                    "password": pwd
                }
                if not send_packet(sock, req):
                    raise Exception("Failed to send request to relay")

                resp, _ = recv_packet(sock)
                if not resp or resp.get("type") != "CONNECT_SUCCESS":
                    err_msg = resp.get("msg", "Connection failed") if resp else "Server timed out"
                    raise Exception(err_msg)

            sock.settimeout(None)
            
            # Connection succeeded! Open RemoteViewerWindow
            self.after(0, lambda: self._open_viewer_session(sock, target))

        except Exception as e:
            sock.close()
            self.after(0, lambda err=str(e): self._on_connect_failed(err))

    def _open_viewer_session(self, sock, target_id):
        self.btn_connect.configure(state="normal", text="➔ Connect")
        self.lbl_connect_status.configure(text="Connected successfully!", text_color="#00e676")
        self.active_viewer = RemoteViewerWindow(self, sock, target_id, on_close=self._on_viewer_closed)

    def _on_viewer_closed(self):
        self.active_viewer = None
        self.lbl_connect_status.configure(text="Session disconnected", text_color="#9e9ea8")

    def _on_connect_failed(self, error_msg):
        self.btn_connect.configure(state="normal", text="➔ Connect")
        self.lbl_connect_status.configure(text=f"Failed: {error_msg}", text_color="#e53935")

    def on_exit(self):
        self.running = False
        if self.relay_control_sock:
            try:
                self.relay_control_sock.close()
            except Exception:
                pass
        if self.active_streamer:
            self.active_streamer.stop()
        self.destroy()

if __name__ == "__main__":
    app = PyDeskApp()
    app.mainloop()
