import socket
import threading
import json
import traceback
import time
from typing import Optional, List, Dict
import chess_logic

HOST = "0.0.0.0"
PORT = 5002 # change if desired

# --- Utilities: JSON send/recv line-based ---
def send_line(conn, obj):
    try:
        data = (json.dumps(obj) + "\n").encode("utf-8")
        conn.sendall(data)
    except Exception:
        # calling code will handle disconnect
        raise

def recv_line(fd) -> Optional[dict]:
    try:
        line = fd.readline()
        if not line:
            return None
        return json.loads(line.strip())
    except json.JSONDecodeError:
        return {"__bad_json__": True}
    except Exception:
        return None

# --- Client handler abstraction ---
class ClientHandler:
    def __init__(self, conn: socket.socket, addr):
        self.conn = conn
        self.addr = addr
        self.file = conn.makefile("r", encoding="utf-8", newline="\n")
        self.lock = threading.Lock()
        self.name: Optional[str] = None
        self.in_game = False
        self.game: Optional["Game"] = None
        self.color: Optional[str] = None  # 'white' or 'black'
        self.alive = True

    def send(self, obj: dict):
        with self.lock:
            try:
                send_line(self.conn, obj)
            except Exception:
                # on send error, mark dead; game will detect
                self.alive = False
                raise

    def close(self):
        try:
            self.file.close()
        except Exception:
            pass
        try:
            self.conn.close()
        except Exception:
            pass
        self.alive = False

# --- Global matchmaking structures ---
queue_lock = threading.Lock()
queue_cond = threading.Condition(queue_lock)
waiting_queue: List[ClientHandler] = []

# server logging
log_lock = threading.Lock()
def log(s: str):
    with log_lock:
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{ts}] {s}")

