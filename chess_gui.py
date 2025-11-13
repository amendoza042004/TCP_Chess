import pygame
import socket
import json
import threading
import sys
import os


WIDTH = 640
HEIGHT = 640
SQ = WIDTH // 8

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 5002

UNICODE_PIECES = {
    "wK": "♔", "wQ": "♕", "wR": "♖", "wB": "♗", "wN": "♘", "wP": "♙",
    "bK": "♚", "bQ": "♛", "bR": "♜", "bB": "♝", "bN": "♞", "bP": "♟"
}

#NETWORK CLIENT
class ServerConnection:
    def __init__(self, name, on_message):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((SERVER_HOST, SERVER_PORT))
        self.file = self.sock.makefile("r")
        self.on_message = on_message

        # send hello
        self.send({"type": "hello", "name": name})

        threading.Thread(target=self.listen, daemon=True).start()

    def send(self, obj):
        raw = json.dumps(obj) + "\n"
        self.sock.sendall(raw.encode())

    def listen(self):
        for line in self.file:
            try:
                data = json.loads(line.strip())
                self.on_message(data)
            except:
                continue

#GUI
class ChessGUI:
    def __init__(self, name):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH + 200, HEIGHT + 100))
        pygame.display.set_caption("Chess - GUI Client")

        try:
            font_path = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
            self.font = pygame.font.Font(font_path, 40)
        except:
            print("WARNING: Unicode font not found — using default.")
            self.font = pygame.font.SysFont("Arial", 40)

        self.infotext = pygame.font.SysFont("Arial", 24)

        # Quit button rectangle
        self.quit_rect = pygame.Rect(WIDTH + 30, HEIGHT + 40, 150, 40)


        # Game state
        self.fen = None
        self.turn = "white"
        self.color = None
        self.opponent = None

        self.history = []      # move list

        self.illegal_message = ""
        self.illegal_timer = 0  


        # Drag state
        self.dragging = False
        self.drag_piece = None
        self.drag_from = None
        self.mouse_x = 0
        self.mouse_y = 0

        # Connect to server
        self.server = ServerConnection(name, self.handle_message)

    #SERVER MESSAGE HANDLER
    def handle_message(self, data):
        print("SERVER:", data)
        t = data.get("type")

        if t == "start":
            self.color = data["color"]
            self.opponent = data["opponent"]

        elif t == "state":
            self.fen = data["fen"]
            self.turn = data["turn"]

        elif t == "move_ok":
            uci = data["uci"]
            mover = data["by"]     # "white" or "black"
            self.history.append((uci, mover))

        elif t == "illegal":
            reason = data.get("reason", "Illegal move")
            print("ILLEGAL:", reason)
            self.illegal_message = reason
            self.illegal_timer = 120   # show for 2 seconds


        elif t == "opponent_left":
            print("Opponent left — you win by forfeit")

        elif t == "result":
            print("GAME OVER:", data)

    #FEN PARSER
    def parse_fen(self, fen):
        board = []
        rows = fen.split()[0].split("/")
        for row in rows:
            line = []
            for ch in row:
                if ch.isdigit():
                    line += [None] * int(ch)
                else:
                    color = "w" if ch.isupper() else "b"
                    piece = ch.upper()  # P,R,N,B,Q,K
                    line.append(color + piece)
            board.append(line)
        return board

    #DRAW PIECES
    def draw_piece(self, code, r, c):
        piece_chr = UNICODE_PIECES[code]

        border = (0, 0, 0)
        fill = (255, 255, 255) if code[0] == "w" else (0, 0, 0)
        text_color = (0, 0, 0) if code[0] == "w" else (255, 255, 255)

        center = (c * SQ + SQ // 2, r * SQ + SQ // 2)
        radius = SQ // 2 - 6

        # background circle
        pygame.draw.circle(self.screen, border, center, radius)
        pygame.draw.circle(self.screen, fill, center, radius - 3)

        # piece symbol
        text = self.font.render(piece_chr, True, text_color)
        rect = text.get_rect(center=center)
        self.screen.blit(text, rect)

    #DRAW BOARD + PIECES
    def draw_board(self):
        light = (240, 217, 181)
        dark = (181, 136, 99)

        for r in range(8):
            for c in range(8):
                color = light if (r + c) % 2 == 0 else dark
                pygame.draw.rect(self.screen, color, (c*SQ, r*SQ, SQ, SQ))

        if not self.fen:
            return

        board = self.parse_fen(self.fen)

        for r in range(8):
            for c in range(8):
                piece = board[r][c]
                if piece and not (self.dragging and self.drag_from == (r, c)):
                    self.draw_piece(piece, r, c)

        if self.dragging and self.drag_piece:
            piece = self.drag_piece
            piece_chr = UNICODE_PIECES[piece]
            border = (0, 0, 0)
            fill = (255, 255, 255) if piece[0] == "w" else (0, 0, 0)
            text_color = (0, 0, 0) if piece[0] == "w" else (255, 255, 255)

            center = (self.mouse_x, self.mouse_y)
            radius = SQ // 2 - 6

            pygame.draw.circle(self.screen, border, center, radius)
            pygame.draw.circle(self.screen, fill, center, radius - 3)

            text = self.font.render(piece_chr, True, text_color)
            rect = text.get_rect(center=center)
            self.screen.blit(text, rect)

    #INPUT HANDLING
    def square_name(self, r, c):
        return "abcdefgh"[c] + "87654321"[r]

    def handle_click(self, pos):
        if not self.fen:
            return

        x, y = pos
        # Ignore clicks below 8x8 board
        if y >= HEIGHT:
            return

        r = y // SQ
        c = x // SQ

        board = self.parse_fen(self.fen)

        # Safety
        if r < 0 or r > 7 or c < 0 or c > 7:
            return

        piece = board[r][c]
        if not piece:
            return

        # only allow dragging your own color
        if self.color is None or piece[0] != self.color[0]:
            return

        self.dragging = True
        self.drag_piece = piece
        self.drag_from = (r, c)

    def handle_drop(self, pos):
        if not self.dragging or not self.fen:
            return

        x, y = pos

        if x < 0 or x >= WIDTH or y < 0 or y >= HEIGHT:
            self.dragging = False
            self.drag_piece = None
            return

        to_r = y // SQ
        to_c = x // SQ

        from_r, from_c = self.drag_from

        move = self.square_name(from_r, from_c) + self.square_name(to_r, to_c)
        print("SEND MOVE:", move)

        self.server.send({"type": "move", "uci": move})

        self.dragging = False
        self.drag_piece = None


    #MAIN LOOP
    def run(self):
        clock = pygame.time.Clock()

        while True:
            self.mouse_x, self.mouse_y = pygame.mouse.get_pos()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

                if event.type == pygame.MOUSEBUTTONDOWN:
                    if self.quit_rect.collidepoint(event.pos):
                        print("Quitting game...")
                        
                        try:
                            self.server.send({"type": "quit"})
                        except:
                            pass
                        
                        pygame.quit()
                        sys.exit()

                    self.handle_click(event.pos)


                if event.type == pygame.MOUSEBUTTONUP:
                    self.handle_drop(event.pos)

            self.screen.fill((0, 0, 0))
            self.draw_board()

            #Illegal move overlay
            if self.illegal_timer > 0:
                self.illegal_timer -= 1

                pygame.draw.rect(
                    self.screen,
                    (255, 0, 0, 180),         
                    (WIDTH//2 - 150, HEIGHT//2 - 40, 300, 80)
                )

                msg = self.infotext.render(self.illegal_message, True, (255, 255, 255))
                rect = msg.get_rect(center=(WIDTH//2, HEIGHT//2))
                self.screen.blit(msg, rect)

            # Move history sidebar
            pygame.draw.rect(self.screen, (50, 50, 50), (WIDTH, 0, 200, HEIGHT))
            title = self.infotext.render("Moves:", True, (255, 255, 255))
            self.screen.blit(title, (WIDTH + 20, 10))

            y_off = 40
            for (uci, mover) in self.history[-30:]:
                color_tag = "(W)" if mover == "white" else "(B)"

                # highlight your moves
                if mover == self.color:
                    txt_color = (0, 255, 0)   
                else:
                    txt_color = (255, 255, 255) 

                lbl = self.infotext.render(f"{color_tag} {uci}", True, txt_color)
                self.screen.blit(lbl, (WIDTH + 20, y_off))
                y_off += 22


            # Info bar
            color_text = self.color.capitalize() if self.color else "?"
            turn_text = self.turn.capitalize() if self.turn else "?"

            info = f"Color: {color_text}   Opponent: {self.opponent}   Turn: {turn_text}"
            label = self.infotext.render(info, True, (255, 255, 255))
            self.screen.blit(label, (10, HEIGHT + 20))

            # Quit button 
            pygame.draw.rect(
                self.screen,
                (120, 120, 120),  
                self.quit_rect,
                border_radius=10  
            )

            quit_label = self.infotext.render("Quit Game", True, (255, 255, 255))
            label_rect = quit_label.get_rect(center=self.quit_rect.center)
            self.screen.blit(quit_label, label_rect)

            pygame.display.flip()
            clock.tick(60)


#START CLIENT
if __name__ == "__main__":
    name = input("Enter your name: ")
    gui = ChessGUI(name)
    gui.run()
