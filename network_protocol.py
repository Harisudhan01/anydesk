import struct
import json
import socket

def send_packet(sock: socket.socket, header_dict: dict, raw_payload: bytes = b""):
    """
    Sends framed message:
    [4 bytes total payload length]
    [4 bytes JSON header length]
    [JSON bytes]
    [raw_payload bytes]
    """
    try:
        json_bytes = json.dumps(header_dict).encode("utf-8")
        json_len = len(json_bytes)
        total_len = 4 + json_len + len(raw_payload)
        
        full_msg = struct.pack("!II", total_len, json_len) + json_bytes + raw_payload
        sock.sendall(full_msg)
        return True
    except (socket.error, OSError):
        return False

def recv_exact(sock: socket.socket, num_bytes: int):
    """Receives exact number of bytes from socket or returns None on disconnect"""
    data = bytearray()
    while len(data) < num_bytes:
        try:
            packet = sock.recv(num_bytes - len(data))
            if not packet:
                return None
            data.extend(packet)
        except (socket.error, OSError):
            return None
    return bytes(data)

def recv_packet(sock: socket.socket):
    """
    Reads a single framed message.
    Returns (header_dict, raw_payload) or (None, None) if closed.
    """
    length_prefix = recv_exact(sock, 8)
    if not length_prefix:
        return None, None
        
    total_len, json_len = struct.unpack("!II", length_prefix)
    
    if json_len > total_len:
        return None, None
        
    json_bytes = recv_exact(sock, json_len)
    if not json_bytes:
        return None, None
        
    try:
        header_dict = json.loads(json_bytes.decode("utf-8"))
    except Exception:
        return None, None
        
    raw_payload_len = total_len - 4 - json_len
    raw_payload = b""
    if raw_payload_len > 0:
        raw_payload = recv_exact(sock, raw_payload_len)
        if raw_payload is None:
            return None, None
            
    return header_dict, raw_payload
