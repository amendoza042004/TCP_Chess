# Minimal chess logic with legality checks:
# - Pieces: K Q R B N P
# - Colors: 'w' / 'b'
# - Coordinate moves: e2e4, e7e8Q
# - Supported: normal moves/captures, promotion (default Q), check/checkmate/stalemate
# - Not supported: castling, en passant, underpromotion (except Q), halfmove clock

from typing import List, Optional, Tuple

FILES = "abcdefgh"
RANKS = "12345678"


def in_bounds(r, c):
    return 0 <= r < 8 and 0 <= c < 8


def algebraic_to_rc(sq: str) -> Tuple[int, int]:
    file = FILES.index(sq[0])
    rank = RANKS.index(sq[1])
    # board[0] is rank 8; translate to 0-based rows top-down
    return 7 - rank, file


def rc_to_algebraic(r: int, c: int) -> str:
    return FILES[c] + RANKS[7 - r]


class Move:
    def __init__(self, uci: str):
        self.uci = uci.strip()
        if len(self.uci) not in (4, 5):
            raise ValueError("Bad UCI")
        self.src = self.uci[0:2]
        self.dst = self.uci[2:4]
        self.promo = self.uci[4].upper() if len(self.uci) == 5 else None
        if self.promo and self.promo not in ('Q', 'R', 'B', 'N'):
            raise ValueError("Unsupported promotion")


