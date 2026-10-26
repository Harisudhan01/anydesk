import os
import socket
import threading
import uuid
import time
from network_protocol import send_packet, recv_packet
from config import DEFAULT_RELAY_PORT

class RelayServer:
    """
    Central Signaling & Data Relay Server.
    Enables remote connection over the internet across any NAT or Firewall.
    """
    def __init__(self, host="0.0.0.0", port=None):
        self.host = host
        env_port = os.environ.get("PORT")
        self.port = int(env_port) if env_port else (port or DEFAULT_RELAY_PORT)
        self.running = False
        
        # registered_hosts: id -> { "control_sock": sock, "password": pass, "ip": ip }
        self.registered_hosts = {}
        # pending_sessions: session_id -> { "viewer_sock": sock, "target_id": id, "event": threading.Event(), "host_sock": None }
        self.pending_sessions = {}
        self.lock = threading.Lock()

    def start(self):
        self.running = True
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind((self.host, self.port))
        self.server_sock.listen(100)
        print(f"[RELAY SERVER] Listening on {self.host}:{self.port} ...")
        
        while self.running:
            try:
                client_sock, client_addr = self.server_sock.accept()
                threading.Thread(target=self._handle_client, args=(client_sock, client_addr), daemon=True).start()
            except Exception:
                break

    def _normalize_id(self, raw_id: str) -> str:
        return raw_id.replace(" ", "").strip()

    def _handle_client(self, client_sock: socket.socket, client_addr):
        header, _ = recv_packet(client_sock)
        if not header:
            client_sock.close()
            return
            
        action = header.get("type")
        
        if action == "REGISTER_HOST":
            self._handle_host_registration(client_sock, client_addr, header)
        elif action == "CONNECT_TARGET":
            self._handle_viewer_connection(client_sock, client_addr, header)
        elif action == "BRIDGE_SESSION_HOST":
            self._handle_host_bridge(client_sock, header)
        else:
            client_sock.close()

    def _handle_host_registration(self, sock, addr, header):
        raw_id = header.get("id", "")
        clean_id = self._normalize_id(raw_id)
        password = header.get("password", "")
        
        with self.lock:
            self.registered_hosts[clean_id] = {
                "control_sock": sock,
                "password": password,
                "addr": addr
            }
        print(f"[RELAY] Host registered: {clean_id} from {addr}")
        send_packet(sock, {"type": "REGISTER_OK", "id": clean_id})
        
        # Keep connection open for incoming signal alerts
        try:
            while self.running:
                hdr, _ = recv_packet(sock)
                if hdr is None:
                    break
        except Exception:
            pass
        finally:
            with self.lock:
                if clean_id in self.registered_hosts and self.registered_hosts[clean_id]["control_sock"] == sock:
                    del self.registered_hosts[clean_id]
            print(f"[RELAY] Host disconnected: {clean_id}")
            sock.close()

    def _handle_viewer_connection(self, viewer_sock, addr, header):
        raw_target = header.get("target_id", "")
        clean_target = self._normalize_id(raw_target)
        pwd = header.get("password", "")
        
        host_info = None
        with self.lock:
            host_info = self.registered_hosts.get(clean_target)
            
        if not host_info:
            send_packet(viewer_sock, {"type": "CONNECT_ERROR", "msg": "Device ID offline or does not exist."})
            viewer_sock.close()
            return

        session_id = str(uuid.uuid4())
        session_event = threading.Event()
        
        with self.lock:
            self.pending_sessions[session_id] = {
                "viewer_sock": viewer_sock,
                "target_id": clean_target,
                "event": session_event,
                "host_sock": None,
                "accepted": False,
                "reason": "Timeout"
            }

        # Request host approval
        incoming_msg = {
            "type": "INCOMING_PROMPT",
            "session_id": session_id,
            "viewer_addr": f"{addr[0]}:{addr[1]}",
            "password": pwd
        }
        
        if not send_packet(host_info["control_sock"], incoming_msg):
            send_packet(viewer_sock, {"type": "CONNECT_ERROR", "msg": "Host is unreachable."})
            viewer_sock.close()
            with self.lock:
                self.pending_sessions.pop(session_id, None)
            return

        # Wait up to 30 seconds for host to respond and connect bridge
        signaled = session_event.wait(timeout=30.0)
        
        session_data = None
        with self.lock:
            session_data = self.pending_sessions.pop(session_id, None)

        if not signaled or not session_data or not session_data.get("accepted"):
            err_reason = session_data.get("reason", "Connection rejected or timed out") if session_data else "Timed out"
            send_packet(viewer_sock, {"type": "CONNECT_ERROR", "msg": err_reason})
            viewer_sock.close()
            return

        # Both host and viewer sockets are now ready for bridging!
        host_sock = session_data["host_sock"]
        send_packet(viewer_sock, {"type": "CONNECT_SUCCESS"})
        
        print(f"[RELAY] Active bridge established for session {session_id} between Host and Viewer")
        self._bridge_sockets(host_sock, viewer_sock)

    def _handle_host_bridge(self, host_sock, header):
        session_id = header.get("session_id")
        accepted = header.get("accepted", False)
        reason = header.get("reason", "User declined")
        
        with self.lock:
            session_data = self.pending_sessions.get(session_id)
            if session_data:
                session_data["accepted"] = accepted
                session_data["reason"] = reason
                session_data["host_sock"] = host_sock
                session_data["event"].set()

    def _bridge_sockets(self, sock1, sock2):
        """Pipes all raw data seamlessly between Host and Viewer"""
        def forward(source, destination):
            try:
                while self.running:
                    data = source.recv(65536)
                    if not data:
                        break
                    destination.sendall(data)
            except Exception:
                pass
            finally:
                try:
                    source.close()
                except Exception:
                    pass
                try:
                    destination.close()
                except Exception:
                    pass

        t1 = threading.Thread(target=forward, args=(sock1, sock2), daemon=True)
        t2 = threading.Thread(target=forward, args=(sock2, sock1), daemon=True)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

if __name__ == "__main__":
    server = RelayServer()
    try:
        server.start()
    except KeyboardInterrupt:
        print("\n[RELAY SERVER] Stopped.")