# --- Game logic / per-game thread ---
class Game:
    def __init__(self, white: ClientHandler, black: ClientHandler):
        self.white = white
        self.black = black
        self.board = chess_logic.Board()
        self.lock = threading.Lock()
        self.ended = False

        # link clients
        self.white.in_game = True
        self.black.in_game = True
        self.white.game = self
        self.black.game = self
        self.white.color = "white"
        self.black.color = "black"

    def start(self):
        log(f"Paired: {self.white.name} (white) vs {self.black.name} (black)")
        # notify start
        try:
            self.white.send({"type":"start","color":"white","opponent":self.black.name})
            self.black.send({"type":"start","color":"black","opponent":self.white.name})
            # send initial state
            self._send_state()
        except Exception:
            # connection issue during start: handle below
            pass

        # game thread doesn't need to actively loop; it responds to messages delivered by client handlers
        # but we still start a thread to monitor client aliveness and detect disconnects/timeouts
        t = threading.Thread(target=self.monitor_loop, daemon=True)
        t.start()

    def _send_state(self):
        obj = {"type":"state","fen":self.board.fen(),"turn":"white" if self.board.turn=='w' else "black","check": self._in_check(self.board.turn)}
        try:
            self.white.send(obj)
            self.black.send(obj)
        except Exception:
            # will be caught by monitor
            pass

    def _in_check(self, color_char):
        # color_char is 'w' or 'b'
        kp = self.board._king_pos(color_char)
        if kp is None:
            return False
        return self.board.is_square_attacked_by(kp[0], kp[1], self.board.enemy(color_char))

    def process_message(self, sender: ClientHandler, msg: dict):
        """
        Called by client handler thread when a JSON message is received from a client in-game.
        """
        with self.lock:
            if self.ended:
                return
            try:
                mtype = msg.get("type")
                if mtype == "move":
                    self._handle_move(sender, msg)
                elif mtype == "chat":
                    self._handle_chat(sender, msg)
                elif mtype == "resign":
                    self._handle_resign(sender)
                elif mtype == "quit":
                    self._handle_disconnect(sender)  # quit in-game -> forfeit
                else:
                    sender.send({"type":"illegal","reason":"unknown command"})
            except Exception as e:
                log(f"Error processing message from {sender.name}: {e}")
                traceback.print_exc()

    def _peer(self, client: ClientHandler) -> ClientHandler:
        return self.black if client is self.white else self.white

    def _handle_chat(self, sender: ClientHandler, msg: dict):
        text = str(msg.get("text",""))
        peer = self._peer(sender)
        try:
            peer.send({"type":"chat","from": sender.name, "text": text})
        except Exception:
            self._handle_disconnect(peer)

    def _handle_resign(self, sender: ClientHandler):
        if self.ended:
            return
        peer = self._peer(sender)
        winner_color = peer.color
        outcome = "resign"
        log(f"{sender.name} resigned; winner={peer.name}")
        try:
            sender.send({"type":"result","outcome":outcome,"winner":winner_color})
        except Exception:
            pass
        try:
            peer.send({"type":"result","outcome":outcome,"winner":winner_color})
        except Exception:
            pass
        self._end_game()

    def _handle_disconnect(self, disconnected_client: ClientHandler):
        if self.ended:
            return
        peer = self._peer(disconnected_client)
        log(f"{disconnected_client.name} disconnected (forfeit). Winner={peer.name}")
        try:
            peer.send({"type":"opponent_left"})
            # also send a result indicating winner
            peer.send({"type":"result","outcome":"forfeit","winner":peer.color})
        except Exception:
            pass
        self._end_game()

    def _handle_move(self, sender: ClientHandler, msg: dict):
        # validate format
        uci = msg.get("uci")
        if not isinstance(uci, str):
            sender.send({"type":"illegal","reason":"bad move format"})
            log(f"[{sender.name}] {uci} ✗ (bad move format)")
            return

        # check turn
        expected_color = "white" if self.board.turn == 'w' else "black"
        if sender.color != expected_color:
            sender.send({"type":"illegal","reason":"not your turn"})
            log(f"[{sender.name}] {uci} ✗ (not their turn)")
            return

        # try to build Move
        try:
            mv = chess_logic.Move(uci)
        except Exception:
            sender.send({"type":"illegal","reason":"bad uci"})
            log(f"[{sender.name}] {uci} ✗ (bad uci)")
            return

        # validate using board
        ok, reason = self.board.make_move(mv)
        if not ok:
            sender.send({"type":"illegal","reason":reason})
            log(f"[{sender.name}] {uci} ✗ ({reason})")
            return

        # SUCCESSFUL MOVE
        # sender successfully played the move
        log(f"[{sender.name}] {uci} ✓")

        # broadcast accepted move
        by_color = sender.color
        try:
            self.white.send({"type":"move_ok","uci": mv.uci, "by": by_color})
            self.black.send({"type":"move_ok","uci": mv.uci, "by": by_color})
        except Exception:
            pass

        # send updated state to both
        self._send_state()

        # check terminal conditions
        if self.board.result:
            if self.board.result == '1-0':
                winner = "white"
                outcome = "checkmate"
            elif self.board.result == '0-1':
                winner = "black"
                outcome = "checkmate"
            else:
                winner = None
                outcome = "stalemate"

            log(f"Result: {outcome}, winner={winner}")
            try:
                self.white.send({"type":"result","outcome": outcome, "winner": winner})
                self.black.send({"type":"result","outcome": outcome, "winner": winner})
            except Exception:
                pass

            self._end_game()

    def _end_game(self):
        self.ended = True
        for p in (self.white, self.black):
            try:
                p.in_game = False
                p.game = None
                p.color = None
            except Exception:
                pass

    def monitor_loop(self):
        # monitor connections; if either client dies, handle as disconnect/forfeit
        while not self.ended:
            if not self.white.alive:
                # white died, black wins
                self._handle_disconnect(self.white)
                break
            if not self.black.alive:
                self._handle_disconnect(self.black)
                break
            time.sleep(0.5)