class Board:
    def __init__(self):
        # 8x8; each cell is None or like 'wP', 'bK'
        self.board: List[List[Optional[str]]] = [[None] * 8 for _ in range(8)]
        self.turn = 'w'
        self._place_start_position()
        self.result: Optional[str] = None   # '1-0','0-1','1/2-1/2'
        self.history: List[str] = []

    def _place_start_position(self):
        # place pawns
        for c in range(8):
            self.board[6][c] = 'wP'
            self.board[1][c] = 'bP'
        # place pieces
        back = ['R', 'N', 'B', 'Q', 'K', 'B', 'N', 'R']
        for c, p in enumerate(back):
            self.board[7][c] = 'w' + p
            self.board[0][c] = 'b' + p

    def copy(self):
        nb = Board.__new__(Board)
        nb.board = [row[:] for row in self.board]
        nb.turn = self.turn
        nb.result = self.result
        nb.history = self.history[:]
        return nb

    def piece_at(self, r, c):
        return self.board[r][c]

    def is_own(self, piece, color):
        return piece is not None and piece[0] == color

    def enemy(self, color):
        return 'b' if color == 'w' else 'w'

    def _ray(self, r, c, dr, dc):
        r += dr
        c += dc
        while in_bounds(r, c):
            yield r, c
            r += dr
            c += dc

    def _attacks_from(self, r, c) -> List[Tuple[int, int]]:
        piece = self.piece_at(r, c)
        if not piece:
            return []
        color, kind = piece[0], piece[1]
        direc = -1 if color == 'w' else 1
        attacks = []

        if kind == 'P':
            # pawn captures only
            for dc in (-1, 1):
                rr, cc = r + direc, c + dc
                if in_bounds(rr, cc):
                    attacks.append((rr, cc))

        elif kind == 'N':
            for dr, dc in [(2, 1), (2, -1), (-2, 1), (-2, -1),
                           (1, 2), (1, -2), (-1, 2), (-1, -2)]:
                rr, cc = r + dr, c + dc
                if in_bounds(rr, cc):
                    attacks.append((rr, cc))

        elif kind == 'B':
            for dr, dc in [(1, 1), (1, -1), (-1, 1), (-1, -1)]:
                for rr, cc in self._ray(r, c, dr, dc):
                    attacks.append((rr, cc))
                    if self.piece_at(rr, cc):
                        break

        elif kind == 'R':
            for dr, dc in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                for rr, cc in self._ray(r, c, dr, dc):
                    attacks.append((rr, cc))
                    if self.piece_at(rr, cc):
                        break

        elif kind == 'Q':
            for dr, dc in [(1, 0), (-1, 0), (0, 1), (0, -1),
                           (1, 1), (1, -1), (-1, 1), (-1, -1)]:
                for rr, cc in self._ray(r, c, dr, dc):
                    attacks.append((rr, cc))
                    if self.piece_at(rr, cc):
                        break

        elif kind == 'K':
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0:
                        continue
                    rr, cc = r + dr, c + dc
                    if in_bounds(rr, cc):
                        attacks.append((rr, cc))

        return attacks

    def is_square_attacked_by(self, r, c, color):
        # is (r,c) attacked by 'color'?
        for rr in range(8):
            for cc in range(8):
                p = self.piece_at(rr, cc)
                if not p or p[0] != color:
                    continue
                for ar, ac in self._attacks_from(rr, cc):
                    if ar == r and ac == c:
                        return True
        return False

    def _king_pos(self, color):
        for r in range(8):
            for c in range(8):
                if self.board[r][c] == color + 'K':
                    return (r, c)
        return None

    def _can_move_like(self, r, c, r2, c2) -> bool:
        piece = self.piece_at(r, c)
        target = self.piece_at(r2, c2)
        if not piece:
            return False
        color, kind = piece[0], piece[1]
        if self.is_own(target, color):
            return False

        dr, dc = r2 - r, c2 - c
        adr, adc = abs(dr), abs(dc)

        if kind == 'P':
            direc = -1 if color == 'w' else 1
            start_row = 6 if color == 'w' else 1

            # forward
            if dc == 0 and (
                (dr == direc and target is None) or
                (r == start_row and dr == 2 * direc and
                 target is None and self.piece_at(r + direc, c) is None)
            ):
                return True

            # capture FIX: require adc == 1
            if adr == 1 and adc == 1 and dr == direc and target is not None and target[0] != color:
                return True

            return False

        if kind == 'N':
            return (adr, adc) in [(1, 2), (2, 1)]

        if kind == 'K':
            return max(adr, adc) == 1  # no castling

        if kind == 'B':
            if adr != adc:
                return False
            step_r = 1 if dr > 0 else -1
            step_c = 1 if dc > 0 else -1
            rr, cc = r + step_r, c + step_c
            while (rr, cc) != (r2, c2):
                if self.piece_at(rr, cc):
                    return False
                rr += step_r
                cc += step_c
            return True

        if kind == 'R':
            if dr != 0 and dc != 0:
                return False
            step_r = 0 if dr == 0 else (1 if dr > 0 else -1)
            step_c = 0 if dc == 0 else (1 if dc > 0 else -1)
            rr, cc = r + step_r, c + step_c
            while (rr, cc) != (r2, c2):
                if self.piece_at(rr, cc):
                    return False
                rr += step_r
                cc += step_c
            return True

        if kind == 'Q':
            if dr == 0 or dc == 0 or adr == adc:
                step_r = 0 if dr == 0 else (1 if dr > 0 else -1)
                step_c = 0 if dc == 0 else (1 if dc > 0 else -1)
                rr, cc = r + step_r, c + step_c
                while (rr, cc) != (r2, c2):
                    if self.piece_at(rr, cc):
                        return False
                    rr += step_r
                    cc += step_c
                return True
            return False

        return False

    def legal_move(self, mv: Move, color: Optional[str] = None) -> Tuple[bool, str]:
        color = color or self.turn
        try:
            r1, c1 = algebraic_to_rc(mv.src)
            r2, c2 = algebraic_to_rc(mv.dst)
        except Exception:
            return False, "bad coordinates"

        piece = self.piece_at(r1, c1)
        if not piece:
            return False, "no piece on source"
        if piece[0] != color:
            return False, "not your piece"
        if not self._can_move_like(r1, c1, r2, c2):
            return False, "illegal move pattern"

        # Make move on a copy and ensure king not left in check
        nb = self.copy()
        nb._apply_move_no_checks(r1, c1, r2, c2, mv.promo)
        kr, kc = nb._king_pos(color)
        if nb.is_square_attacked_by(kr, kc, nb.enemy(color)):
            return False, "king would be in check"
        return True, "ok"

    def _apply_move_no_checks(self, r1, c1, r2, c2, promo: Optional[str]):
        piece = self.board[r1][c1]
        self.board[r1][c1] = None
        # promotion
        if piece[1] == 'P' and (r2 == 0 or r2 == 7):
            promo_piece = promo if promo in ('Q', 'R', 'B', 'N') else 'Q'
            self.board[r2][c2] = piece[0] + promo_piece
        else:
            self.board[r2][c2] = piece

    def make_move(self, mv: Move) -> Tuple[bool, str]:
        ok, reason = self.legal_move(mv)
        if not ok:
            return False, reason

        r1, c1 = algebraic_to_rc(mv.src)
        r2, c2 = algebraic_to_rc(mv.dst)
        self._apply_move_no_checks(r1, c1, r2, c2, mv.promo)
        self.history.append(mv.uci)
        self.turn = self.enemy(self.turn)

        # check terminal?
        outcome = self._maybe_terminal()
        if outcome:
            self.result = outcome

        return True, "ok"

    # ----------------------------------------------------------
    # NEW MOVE GENERATOR
    # ----------------------------------------------------------

    def _generate_moves_for_piece(self, r, c, color):
        """Yield all *legal* Move objects for the piece at (r,c)."""
        p = self.piece_at(r, c)
        if not p or p[0] != color:
            return

        kind = p[1]

        DIRS_B = [(1, 1), (1, -1), (-1, 1), (-1, -1)]
        DIRS_R = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        DIRS_Q = DIRS_B + DIRS_R

        if kind == 'P':
            direc = -1 if color == 'w' else 1
            start_row = 6 if color == 'w' else 1

            # forward 1
            rr, cc = r + direc, c
            if in_bounds(rr, cc) and self.piece_at(rr, cc) is None:
                if rr in (0, 7):
                    for promo in "QRBN":
                        yield Move(rc_to_algebraic(r, c) + rc_to_algebraic(rr, cc) + promo)
                else:
                    yield Move(rc_to_algebraic(r, c) + rc_to_algebraic(rr, cc))

                # forward 2
                rr2 = r + 2 * direc
                if r == start_row and in_bounds(rr2, cc) and self.piece_at(rr2, cc) is None:
                    yield Move(rc_to_algebraic(r, c) + rc_to_algebraic(rr2, cc))

            # captures
            for dc in (-1, 1):
                rr, cc = r + direc, c + dc
                if in_bounds(rr, cc):
                    target = self.piece_at(rr, cc)
                    if target and target[0] != color:
                        if rr in (0, 7):
                            for promo in "QRBN":
                                yield Move(rc_to_algebraic(r, c) + rc_to_algebraic(rr, cc) + promo)
                        else:
                            yield Move(rc_to_algebraic(r, c) + rc_to_algebraic(rr, cc))

        elif kind == 'N':
            for dr, dc in [(2, 1), (2, -1), (-2, 1), (-2, -1),
                           (1, 2), (1, -2), (-1, 2), (-1, -2)]:
                rr, cc = r + dr, c + dc
                if in_bounds(rr, cc) and not self.is_own(self.piece_at(rr, cc), color):
                    yield Move(rc_to_algebraic(r, c) + rc_to_algebraic(rr, cc))

        elif kind == 'K':
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0:
                        continue
                    rr, cc = r + dr, c + dc
                    if in_bounds(rr, cc) and not self.is_own(self.piece_at(rr, cc), color):
                        yield Move(rc_to_algebraic(r, c) + rc_to_algebraic(rr, cc))

        elif kind == 'B':
            for dr, dc in DIRS_B:
                for rr, cc in self._ray(r, c, dr, dc):
                    if self.is_own(self.piece_at(rr, cc), color):
                        break
                    yield Move(rc_to_algebraic(r, c) + rc_to_algebraic(rr, cc))
                    if self.piece_at(rr, cc):
                        break

        elif kind == 'R':
            for dr, dc in DIRS_R:
                for rr, cc in self._ray(r, c, dr, dc):
                    if self.is_own(self.piece_at(rr, cc), color):
                        break
                    yield Move(rc_to_algebraic(r, c) + rc_to_algebraic(rr, cc))
                    if self.piece_at(rr, cc):
                        break

        elif kind == 'Q':
            for dr, dc in DIRS_Q:
                for rr, cc in self._ray(r, c, dr, dc):
                    if self.is_own(self.piece_at(rr, cc), color):
                        break
                    yield Move(rc_to_algebraic(r, c) + rc_to_algebraic(rr, cc))
                    if self.piece_at(rr, cc):
                        break

    # ----------------------------------------------------------

    def _has_legal_move(self, color):
        for r in range(8):
            for c in range(8):
                p = self.piece_at(r, c)
                if not p or p[0] != color:
                    continue
                for mv in self._generate_moves_for_piece(r, c, color):
                    ok, _ = self.legal_move(mv, color)
                    if ok:
                        return True
        return False

    # ----------------------------------------------------------

    def _maybe_terminal(self) -> Optional[str]:
        color = self.turn
        kp = self._king_pos(color)

        if kp is None:
            return '1-0' if color == 'b' else '0-1'

        in_check = self.is_square_attacked_by(kp[0], kp[1], self.enemy(color))
        has_moves = self._has_legal_move(color)

        if has_moves:
            return None

        if in_check:
            return '1-0' if color == 'b' else '0-1'
        else:
            return '1/2-1/2'

    def fen(self) -> str:
        rows = []
        for r in range(8):
            s = ""
            empty = 0
            for c in range(8):
                p = self.board[r][c]
                if p is None:
                    empty += 1
                else:
                    if empty > 0:
                        s += str(empty)
                        empty = 0
                    ch = p[1]
                    s += ch.upper() if p[0] == 'w' else ch.lower()
            if empty > 0:
                s += str(empty)
            rows.append(s)

        side = 'w' if self.turn == 'w' else 'b'
        castling = "KQkq"
        enpassant = "-"
        halfmove = 0
        fullmove = 1

        return f"{'/'.join(rows)} {side} {castling} {enpassant} {halfmove} {fullmove}"
