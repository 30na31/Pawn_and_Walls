import socket
import threading
import json
import random
from typing import Optional, Tuple, List, Dict, Any, cast


HOST = "0.0.0.0"
PORT = 5000


class Client:
	def __init__(self, conn: socket.socket, addr: Tuple[str, int], name: str, pref: str):
		self.conn = conn
		self.addr = addr
		self.name = name
		self.pref = pref  # 'white' | 'black' | 'any'
		self.peer: Optional["Client"] = None
		self.role: Optional[str] = None  # 'white' | 'black'
		self.ready: threading.Event = threading.Event()


waiting_any: List[Client] = []
waiting_white: List[Client] = []
waiting_black: List[Client] = []
q_lock: threading.Lock = threading.Lock()
cv: threading.Condition = threading.Condition(q_lock)


def send_line(conn: socket.socket, obj: Dict[str, Any]) -> None:
	data = json.dumps(obj, separators=(",", ":")).encode("utf-8") + b"\n"
	conn.sendall(data)


def try_match(new_client: Client) -> Optional[Tuple[Client, Client]]:
	"""Try to find a match for new_client under q_lock.
	Return tuple (white_client, black_client) or None.
	"""
	def pop_other(lst: List[Client], exclude: Client) -> Optional[Client]:
		# pop the first client that is not the exclude
		for i, c in enumerate(lst):
			if c is not exclude:
				return lst.pop(i)
		return None

	if new_client.pref == "white":
		# Prefer complement, then any, then same
		other = pop_other(waiting_black, new_client) or pop_other(waiting_any, new_client)
		if other:
			return new_client, other
		other = pop_other(waiting_white, new_client)
		if other:
			# Both wanted white; assign new_client white, other black
			return new_client, other
		if new_client not in waiting_white:
			waiting_white.append(new_client)
		return None

	if new_client.pref == "black":
		other = pop_other(waiting_white, new_client) or pop_other(waiting_any, new_client)
		if other:
			return other, new_client
		other = pop_other(waiting_black, new_client)
		if other:
			# Both wanted black; assign other white, new_client black
			return other, new_client
		if new_client not in waiting_black:
			waiting_black.append(new_client)
		return None

	# any
	other = pop_other(waiting_white, new_client) or pop_other(waiting_black, new_client) or pop_other(waiting_any, new_client)
	if other:
		if other.pref == "white":
			return other, new_client
		if other.pref == "black":
			return new_client, other
		# both any: assign randomly to reduce bias
		return (other, new_client) if random.random() < 0.5 else (new_client, other)

	if new_client not in waiting_any:
		waiting_any.append(new_client)
	return None


def remove_waiting(client: Client) -> None:
	"""Remove client from any waiting list if present (under q_lock)."""
	def _remove(lst: List[Client]):
		try:
			lst.remove(client)
		except ValueError:
			pass
	_remove(waiting_any)
	_remove(waiting_white)
	_remove(waiting_black)


def _conn_closed(sock: socket.socket) -> bool:
	try:
		sock.settimeout(0.0)
		try:
			data = sock.recv(1, socket.MSG_PEEK)
		except BlockingIOError:
			return False
		return data == b""
	except Exception:
		return True
	finally:
		try:
			sock.settimeout(None)
		except Exception:
			pass


def handle_client(conn: socket.socket, addr: Tuple[str, int]) -> None:
	conn_file = conn.makefile("rwb")
	me: Optional[Client] = None
	try:
		line = conn_file.readline()
		if not line:
			return
		try:
			msg = json.loads(line.decode("utf-8"))
		except Exception:
			send_line(conn, {"type": "error", "message": "invalid json"})
			return

		if not isinstance(msg, dict):
			send_line(conn, {"type": "error", "message": "invalid message"})
			return

		msg_dict: Dict[str, Any] = cast(Dict[str, Any], msg)
		msg_type = str(msg_dict.get("type") or "")
		if msg_type != "join":
			send_line(conn, {"type": "error", "message": "expected join"})
			return

		name = str(msg_dict.get("name") or "Player")[:32]
		pref = str(msg_dict.get("pref") or "any").lower()
		if pref not in ("white", "black", "any"):
			pref = "any"

		print(f"[server] join from {addr}: name='{name}', pref='{pref}'")
		me = Client(conn, addr, name, pref)

		with cv:
			pair = try_match(me)
			while True:
				if pair is not None:
					white_client, black_client = pair
					# set roles and peers
					white_client.role = "white"
					black_client.role = "black"
					white_client.peer = black_client
					black_client.peer = white_client
					white_client.ready.set()
					black_client.ready.set()
					print(f"[server] matched: white='{white_client.name}' vs black='{black_client.name}'")
					cv.notify_all()
					break
				# If another thread already matched us, stop trying
				if me.ready.is_set() or me.peer is not None:
					break
				# wait for someone new to arrive (with timeout to detect disconnect)
				cv.wait(timeout=2.0)
				if _conn_closed(conn):
					remove_waiting(me)
					cv.notify_all()
					return
				pair = try_match(me)

		# At this point, me.ready should be set and roles assigned
		if me.role is None or me.peer is None:
			return

		# Send start to this client
		try:
			send_line(me.conn, {"type": "start", "you": me.role, "opponent": me.peer.name})
			print(f"[server] start sent to '{me.name}': you='{me.role}', opponent='{me.peer.name}'")
		except Exception:
			return

		# Relay loop: forward move lines to peer
		me.conn.settimeout(1.0)
		peer_conn: socket.socket = me.peer.conn
		buffer: bytes = b""
		while True:
			try:
				chunk = me.conn.recv(4096)
				if not chunk:
					break
				buffer += chunk
				while True:
					idx = buffer.find(b"\n")
					if idx == -1:
						break
					one = buffer[:idx]
					buffer = buffer[idx+1:]
					try:
						one_s = one.decode("utf-8")
						payload: Any = json.loads(one_s)
					except Exception:
						continue
					if isinstance(payload, dict):
						payload_dict: Dict[str, Any] = cast(Dict[str, Any], payload)
						p_type = str(payload_dict.get("type") or "")
						if p_type == "move":
							# Validate peer socket before attempting to send
							try:
								if (peer_conn is None) or (getattr(peer_conn, 'fileno', lambda: -1)() == -1) or _conn_closed(peer_conn):
									print("[server] peer socket invalid or closed; stopping relay")
									break
							except Exception:
								print("[server] peer socket check failed; stopping relay")
								break
							try:
								print(f"[server] relay move from '{me.name}' to '{me.peer.name}': {payload_dict}")
								send_line(peer_conn, payload_dict)
							except Exception as e:
								print(f"[server] relay failed: {e}")
								break
			except socket.timeout:
				# also check if peer closed
				if _conn_closed(peer_conn):
					break
				continue
			except Exception:
				break

		# notify peer that session ended
		try:
			send_line(peer_conn, {"type": "end"})
		except Exception:
			pass
	finally:
		with cv:
			if me is not None:
				remove_waiting(me)
			cv.notify_all()
		try:
			conn.shutdown(socket.SHUT_RDWR)
		except Exception:
			pass
		try:
			conn.close()
		except Exception:
			pass


def serve() -> None:
	print(f"Matchmaking server listening on {HOST}:{PORT}")
	with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
		s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		s.bind((HOST, PORT))
		s.listen()
		while True:
			conn, addr = s.accept()
			# Notify waiters that a new client arrived
			with cv:
				t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
				t.start()
				cv.notify_all()


if __name__ == "__main__":
	try:
		serve()
	except KeyboardInterrupt:
		print("\nServer stopped.")
