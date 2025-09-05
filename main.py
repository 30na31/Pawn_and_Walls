import pygame
import os
import sys
import socket
import threading
import json
from typing import Optional, List, Dict, Any, Tuple, cast

pygame.init()
WIDTH, HEIGHT = 800, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
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

label_pos = (WIDTH // 2 - label_surf.get_width() // 2, 24)

input_rect = pygame.Rect(0, 0, input_w, input_h)
input_rect.centerx = WIDTH // 2
input_rect.top = label_pos[1] + label_surf.get_height() + 12

button_rect = pygame.Rect(0, 0, button_w, button_h)
button_rect.centerx = WIDTH // 2
button_rect.top = input_rect.bottom + 12

active = False
text = ""

clock = pygame.time.Clock()

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 5000

def draw_board(name_value: str, your_color: Optional[str] = None, sock: Optional[socket.socket] = None) -> None:
    # Draw a 9x9 chessboard (green/white) centered on the screen
    # Update window caption for board
    caption_label = name_value
    if your_color:
        caption_label += f" ({your_color})"
    pygame.display.set_caption(caption_label)
    squares = 9
    margin = 40  # visual padding around the board
    board_size = min(WIDTH, HEIGHT) - margin * 2
    sq = board_size // squares
    # Recompute board size to be a multiple of square size, then center
    board_size = sq * squares
    left = (WIDTH - board_size) // 2
    top = (HEIGHT - board_size) // 2

    GREEN = (118, 150, 86)
    WHITE = (255, 255, 255)

    # Small title text (optional)
    title_text = FONT.render("Press ESC to return", True, LABEL)

    # Load piece images once (scaled to square size)
    base_dir = os.path.dirname(__file__)
    white_pawn_path = os.path.join(base_dir, "white pawn.png")
    black_pawn_path = os.path.join(base_dir, "black pawn.png")

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

    # Drag state
    dragging = False
    drag_color: Optional[str] = None
    drag_offset = (0, 0)
    drag_pos_px = (0, 0)

    # Networking: listener for opponent moves
    state_lock = threading.Lock()
    pending_moves: List[Dict[str, Any]] = []

    def legal_moves(r: int, c: int) -> List[Tuple[int, int]]:
        candidates = [(r-1, c), (r+1, c), (r, c-1), (r, c+1)]
        in_bounds = [(rr, cc) for rr, cc in candidates if 0 <= rr < squares and 0 <= cc < squares]
        # cannot move into occupied square
        occ = {positions["white"], positions["black"]}
        return [(rr, cc) for rr, cc in in_bounds if (rr, cc) not in occ]

    def send_move(from_rc: Tuple[int, int], to_rc: Tuple[int, int], color: str) -> None:
        if not sock:
            return
        try:
            msg = json.dumps({"type": "move", "from": list(from_rc), "to": list(to_rc), "color": color}).encode("utf-8") + b"\n"
            sock.sendall(msg)
        except Exception:
            pass

    def listen_loop():
        if not sock:
            return
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
                        elif p_type == "end":
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
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running_board = False
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                # Determine clicked square
                col = (mx - left) // sq
                row = (my - top) // sq
                if 0 <= row < squares and 0 <= col < squares:
                    # Check if clicking your piece (if color known), else allow white by default
                    yours = your_color or "white"
                    pr, pc = positions[yours]
                    if row == pr and col == pc:
                        dragging = True
                        drag_color = yours
                        # drag offset to keep image centered under cursor
                        drag_offset = (mx - (left + pc * sq + sq // 2), my - (top + pr * sq + sq // 2))
                        drag_pos_px = (mx, my)
            if event.type == pygame.MOUSEMOTION and dragging:
                drag_pos_px = event.pos
            if event.type == pygame.MOUSEBUTTONUP and event.button == 1 and dragging:
                mx, my = event.pos
                col = (mx - left) // sq
                row = (my - top) // sq
                yours = drag_color or (your_color or "white")
                from_rc = positions[yours]
                lm = legal_moves(*from_rc)
                if 0 <= row < squares and 0 <= col < squares and (row, col) in lm:
                    positions[yours] = (row, col)
                    send_move(from_rc, (row, col), yours)
                # end drag in any case
                dragging = False
                drag_color = None

        screen.fill(BG)

        # Apply any pending opponent moves
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
                        except Exception:
                            pass

        # Optional: show the entered name at the top if provided
        if name_value:
            label = str(name_value)
            if your_color:
                label += f" ({your_color})"
            name_surf = BIG.render(label, True, TEXT)
            screen.blit(name_surf, (WIDTH // 2 - name_surf.get_width() // 2, top - 30))

        # Draw the board
        for r in range(squares):
            for c in range(squares):
                color = WHITE if (r + c) % 2 == 0 else GREEN
                rect = pygame.Rect(left + c * sq, top + r * sq, sq, sq)
                pygame.draw.rect(screen, color, rect)

        # If dragging, show legal moves for selected piece
        if dragging and drag_color:
            from_r, from_c = positions[drag_color]
            for rr, cc in legal_moves(from_r, from_c):
                hrect = pygame.Rect(left + cc * sq, top + rr * sq, sq, sq)
                pygame.draw.rect(screen, (255, 215, 0), hrect, width=4, border_radius=4)

        # Draw pieces, with dragged piece following cursor
        def draw_piece(img: Optional[pygame.Surface], pos_rc: Tuple[int, int], fallback_color: Tuple[int, int, int]):
            if img:
                r, c = pos_rc
                rect = pygame.Rect(left + c * sq, top + r * sq, sq, sq)
                ir = img.get_rect()
                ir.center = rect.center
                screen.blit(img, (ir.x, ir.y))
            else:
                r, c = pos_rc
                rect = pygame.Rect(left + c * sq, top + r * sq, sq, sq)
                pygame.draw.circle(screen, fallback_color, rect.center, sq // 3)

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

        # Helper text
        screen.blit(title_text, (WIDTH // 2 - title_text.get_width() // 2, top + board_size + 10))

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
            s = socket.create_connection((SERVER_HOST, SERVER_PORT), timeout=5.0)
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

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if input_rect.collidepoint(event.pos):
                active = True
            else:
                active = False

            if button_rect.collidepoint(event.pos):
                matchmaking_screen(text)

        if event.type == pygame.KEYDOWN and active:
            if event.key == pygame.K_RETURN:
                matchmaking_screen(text)
            elif event.key == pygame.K_BACKSPACE:
                text = text[:-1]
            else:
                # Append printable character
                if event.unicode.isprintable():
                    text += event.unicode

    screen.fill(BG)

    # Keep window caption in sync with entered name on the entry screen
    if text:
        pygame.display.set_caption(f"Name Entry - {text}")
    else:
        pygame.display.set_caption("Name Entry")

    # Label
    screen.blit(label_surf, label_pos)

    # Input box
    pygame.draw.rect(screen, INPUT_BG, input_rect, border_radius=6)
    pygame.draw.rect(
        screen,
        BORDER_ACTIVE if active else BORDER_INACTIVE,
        input_rect,
        width=2,
        border_radius=6
    )
    txt_surf = BIG.render(text, True, TEXT)
    # Keep text inside the box
    clip = txt_surf.get_rect()
    clip.width = input_rect.width - 12
    screen.set_clip(input_rect.inflate(-12, -8))
    screen.blit(txt_surf, (input_rect.x + 8, input_rect.y + 6))
    screen.set_clip(None)

    # Submit button
    pygame.draw.rect(screen, BUTTON_BG, button_rect, border_radius=6)
    btn_text = FONT.render("Submit", True, BUTTON_TEXT)
    screen.blit(
        btn_text,
        (button_rect.centerx - btn_text.get_width() // 2,
         button_rect.centery - btn_text.get_height() // 2))
    pygame.display.flip()
    clock.tick(60)  