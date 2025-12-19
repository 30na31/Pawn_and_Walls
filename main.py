import pygame
import os
import sys
import socket
import threading
import json
from typing import Optional, List, Dict, Any, Tuple, cast

pygame.init()
WIDTH, HEIGHT = 1100, 900
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
pygame.display.set_caption(f"Name Entry")



FONT = pygame.font.SysFont(None, 28)
BIG = pygame.font.SysFont(None, 36)
# co
BG = (235, 235, 240)
TEXT = (20, 20, 20)
LABEL = (90, 90, 90)
BORDER_ACTIVE = (50, 120, 220)
BORDER_INACTIVE = (150, 150, 160)
BUTTON_BG = (70, 130, 180)
BUTTON_TEXT = (255, 255, 255)
INPUT_BG = (255, 255, 255)


input_w, input_h = 360, 44
button_w, button_h = 140, 44

label_surf = FONT.render("Username", True, LABEL)
server_label_surf = FONT.render("Server", True, LABEL)

label_pos = [WIDTH // 2 - label_surf.get_width() // 2, 24]

input_rect = pygame.Rect(0, 0, input_w, input_h)
input_rect.centerx = WIDTH // 2
input_rect.top = label_pos[1] + label_surf.get_height() + 12

server_input_rect = pygame.Rect(0, 0, input_w, input_h)
server_input_rect.centerx = WIDTH // 2
server_input_rect.top = input_rect.bottom + 28

button_rect = pygame.Rect(0, 0, button_w, button_h)
button_rect.centerx = WIDTH // 2
button_rect.top = server_input_rect.bottom + 16

active_field: Optional[str] = None  # 'name' | 'server'
text = ""
server_text = ""

clock = pygame.time.Clock()

server_host = "127.0.0.1"
server_port = 5000


def _parse_server_endpoint(text: str) -> tuple[str, int]:
    host = server_host
    port = server_port
    s = (text or "").strip()
    if not s:
        return host, port
    try:
        if ":" in s:
            h, p = s.rsplit(":", 1)
            if h:
                host = h.strip()
            if p:
                port = int(p.strip())
        elif s.isdigit():
            port = int(s)
        else:
            host = s
    except Exception:
        pass
    return host, port

_env_server = os.environ.get("PAWN_SERVER")
if _env_server:
    server_host, server_port = _parse_server_endpoint(_env_server)

for i, arg in enumerate(sys.argv):
    if arg == "--server" and i + 1 < len(sys.argv):
        server_host, server_port = _parse_server_endpoint(sys.argv[i + 1])
        break

def draw_board(name_value: str, your_color: Optional[str] = None, sock: Optional[socket.socket] = None) -> None:

    caption_label = name_value
    if your_color:
        caption_label += f" ({your_color})"
    pygame.display.set_caption(caption_label)
    squares = 9
    margin = 60  
    def compute_layout():
        cur_w, cur_h = screen.get_size()
        board_size = min(cur_w, cur_h) - margin * 2
        board_size = max(board_size, squares * 30) 
        sq_ = board_size // squares
        board_size = sq_ * squares
        left_ = (cur_w - board_size) // 2
        top_ = (cur_h - board_size) // 2
        return sq_, board_size, left_, top_
    sq, board_size, left, top = compute_layout()

    GREEN = (118, 150, 86)
    WHITE = (255, 255, 255)

    title_text = FONT.render("Press ESC to return", True, LABEL)

    if " vs " in name_value:
        my_name, opp_name = name_value.split(" vs ", 1)
    else:
        my_name, opp_name = name_value, "Opponent"

    try:
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            base_dir = sys._MEIPASS  # type: ignore[attr-defined]
        else:
            base_dir = os.path.dirname(__file__)
    except Exception:
        base_dir = os.path.dirname(__file__)
    white_pawn_path = os.path.join(base_dir, "white pawn.png")  # type: ignore
    black_pawn_path = os.path.join(base_dir, "black pawn.png")  # type: ignore

    def load_piece(path: str, size: int):
        try:
            img = pygame.image.load(path).convert_alpha()
            target = (int(size * 0.9), int(size * 0.9))
            return pygame.transform.smoothscale(img, target)
        except Exception:
            return None

    white_img = load_piece(white_pawn_path, sq)
    black_img = load_piece(black_pawn_path, sq)

    # Board state: positions as (row, col)
    col_e = 4
    row_1 = squares - 1
    row_9 = 0
    positions = {
        "white": (row_1, col_e),
        "black": (row_9, col_e),
    }


    horizontal_walls: set[Tuple[int, int]] = set()  # anchors for horizontal walls
    vertical_walls: set[Tuple[int, int]] = set()    # anchors for vertical walls
    max_walls_per_player = 9
    walls_remaining = {"white": max_walls_per_player, "black": max_walls_per_player}
    placing_wall = False
    wall_preview: Optional[Tuple[str, int, int]] = None  # (orientation, r, c)
    wall_error_msg: Optional[str] = None
    wall_error_ts: int = 0

    # Turn management
    turn: str = "white"

    # View orientation
    flip_view: bool = (your_color == "black")

    def to_display_rc(r: int, c: int) -> Tuple[int, int]:
        if not flip_view:
            return r, c
        return (squares - 1 - r, squares - 1 - c)

    def from_display_rc(dr: int, dc: int) -> Tuple[int, int]:
        # inverse of to_display_rc 
        if not flip_view:
            return dr, dc
        return (squares - 1 - dr, squares - 1 - dc)


    def anchor_to_display_rc(r: int, c: int) -> Tuple[int, int]:
        if not flip_view:
            return r, c
        return ( (squares - 2) - r, (squares - 2) - c )

    def anchor_from_display_rc(dr: int, dc: int) -> Tuple[int, int]:
        if not flip_view:
            return dr, dc
        return ( (squares - 2) - dr, (squares - 2) - dc )

    def mouse_to_logical(mx: int, my: int) -> Optional[Tuple[int, int]]:
        dc = (mx - left) // sq
        dr = (my - top) // sq
        if 0 <= dr < squares and 0 <= dc < squares:
            r, c = from_display_rc(int(dr), int(dc))
            return (r, c)
        return None

    dragging = False
    drag_color: Optional[str] = None
    drag_offset = (0, 0)
    drag_pos_px = (0, 0)


    state_lock = threading.Lock()
    pending_moves: List[Dict[str, Any]] = []
    opponent_left = threading.Event()


    last_move: Optional[Tuple[str, Tuple[int, int], int]] = None  


    rematch_local_request = False
    rematch_remote_request = False

    game_over = False
    winner_color: Optional[str] = None
    winner_name: Optional[str] = None
    win_announced = False
    white_score = 0
    black_score = 0
    score_updated_for_game = False

    def check_and_set_victory(trigger_color: Optional[str] = None, announce: bool = True):

        nonlocal game_over, winner_color, winner_name, win_announced, white_score, black_score, score_updated_for_game
        if game_over:
            return
        # White victory
        if positions["white"][0] == 0:
            game_over = True
            winner_color = "white"
        # Black victory
        elif positions["black"][0] == squares - 1:
            game_over = True
            winner_color = "black"
        if game_over:
            # Increment score 
            if not score_updated_for_game and winner_color in ("white", "black"):
                if winner_color == "white":
                    white_score += 1
                else:
                    black_score += 1
                score_updated_for_game = True
            if your_color == winner_color:
                # local player won
                if " vs " in name_value:
                    winner = name_value.split(" vs ", 1)[0] if your_color in ("white", "black") else name_value
                else:
                    winner = name_value
                winner_name = winner
            else:
                # Opponent possibly won
                if " vs " in name_value:
                    parts = name_value.split(" vs ", 1)
                    if your_color in ("white", "black"):
                        winner_name = parts[1]
                    else:
                        winner_name = parts[0]
                else:
                    winner_name = "Opponent"
            if announce and sock and not win_announced:
                try:
                    msg = {"type": "win", "winner_color": winner_color, "winner_name": winner_name} # type: ignore
                    sock.sendall(json.dumps(msg).encode("utf-8") + b"\n")
                    win_announced = True
                except Exception:
                    pass

    def reset_game_state():
        nonlocal positions, turn, last_move, dragging, drag_color, rematch_local_request, rematch_remote_request, game_over, winner_color, winner_name, win_announced, score_updated_for_game, horizontal_walls, vertical_walls, walls_remaining, placing_wall, wall_preview
        positions = {"white": (row_1, col_e), "black": (row_9, col_e)}
        turn = "white"
        last_move = None
        dragging = False
        drag_color = None
        rematch_local_request = False
        rematch_remote_request = False
        game_over = False
        winner_color = None
        winner_name = None
        win_announced = False
        score_updated_for_game = False
        horizontal_walls.clear()
        vertical_walls.clear()
        walls_remaining = {"white": max_walls_per_player, "black": max_walls_per_player}
        placing_wall = False
        wall_preview = None

    def legal_moves(r: int, c: int) -> List[Tuple[int, int]]:
        # cardinal step moves
        deltas = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        step_candidates = [(r + dr, c + dc) for dr, dc in deltas]
        in_bounds_steps = [(rr, cc) for rr, cc in step_candidates if 0 <= rr < squares and 0 <= cc < squares]

        occ = {positions["white"], positions["black"]}
        # wall blocking helper
        def blocked(a: Tuple[int, int], b: Tuple[int, int]) -> bool:
            ar, ac = a
            br, bc = b
            dr = br - ar
            dc = bc - ac

            if dc == 0 and abs(dr) == 1:
                if dr == -1:  
                    return (ar-1, ac if ac < squares-1 else ac-1) in horizontal_walls or (ar-1, ac-1) in horizontal_walls
                else:  
                    return (ar, ac if ac < squares-1 else ac-1) in horizontal_walls or (ar, ac-1) in horizontal_walls
            # Horizontal pawn movement
            if dr == 0 and abs(dc) == 1:
                if dc == -1: 
                    return (ar if ar < squares-1 else ar-1, ac-1) in vertical_walls or (ar-1, ac-1) in vertical_walls
                else:  
                    return (ar if ar < squares-1 else ar-1, ac) in vertical_walls or (ar-1, ac) in vertical_walls
            return False

        moves: List[Tuple[int, int]] = [(rr, cc) for rr, cc in in_bounds_steps if (rr, cc) not in occ and not blocked((r, c), (rr, cc))]

        mover_color: Optional[str] = None
        if positions["white"] == (r, c):
            mover_color = "white"
            opponent_pos = positions["black"]
        elif positions["black"] == (r, c):
            mover_color = "black"
            opponent_pos = positions["white"]
        else:
            opponent_pos = None  # type: ignore

        if mover_color is not None and opponent_pos is not None:
            for dr, dc in deltas:
                adj = (r + dr, c + dc)
                land = (r + 2 * dr, c + 2 * dc)
                if adj == opponent_pos:
                    lr, lc = land
                    if 0 <= lr < squares and 0 <= lc < squares and land not in occ:
                        if not blocked((r, c), adj) and not blocked(adj, land):
                            moves.append(land)

        # Remove duplicates 
        seen = set() # type: ignore
        uniq_moves: List[Tuple[int, int]] = []
        for m in moves:
            if m not in seen:
                seen.add(m) # type: ignore
                uniq_moves.append(m)
        return uniq_moves

    def piece_color_at(r: int, c: int) -> Optional[str]:
        if positions["white"] == (r, c):
            return "white"
        if positions["black"] == (r, c):
            return "black"
        return None

    def send_move(from_rc: Tuple[int, int], to_rc: Tuple[int, int], color: str) -> None:
        if not sock:
            return
        try:
            msg = json.dumps({"type": "move", "from": list(from_rc), "to": list(to_rc), "color": color}).encode("utf-8") + b"\n"
            sock.sendall(msg)
            # Log locally to help debug networking
            print(f"[client] sent move: {color} {from_rc} -> {to_rc}")
        except Exception:
            pass

    def send_wall(orientation: str, r: int, c: int, color: str) -> None:
        if not sock:
            return
        try:
            msg = json.dumps({"type": "wall", "o": orientation, "r": r, "c": c, "color": color}).encode("utf-8") + b"\n"
            sock.sendall(msg)
            print(f"[client] sent wall: {color} {orientation} ({r},{c})")
        except Exception:
            pass

    def can_place_wall(orientation: str, r: int, c: int) -> bool:
        if orientation == 'h':
            if not (0 <= r <= squares - 2 and 0 <= c <= squares - 2):
                return False
            if (r, c) in horizontal_walls:
                return False
            if (r, c - 1) in horizontal_walls:
                return False
            if (r, c + 1) in horizontal_walls:
                return False
            if (r, c) in vertical_walls:
                return False
            return True
        elif orientation == 'v':
            if not (0 <= r <= squares - 2 and 0 <= c <= squares - 2):
                return False
            if (r, c) in vertical_walls:
                return False
            if (r - 1, c) in vertical_walls:
                return False
            if (r + 1, c) in vertical_walls:
                return False
            if (r, c) in horizontal_walls:
                return False
            return True
        else:
            return False

    def place_wall(orientation: str, r: int, c: int, color: str, remote: bool = False) -> bool:
        nonlocal wall_error_msg, wall_error_ts
        if remote:
            if orientation not in ("h", "v"):
                return False
            if not (0 <= r <= squares - 2 and 0 <= c <= squares - 2):
                return False
            if orientation == 'h':
                if (r, c) in horizontal_walls:
                    return False
                horizontal_walls.add((r, c))
            else:
                if (r, c) in vertical_walls:
                    return False
                vertical_walls.add((r, c))
            try:
                drw, dcw = anchor_to_display_rc(r, c)
                print(f"[client] remote wall applied {color} {orientation} ({r},{c}) -> display=({drw},{dcw})")
            except Exception:
                pass
            if walls_remaining[color] > 0:
                walls_remaining[color] -= 1
            return True

        if walls_remaining[color] <= 0:
            return False
        if not can_place_wall(orientation, r, c):
            return False
        if orientation == 'h':
            if (r, c) in horizontal_walls:
                return False
            horizontal_walls.add((r, c))
        else:
            if (r, c) in vertical_walls:
                return False
            vertical_walls.add((r, c))
        # Debug placement mapping
        try:
            drw, dcw = anchor_to_display_rc(r, c)
            print(f"[debug wall] placed {orientation} anchor=({r},{c}) color={color} flip={flip_view} -> display_anchor=({drw},{dcw})")
        except Exception:
            pass
        def has_path(start: Tuple[int, int], target_rows: set[int]) -> bool:
            from collections import deque
            seen = {start}
            dq = deque([start])
            while dq:
                cr, cc = dq.popleft()
                if cr in target_rows:
                    return True
                for nr, nc in legal_moves(cr, cc):
                    if (nr, nc) not in seen:
                        seen.add((nr, nc))
                        dq.append((nr, nc))
            return False
        white_ok = has_path(positions['white'], {0})
        black_ok = has_path(positions['black'], {squares - 1})
        if not (white_ok and black_ok):
            if orientation == 'h':
                horizontal_walls.discard((r, c))
            else:
                vertical_walls.discard((r, c))
            # Show message to the local player
            wall_error_msg = "The wall can't be placed here Idiot!!"
            wall_error_ts = pygame.time.get_ticks()
            return False
        if walls_remaining[color] > 0:
            walls_remaining[color] -= 1
        return True

    def listen_loop():
        if not sock:
            return
        nonlocal rematch_remote_request, rematch_local_request, game_over, winner_color, winner_name, win_announced, score_updated_for_game, turn, white_score, black_score, your_color, flip_view
        sock.settimeout(0.5)
        buf: bytes = b""
        while True:
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                buf += chunk
                while True:
                    nl = buf.find(b"\n")
                    if nl == -1:
                        break
                    one = buf[:nl]
                    buf = buf[nl+1:]
                    try:
                        one_str: str = one.decode("utf-8")
                        payload_any: Any = json.loads(one_str)
                    except Exception:
                        continue
                    if isinstance(payload_any, dict):
                        payload = cast(Dict[str, Any], payload_any)
                        p_type = str(payload.get("type") or "")
                        if p_type == "move":
                            with state_lock:
                                pending_moves.append(payload)
                        elif p_type == "wall":
                            o = str(payload.get("o") or "")
                            r_any = payload.get("r")
                            c_any = payload.get("c")
                            w_color = str(payload.get("color") or "")
                            if o in ("h", "v") and isinstance(r_any, int) and isinstance(c_any, int) and w_color in ("white", "black"):
                                applied = place_wall(o, int(r_any), int(c_any), w_color, remote=True)
                                if applied:
                                    print(f"[client] remote wall {w_color} {o} ({r_any},{c_any})")
                                    if turn == w_color:
                                        turn = 'white' if w_color == 'black' else 'black'
                        elif p_type == "rematch":
                            if game_over:
                                print("[client] rematch request received")
                                rematch_remote_request = True
                        elif p_type == "rematch_start":
                            new_you = payload.get("you")
                            if isinstance(new_you, str) and new_you in ("white", "black"):
                                your_color = new_you
                                flip_view = (your_color == "black")
                            print("[client] rematch_start received -> resetting game state, you=", your_color)
                            reset_game_state()
                            turn = "white"
                            rematch_local_request = False
                            rematch_remote_request = False
                        elif p_type == "win":
                            # Opponent announced a win
                            winner_color_msg = payload.get("winner_color")
                            name_msg = payload.get("winner_name")
                            if isinstance(winner_color_msg, str):
                                winner_color_local = winner_color_msg
                            else:
                                winner_color_local = None
                            if isinstance(name_msg, str):
                                winner_name_local = name_msg
                            else:
                                winner_name_local = "Opponent"
                            if not game_over:
                                game_over = True
                                winner_color = winner_color_local
                                winner_name = winner_name_local
                                win_announced = True
                                if not score_updated_for_game and winner_color in ("white", "black"):
                                    if winner_color == "white":
                                        white_score += 1
                                    else:
                                        black_score += 1
                                    score_updated_for_game = True
                        elif p_type == "end":
                            opponent_left.set()
                            return
            except socket.timeout:
                continue
            except Exception:
                break

    listener = None
    if sock is not None:
        listener = threading.Thread(target=listen_loop, daemon=True)
        listener.start()

    running_board = True
    while running_board:
        sq, board_size, left, top = compute_layout()
        if sock is not None:
            with state_lock:
                while pending_moves:
                    mv = pending_moves.pop(0)
                    color = str(mv.get("color") or "")
                    fr_any = mv.get("from")
                    to_any = mv.get("to")
                    if (
                        color in ("white", "black") and
                        isinstance(fr_any, list) and len(cast(List[Any], fr_any)) == 2 and
                        isinstance(to_any, list) and len(cast(List[Any], to_any)) == 2
                    ):
                        try:
                            to_list = cast(List[Any], to_any)
                            tr = (int(to_list[0]), int(to_list[1]))
                            positions[color] = tr
                            last_move = (color, tr, pygame.time.get_ticks())
                            print(f"[client] received move: {color} -> {tr}")
                            pre_go = game_over # type: ignore
                            check_and_set_victory(trigger_color=color, announce=False)
                            if not game_over:
                                turn = "black" if color == "white" else "white"
                        except Exception:
                            pass

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if game_over and not opponent_left.is_set():
                        # Treat ESC during game over as rematch request
                        if not rematch_local_request:
                            rematch_local_request = True
                            if sock:
                                try:
                                    sock.sendall(json.dumps({"type": "rematch"}).encode("utf-8") + b"\n")
                                except Exception:
                                    pass
                            # Wait for server to send rematch_start
                            pass
                    else:
                        # Exit to entry screen
                        running_board = False
                if event.key == pygame.K_w and not game_over and (your_color == turn) and walls_remaining.get(your_color,0) > 0: # type: ignore
                    # Toggle wall placement mode
                    placing_wall = not placing_wall
                    wall_preview = None
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if opponent_left.is_set():
                    # Ignore further interaction after opponent leaves
                    continue
                # Rematch button geometry (always active unless opponent left)
                cur_w, cur_h = screen.get_size()
                btn_w, btn_h = 140, 40
                btn_margin = 10
                rematch_rect = pygame.Rect(cur_w - btn_w - btn_margin, btn_margin, btn_w, btn_h)
                if rematch_rect.collidepoint(event.pos):
                    if not rematch_local_request:
                        rematch_local_request = True
                        if sock:
                            try:
                                sock.sendall(json.dumps({"type": "rematch"}).encode("utf-8") + b"\n")
                            except Exception:
                                pass
                    if rematch_remote_request:
                        # Wait for server to send rematch_start
                        pass
                    continue  # handled click
                if game_over:
                    # Treat board click as implicit rematch request
                    if not rematch_local_request:
                        rematch_local_request = True
                        if sock:
                            try:
                                sock.sendall(json.dumps({"type": "rematch"}).encode("utf-8") + b"\n")
                            except Exception:
                                pass
                    if rematch_remote_request:
                        # Wait for server to send rematch_start
                        pass
                    continue  # don't allow moving during game over
                mx, my = event.pos
                # If placing wall, commit placement based on preview
                if placing_wall and not game_over and (your_color == turn):
                    if wall_preview is not None:
                        o, wr, wc = wall_preview
                        # wr,wc already normalized anchor (0..squares-2)
                        if place_wall(o, wr, wc, your_color): # type: ignore
                            send_wall(o, wr, wc, your_color) # type: ignore
                            turn = 'black' if turn == 'white' else 'white'
                    placing_wall = False
                    wall_preview = None
                    continue
                maybe_rc = mouse_to_logical(mx, my)
                if maybe_rc is not None:
                    lr, lc = maybe_rc
                    clicked_color = piece_color_at(lr, lc)
                    if (
                        clicked_color is not None
                        and clicked_color == turn
                        and (your_color is None or clicked_color == your_color)
                    ):
                        dragging = True
                        drag_color = clicked_color
                        d_r, d_c = to_display_rc(lr, lc)
                        center_x = left + d_c * sq + sq // 2
                        center_y = top + d_r * sq + sq // 2
                        drag_offset = (mx - center_x, my - center_y)
                        drag_pos_px = (mx, my)
            if event.type == pygame.MOUSEMOTION:
                mx, my = event.pos
                if placing_wall:
                    mods = pygame.key.get_mods()
                    orientation = 'h'
                    if mods & pygame.KMOD_SHIFT:
                        orientation = 'v'
                    dc = (mx - left) // sq
                    dr = (my - top) // sq
                    if 0 <= dr < squares-1 and 0 <= dc < squares-1:
                        ar, ac = anchor_from_display_rc(int(dr), int(dc))
                        if can_place_wall(orientation, ar, ac):
                            wall_preview = (orientation, ar, ac)
                        else:
                            wall_preview = None
                    else:
                        wall_preview = None
                if dragging and not opponent_left.is_set():
                    drag_pos_px = event.pos
            if event.type == pygame.MOUSEBUTTONUP and event.button == 1 and dragging:
                if opponent_left.is_set():
                    dragging = False
                    drag_color = None
                else:
                    mx, my = event.pos
                    dest = mouse_to_logical(mx, my)
                    yours = drag_color or (your_color or "white") # type: ignore
                    from_rc = positions[yours]
                    lm = legal_moves(*from_rc)
                    if dest is not None:
                        row, col = dest
                        if (row, col) in lm:
                            positions[yours] = (row, col)
                            send_move(from_rc, (row, col), yours) # type: ignore
                            last_move = (yours, (row, col), pygame.time.get_ticks()) #type: ignore
                            turn = "black" if yours == "white" else "white"
                            check_and_set_victory(trigger_color=yours, announce=True) # type: ignore
                    dragging = False
                    drag_color = None

        screen.fill(BG)

        cur_w, _cur_h = screen.get_size()
        if name_value:
            label = str(name_value)
            if your_color:
                label += f" ({your_color})"
            label += f"  •  Turn: {turn.title()}"
            name_surf = BIG.render(label, True, TEXT)
            label_y = max(5, top - 40)
            screen.blit(name_surf, (cur_w // 2 - name_surf.get_width() // 2, label_y))
        # Bottom-left anchored scoreboard & walls info
        # Show names instead of colors in the score HUD
        if your_color in ("white", "black"):
            if your_color == "white":
                white_name, black_name = my_name, opp_name
            else:
                white_name, black_name = opp_name, my_name
        else:
            white_name, black_name = "White", "Black"
        score_text = f"{white_name} {white_score} - {black_score} {black_name}"
        walls_text = f"Walls W:{walls_remaining['white']} B:{walls_remaining['black']}  (W=wall, Shift=vertical)"
        score_surf = FONT.render(score_text, True, LABEL)
        walls_surf = FONT.render(walls_text, True, LABEL)
        bl_margin = 18
        cur_w, cur_h = screen.get_size()
        walls_y = cur_h - bl_margin - walls_surf.get_height()
        score_y = walls_y - 4 - score_surf.get_height()
        hud_x = bl_margin
        bg_w = max(score_surf.get_width(), walls_surf.get_width()) + 14
        bg_h = (walls_y + walls_surf.get_height()) - score_y + 10
        backdrop = pygame.Surface((bg_w, bg_h), pygame.SRCALPHA)
        backdrop.fill((255, 255, 255, 170))
        screen.blit(backdrop, (hud_x - 7, score_y - 5))
        screen.blit(score_surf, (hud_x, score_y))
        screen.blit(walls_surf, (hud_x, walls_y))

        # Draw the board
        for r in range(squares):
            for c in range(squares):
                color = WHITE if (r + c) % 2 == 0 else GREEN
                rect = pygame.Rect(left + c * sq, top + r * sq, sq, sq)
                pygame.draw.rect(screen, color, rect)

        # Draw placed walls
        wall_color = (90, 60, 25)
        for (wr, wc) in horizontal_walls:
            dr1, dc1 = anchor_to_display_rc(wr, wc)
            x = left + dc1 * sq
            # Horizontal wall lies between rows r and r+1 -> y at (r+1)*sq
            y = top + (dr1 + 1) * sq - 4
            pygame.draw.rect(screen, wall_color, pygame.Rect(x, y, sq * 2, 8), border_radius=2)
        for (wr, wc) in vertical_walls:
            dr1, dc1 = anchor_to_display_rc(wr, wc)
            # Vertical wall lies between cols c and c+1 -> x at (c+1)*sq
            x = left + (dc1 + 1) * sq - 4
            y = top + dr1 * sq
            pygame.draw.rect(screen, wall_color, pygame.Rect(x, y, 8, sq * 2), border_radius=2)

        # Wall preview
        if placing_wall and wall_preview is not None:
            o, wr, wc = wall_preview
            preview_color = (200, 140, 60)
            dr1, dc1 = anchor_to_display_rc(wr, wc)
            if o == 'h':
                x = left + dc1 * sq
                y = top + (dr1 + 1) * sq - 4
                pygame.draw.rect(screen, preview_color, pygame.Rect(x, y, sq * 2, 8), border_radius=2)
            else:
                x = left + (dc1 + 1) * sq - 4
                y = top + dr1 * sq
                pygame.draw.rect(screen, preview_color, pygame.Rect(x, y, 8, sq * 2), border_radius=2)

        # If dragging, show legal moves for selected piece
        if dragging and drag_color:
            from_r, from_c = positions[drag_color]
            for rr, cc in legal_moves(from_r, from_c):
                d_rr, d_cc = to_display_rc(rr, cc)
                hrect = pygame.Rect(left + d_cc * sq, top + d_rr * sq, sq, sq)
                pygame.draw.rect(screen, (255, 215, 0), hrect, width=4, border_radius=4)

        # Draw pieces, with dragged piece following cursor
        def draw_piece(img: Optional[pygame.Surface], pos_rc: Tuple[int, int], fallback_color: Tuple[int, int, int]):
            if img:
                r, c = pos_rc
                d_r, d_c = to_display_rc(r, c)
                rect = pygame.Rect(left + d_c * sq, top + d_r * sq, sq, sq)
                ir = img.get_rect()
                ir.center = rect.center
                screen.blit(img, (ir.x, ir.y))
            else:
                r, c = pos_rc
                d_r, d_c = to_display_rc(r, c)
                rect = pygame.Rect(left + d_c * sq, top + d_r * sq, sq, sq)
                pygame.draw.circle(screen, fallback_color, rect.center, sq // 3)

        # Last move highlight (2 seconds)
        now_ms = pygame.time.get_ticks()
        if last_move is not None:
            mv_color, mv_to, ts = last_move # type: ignore
            if now_ms - ts <= 2000:
                lr, lc = mv_to
                d_r, d_c = to_display_rc(lr, lc)
                hl = pygame.Rect(left + d_c * sq + 4, top + d_r * sq + 4, sq - 8, sq - 8)
                pygame.draw.rect(screen, (255, 215, 0), hl, width=3, border_radius=6)
            else:
                last_move = None

        # Non-dragged piece first
        if not (dragging and drag_color == "white"):
            draw_piece(white_img, positions["white"], (230, 230, 230))
        if not (dragging and drag_color == "black"):
            draw_piece(black_img, positions["black"], (20, 20, 20))

        # Draw dragged piece on top following cursor
        if dragging and drag_color:
            img = white_img if drag_color == "white" else black_img
            if img:
                mx, my = drag_pos_px
                ir = img.get_rect()
                ir.center = (mx - drag_offset[0], my - drag_offset[1])
                screen.blit(img, (ir.x, ir.y))
            else:
                pygame.draw.circle(screen, (255, 0, 0), (drag_pos_px[0], drag_pos_px[1]), sq // 3)


        if game_over:
            if winner_color in ("white", "black") and your_color in ("white", "black"): # type: ignore
                if winner_color == your_color:
                    turn_msg = "You win!"
                else:
                    turn_msg = "You lost!"
            else:
                if winner_name:
                    turn_msg = f"{winner_name} wins!"
                elif winner_color:
                    turn_msg = f"{winner_color.title()} wins!"
                else:
                    turn_msg = "Game over"
        else:
            if your_color:
                turn_msg = "Your move" if turn == your_color else "Opponent's move"
            else:
                # local/offline: show whose move
                turn_msg = f"{turn.title()}'s move"
        cur_w, cur_h = screen.get_size()
        turn_surf = FONT.render(turn_msg, True, LABEL)

        if wall_error_msg and (now_ms - wall_error_ts) <= 2000:
            err_surf = BIG.render(wall_error_msg, True, (200, 60, 60))
            screen.blit(err_surf, (cur_w // 2 - err_surf.get_width() // 2, base_y - err_surf.get_height() - 6))

        if opponent_left.is_set():
            second_surf = BIG.render("Opponent disconnected. Press ESC.", True, (200, 60, 60))
        elif game_over:
            if rematch_local_request and rematch_remote_request:
                second_line = "Restarting"
            elif rematch_local_request:
                second_line = "Waiting for opponent..."
            elif rematch_remote_request:
                second_line = "Opponent wants rematch"
            else:
                second_line = "Press ESC or click Rematch"
            second_surf = FONT.render(second_line, True, LABEL)
        else:
            second_surf = title_text  # reuse existing surface (Press ESC to return)

        spacing = 4
        base_y = top + board_size + 10
        needed = turn_surf.get_height() + spacing + second_surf.get_height()
        bottom_limit = cur_h - 5

        if base_y + needed <= bottom_limit:
            turn_y = base_y
            second_y = turn_y + turn_surf.get_height() + spacing
        else:
            # Try anchoring at bottom
            second_y = bottom_limit - second_surf.get_height()
            turn_y = second_y - spacing - turn_surf.get_height()
            if turn_y < base_y:
                # Not enough space: shift both up as a block but keep order
                turn_y = max(5, bottom_limit - needed)
                second_y = turn_y + turn_surf.get_height() + spacing

        screen.blit(turn_surf, (cur_w // 2 - turn_surf.get_width() // 2, turn_y))
        screen.blit(second_surf, (cur_w // 2 - second_surf.get_width() // 2, second_y))

        # Rematch button (top-right) - always visible unless opponent left
        btn_w, btn_h = 140, 40
        btn_margin = 10
        rematch_rect = pygame.Rect(cur_w - btn_w - btn_margin, btn_margin, btn_w, btn_h)
        if opponent_left.is_set():
            rematch_label = "(N/A)"
            btn_color = (160, 160, 160)
        else:
            if rematch_local_request and rematch_remote_request:
                rematch_label = "Restarting"
                btn_color = (90, 170, 90)
            elif rematch_local_request:
                rematch_label = "Waiting..."
                btn_color = (180, 150, 70)
            elif rematch_remote_request:
                rematch_label = "Accept"
                btn_color = (70, 130, 200)
            else:
                rematch_label = "Rematch"
                btn_color = (70, 130, 180)
        pygame.draw.rect(screen, btn_color, rematch_rect, border_radius=8)
        pygame.draw.rect(screen, (40, 40, 40), rematch_rect, width=2, border_radius=8)
        r_txt = FONT.render(rematch_label, True, (255, 255, 255))
        screen.blit(r_txt, (rematch_rect.centerx - r_txt.get_width() // 2, rematch_rect.centery - r_txt.get_height() // 2))

        # Helper text / opponent status

        pygame.display.flip()
        clock.tick(60)

    # Cleanup listener/socket if provided
    if sock is not None:
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        try:
            sock.close()
        except Exception:
            pass


def matchmaking_screen(player_name: str):
    # Update caption for matchmaking
    pygame.display.set_caption(f"Matchmaking - {player_name}")
    # UI elements
    title = BIG.render("Find Opponent", True, TEXT)
    info = FONT.render("Choose your color preference", True, LABEL)

    color_options = ["white", "black", "any"]
    color_idx = 2  # default 'any'

    # Buttons
    color_btn = pygame.Rect(0, 0, 180, 44)
    color_btn.centerx = WIDTH // 2
    color_btn.top = 140

    find_btn = pygame.Rect(0, 0, 200, 48)
    find_btn.centerx = WIDTH // 2
    find_btn.top = color_btn.bottom + 16

    cancel_btn = pygame.Rect(0, 0, 140, 40)
    cancel_btn.centerx = WIDTH // 2
    cancel_btn.top = find_btn.bottom + 12

    status_msg = ""
    in_progress = False
    result_lock = threading.Lock()
    result: Optional[Dict[str, Any]] = None
    err: Optional[str] = None
    sock_ref: List[Optional[socket.socket]] = [None]

    def worker(name: str, pref: str):
        nonlocal result, err
        try:
            s = socket.create_connection((server_host, server_port), timeout=5.0)
            sock_ref[0] = s
            line = json.dumps({"type": "join", "name": name, "pref": pref}).encode("utf-8") + b"\n"
            s.sendall(line)
            s.settimeout(20.0)  # wait up to 20s for match
            buff = b""
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                buff += chunk
                if b"\n" in buff:
                    one, _, _rest = buff.partition(b"\n")
                    try:
                        data = json.loads(one.decode("utf-8"))
                    except Exception:
                        err = "Invalid server response"
                        break
                    with result_lock:
                        result = data
                    break
        except Exception as e:
            err = str(e)
        finally:
            # Keep socket open for the board session; don't clear here
            pass

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                # back to entry screen
                return
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if color_btn.collidepoint(event.pos) and not in_progress:
                    color_idx = (color_idx + 1) % len(color_options)
                elif find_btn.collidepoint(event.pos) and not in_progress:
                    # start matchmaking
                    status_msg = "Connecting to server..."
                    in_progress = True
                    t = threading.Thread(target=worker, args=(player_name, color_options[color_idx]), daemon=True)
                    t.start()
                elif cancel_btn.collidepoint(event.pos):
                    # cancel search
                    if in_progress:
                        status_msg = "Cancelled."
                        in_progress = False
                        if sock_ref[0]:
                            try:
                                sock_ref[0].shutdown(socket.SHUT_RDWR)
                                sock_ref[0].close()
                            except Exception:
                                pass
                            finally:
                                sock_ref[0] = None
                    else:
                        return

        # Poll result
        with result_lock:
            if result is not None:
                data = result
                result = None
                in_progress = False
                if data is not None and data.get("type") == "start":
                    your = str(data.get("you") or "")
                    opponent = str(data.get("opponent") or "Opponent")
                    # go to board and show opponent in the label; pass session socket
                    draw_board(f"{player_name} vs {opponent}", your_color=your, sock=sock_ref[0])
                    # after returning from board, go back to entry
                    # ensure socket is cleared after board returns
                    sock_ref[0] = None
                    return
                else:
                    status_msg = "Matchmaking failed."

        if in_progress and not status_msg.startswith("Waiting"):
            status_msg = "Waiting for opponent..."

        # Draw UI
        screen.fill(BG)
        screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 40))
        screen.blit(info, (WIDTH // 2 - info.get_width() // 2, 90))

        # Color button
        pygame.draw.rect(screen, INPUT_BG, color_btn, border_radius=6)
        pygame.draw.rect(screen, BORDER_INACTIVE, color_btn, width=2, border_radius=6)
        col_text = FONT.render(f"Color: {color_options[color_idx].title()}", True, TEXT)
        screen.blit(col_text, (color_btn.centerx - col_text.get_width() // 2, color_btn.centery - col_text.get_height() // 2))

        # Find button
        pygame.draw.rect(screen, (46, 160, 67) if not in_progress else (140, 180, 150), find_btn, border_radius=6)
        find_text = FONT.render("Find Opponent", True, BUTTON_TEXT)
        screen.blit(find_text, (find_btn.centerx - find_text.get_width() // 2, find_btn.centery - find_text.get_height() // 2))

        # Cancel/back button
        pygame.draw.rect(screen, (200, 80, 80), cancel_btn, border_radius=6)
        cancel_text = FONT.render("Cancel" if in_progress else "Back", True, BUTTON_TEXT)
        screen.blit(cancel_text, (cancel_btn.centerx - cancel_text.get_width() // 2, cancel_btn.centery - cancel_text.get_height() // 2))

        # Status
        if status_msg:
            st = FONT.render(status_msg, True, LABEL)
            screen.blit(st, (WIDTH // 2 - st.get_width() // 2, cancel_btn.bottom + 16))

        pygame.display.flip()
        clock.tick(60)

while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        if event.type == pygame.VIDEORESIZE:
            WIDTH, HEIGHT = event.w, event.h # type: ignore
            screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
            # Recenter UI elements
            label_pos[0] = WIDTH // 2 - label_surf.get_width() // 2
            input_rect.centerx = WIDTH // 2
            input_rect.top = label_pos[1] + label_surf.get_height() + 12
            button_rect.centerx = WIDTH // 2
            button_rect.top = server_input_rect.bottom + 16

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if input_rect.collidepoint(event.pos):
                active_field = 'name'
            elif server_input_rect.collidepoint(event.pos):
                active_field = 'server'
            else:
                active_field = None

            if button_rect.collidepoint(event.pos):
                h, p = _parse_server_endpoint(server_text)
                server_host, server_port = h, p
                matchmaking_screen(text)

        if event.type == pygame.KEYDOWN:
            if active_field == 'name':
                if event.key == pygame.K_RETURN:
                    h, p = _parse_server_endpoint(server_text)
                    server_host, server_port = h, p
                    matchmaking_screen(text)
                elif event.key == pygame.K_BACKSPACE:
                    text = text[:-1]
                else:
                    if event.unicode.isprintable():
                        text += event.unicode
            elif active_field == 'server':
                if event.key == pygame.K_RETURN:
                    h, p = _parse_server_endpoint(server_text)
                    server_host, server_port = h, p
                    matchmaking_screen(text)
                elif event.key == pygame.K_BACKSPACE:
                    server_text = server_text[:-1]
                else:
                    if event.unicode.isprintable():
                        server_text += event.unicode

    screen.fill(BG)

    # Keep window caption in sync with entered name on the entry screen
    if text:
        pygame.display.set_caption(f"Name Entry - {text}")
    else:
        pygame.display.set_caption("Name Entry")

    # Labels
    screen.blit(label_surf, tuple(label_pos))
    srv_label_pos = (WIDTH // 2 - server_label_surf.get_width() // 2, input_rect.bottom + 6)
    screen.blit(server_label_surf, srv_label_pos)

    # Input boxes
    # Username
    pygame.draw.rect(screen, INPUT_BG, input_rect, border_radius=6)
    pygame.draw.rect(screen, BORDER_ACTIVE if active_field == 'name' else BORDER_INACTIVE, input_rect, width=2, border_radius=6)
    txt_surf = BIG.render(text, True, TEXT)
    clip = txt_surf.get_rect(); clip.width = input_rect.width - 12
    screen.set_clip(input_rect.inflate(-12, -8))
    screen.blit(txt_surf, (input_rect.x + 8, input_rect.y + 6))
    screen.set_clip(None)

    # Server
    pygame.draw.rect(screen, INPUT_BG, server_input_rect, border_radius=6)
    pygame.draw.rect(screen, BORDER_ACTIVE if active_field == 'server' else BORDER_INACTIVE, server_input_rect, width=2, border_radius=6)
    display_srv = server_text or f"{server_host}:{server_port}"
    srv_txt = BIG.render(display_srv, True, TEXT)
    clip2 = srv_txt.get_rect(); clip2.width = server_input_rect.width - 12
    screen.set_clip(server_input_rect.inflate(-12, -8))
    screen.blit(srv_txt, (server_input_rect.x + 8, server_input_rect.y + 6))
    screen.set_clip(None)

    # Server address can be edited in the input above; defaults via env/CLI or 127.0.0.1:5000

    # Submit button
    pygame.draw.rect(screen, BUTTON_BG, button_rect, border_radius=6)
    btn_text = FONT.render("Submit", True, BUTTON_TEXT)
    screen.blit(
        btn_text,
        (button_rect.centerx - btn_text.get_width() // 2,
         button_rect.centery - btn_text.get_height() // 2))
    pygame.display.flip()
    clock.tick(60)  