# --- Matchmaking thread that pairs waiting clients ---
def matchmaking_thread():
    while True:
        with queue_cond:
            while len(waiting_queue) < 2:
                queue_cond.wait()
            # pop first two (FIFO)
            a = waiting_queue.pop(0)
            b = waiting_queue.pop(0)
        # start a game
        game = Game(a, b)
        try:
            game.start()
        except Exception:
            log("Failed to start game")
            traceback.print_exc()

# --- Per-client handler: receives messages, queueing, and forwarding to game if in one ---
def client_thread(conn: socket.socket, addr):
    client = ClientHandler(conn, addr)
    log(f"Client connected from {addr}")
    try:
        # expect a hello first
        client.send({"type":"welcome","ok":True})
        hello = recv_line(client.file)
        if not hello or not isinstance(hello, dict) or hello.get("type") != "hello":
            client.send({"type":"illegal","reason":"expected hello"})
            client.close()
            log(f"Client at {addr} failed to send hello; disconnected")
            return
        name = hello.get("name")
        if not isinstance(name, str) or not name.strip():
            client.send({"type":"illegal","reason":"bad name"})
            client.close()
            return
        client.name = name.strip()
        log(f"Client {client.name} connected from {addr}")
        # Enforce name uniqueness (simple check)
        # (we'll scan waiting_queue + active games)
        # naive uniqueness: if name currently in waiting_queue or in-game, append suffix
        original = client.name
        with queue_lock:
            taken = set()
            for c in waiting_queue:
                if c.name:
                    taken.add(c.name)
            # find active names via weak scan of threads - we won't exhaustively track; basic uniqueness
            i = 1
            while client.name in taken:
                i += 1
                client.name = f"{original}_{i}"

        # Put into waiting queue
        with queue_cond:
            waiting_queue.append(client)
            pos = len(waiting_queue)
            client.send({"type":"queued","pos": pos})
            queue_cond.notify_all()
        # Main loop: read lines and either handle pre-game chat/quit, or forward to game when in-game
        while client.alive:
            msg = recv_line(client.file)
            if msg is None:
                # disconnected
                client.alive = False
                break
            if isinstance(msg, dict) and msg.get("__bad_json__"):
                client.send({"type":"illegal","reason":"bad json"})
                continue
            # top-level commands allowed in lobby: chat (optional), quit
            mtype = msg.get("type")
            if not client.in_game:
                if mtype == "quit":
                    client.send({"type":"welcome","ok":False})
                    client.close()
                    break
                # allow chat in lobby (not required by spec; we'll ignore others)
                if mtype == "chat":
                    # echo to self as ack
                    client.send({"type":"chat","from":"server","text":"(lobby) message ignored; waiting for pairing"})
                    continue
                # other messages are enqueued only once paired; just ignore unknowns politely
                client.send({"type":"queued","pos": waiting_queue.index(client)+1 if client in waiting_queue else 0})
                continue
            else:
                # in a game: forward to game object
                if client.game:
                    client.game.process_message(client, msg)
                else:
                    # race: in_game True but no game yet
                    client.send({"type":"illegal","reason":"no game yet"})
    except Exception:
        log(f"Exception in client thread for {client.addr}")
        traceback.print_exc()
    finally:
        # cleanup: if client was in waiting queue remove
        with queue_cond:
            if client in waiting_queue:
                waiting_queue.remove(client)
        # if client was in a game, notify game
        if client.in_game and client.game:
            try:
                client.game._handle_disconnect(client)
            except Exception:
                pass
        client.close()
        log(f"Client {client.name or client.addr} disconnected")

# --- Server main ---
def main():
    # start matchmaking thread
    mt = threading.Thread(target=matchmaking_thread, daemon=True)
    mt.start()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen(50)
        log(f"Server listening on {HOST}:{PORT}")
        while True:
            try:
                conn, addr = s.accept()
                t = threading.Thread(target=client_thread, args=(conn, addr), daemon=True)
                t.start()
            except KeyboardInterrupt:
                log("Shutting down server (KeyboardInterrupt)")
                break
            except Exception:
                traceback.print_exc()

if __name__ == "__main__":
    main()
