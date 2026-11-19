import random
import tkinter as tk
from itertools import combinations
from typing import Literal

# --- CORE POKER ENGINE (ZERO EXTERNAL DEPS) ---
SUITS = ("♠", "♥", "♦", "♣")
RANKS = "23456789TJQKA"
RANK_VAL = {r: i + 2 for i, r in enumerate(RANKS)}
HAND_NAMES: tuple[
    Literal["High Card"],
    Literal["One Pair"],
    Literal["Two Pair"],
    Literal["Three of a Kind"],
    Literal["Straight"],
    Literal["Flush"],
    Literal["Full House"],
    Literal["Four of a Kind"],
    Literal["Straight Flush"],
    Literal["Royal Flush"],
] = (
    "High Card",
    "One Pair",
    "Two Pair",
    "Three of a Kind",
    "Straight",
    "Flush",
    "Full House",
    "Four of a Kind",
    "Straight Flush",
    "Royal Flush",
)

BOT_PROFILES = [
    ("Seat 1 · Tight", 0.14, 0.06),
    ("Seat 2 · TAG", 0.22, 0.12),
    ("Seat 3 · Loose", 0.34, 0.18),
    ("Seat 4 · Rock", 0.10, 0.04),
    ("Seat 5 · LAG", 0.38, 0.22),
]

# 6 seat coordinates on a 920x595 canvas (Seat 0 = You at bottom center)
SEAT_POS: list[tuple[int, int]] = [
    (460, 488),  # 0: You (Bottom)
    (175, 435),  # 1: Bottom-Left
    (130, 195),  # 2: Top-Left
    (460, 112),  # 3: Top Center
    (790, 195),  # 4: Top-Right
    (745, 435),  # 5: Bottom-Right
]

DEALER_OFFSET: list[tuple[int, int]] = [
    (0, -68),
    (68, -28),
    (72, 24),
    (0, 62),
    (-72, 24),
    (-68, -28),
]


def eval_5(cards) -> list[int]:
    vals = sorted((RANK_VAL[c[0]] for c in cards), reverse=True)
    suits = [c[1] for c in cards]
    is_flush = len(set(suits)) == 1

    unique_vals = sorted(set(vals), reverse=True)
    is_straight = False
    straight_high = 0
    if len(unique_vals) == 5:
        if unique_vals[0] - unique_vals[4] == 4:
            is_straight = True
            straight_high = unique_vals[0]
        elif unique_vals == [14, 5, 4, 3, 2]:
            is_straight = True
            straight_high = 5

    if is_straight and is_flush:
        return [9, 14] if straight_high == 14 else [8, straight_high]

    counts: dict[int, int] = {}
    for v in vals:
        counts[v] = counts.get(v, 0) + 1
    grouped = sorted(counts.items(), key=lambda x: (x[1], x[0]), reverse=True)
    freq = [g[1] for g in grouped]
    ordered_ranks = [g[0] for g in grouped]

    if freq == [4, 1]:
        return [7, *ordered_ranks]
    if freq == [3, 2]:
        return [6, *ordered_ranks]
    if is_flush:
        return [5, *vals]
    if is_straight:
        return [4, straight_high]
    if freq == [3, 1, 1]:
        return [3, *ordered_ranks]
    if freq == [2, 2, 1]:
        return [2, *ordered_ranks]
    if freq == [2, 1, 1, 1]:
        return [1, *ordered_ranks]
    return [0, *vals]


def best_hand(cards) -> list[int]:
    if len(cards) < 5:
        return [-1]
    return max((eval_5(c) for c in combinations(cards, 5)), key=lambda r: r)


def preflop_strength(hole) -> float:
    v1, v2 = sorted((RANK_VAL[hole[0][0]], RANK_VAL[hole[1][0]]), reverse=True)
    suited = hole[0][1] == hole[1][1]
    pair = v1 == v2
    gap = v1 - v2

    score = (v1 / 14.0) * 0.55
    if pair:
        score += 0.35 + (v1 / 14.0) * 0.15
    else:
        if suited:
            score += 0.08
        if gap == 1:
            score += 0.08
        elif gap == 2:
            score += 0.04
        elif gap >= 4:
            score -= 0.08
    return max(0.05, min(1.0, score))


def bot_decide(hole, board, to_call, pot, stack, min_raise, aggro, bluff_rate):
    if not board:
        strength = preflop_strength(hole)
    else:
        rank_cat = best_hand(hole + board)[0]
        strength = min(1.0, 0.16 + rank_cat * 0.15 + (RANK_VAL[hole[0][0]] / 140.0))

    pot_odds = to_call / (pot + to_call) if to_call > 0 else 0.0
    bluff = random.random() < bluff_rate

    if to_call == 0:
        if strength > (0.72 - aggro * 0.25) or (bluff and stack > min_raise * 2):
            bet = min(stack, max(min_raise, int(pot * random.choice((0.4, 0.65)))))
            return ("raise", bet)
        return ("check", 0)

    if strength >= (0.86 - aggro * 0.18) and stack > to_call:
        raise_amt = min(stack, to_call + max(min_raise, int(pot * 0.65)))
        return ("raise", raise_amt)
    if (
        strength >= pot_odds + (0.14 - aggro * 0.15)
        or (to_call <= min_raise and strength >= 0.30)
        or bluff
    ):
        return ("call", min(stack, to_call))
    return ("fold", 0)


class SixMaxPokerTable:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("6-Max Hold'em — Low-RAM Table")
        self.root.configure(bg="#0b1510")
        self.root.geometry("920x660")
        self.root.resizable(False, False)

        self.sb = 10
        self.bb = 20
        self.dealer_idx: int = 5
        self.current_turn: int | None = None

        self.names = ["You"] + [p[0] for p in BOT_PROFILES]
        self.aggros = [0.0] + [p[1] for p in BOT_PROFILES]
        self.bluffs = [0.0] + [p[2] for p in BOT_PROFILES]
        self.stacks = [1000] * 6

        self._build_ui()
        self.start_hand()

    def _build_ui(self):
        self.canvas = tk.Canvas(
            self.root, width=920, height=595, bg="#0b1510", highlightthickness=0
        )
        self.canvas.pack(fill="both", expand=True)

        # Outer wooden rail & green felt oval
        self.canvas.create_oval(
            125, 115, 795, 485, fill="#3b2112", outline="#5c361e", width=8
        )
        self.canvas.create_oval(
            142, 130, 778, 470, fill="#14452f", outline="#1e6847", width=3
        )
        self.canvas.create_oval(
            162, 148, 758, 452, fill="", outline="#1b593c", width=1, dash=(6, 6)
        )

        # Pot & Street Readouts on Felt
        self.pot_text = self.canvas.create_text(
            460, 232, text="POT: $0", fill="#f4d03f", font=("Consolas", 15, "bold")
        )
        self.street_text = self.canvas.create_text(
            460, 206, text="PREFLOP", fill="#a3e4d7", font=("Consolas", 10, "bold")
        )
        self.status_text = self.canvas.create_text(
            460, 355, text="", fill="#ffffff", font=("Consolas", 10, "bold"), width=420
        )
        self.hand_readout = self.canvas.create_text(
            460, 378, text="", fill="#f7dc6f", font=("Consolas", 10)
        )

        # 5 Community Card Slots
        self.board_rects = []
        self.board_texts = []
        for i in range(5):
            x0 = 335 + i * 54
            y0, x1, y1 = 252, x0 + 44, 316
            r = self.canvas.create_rectangle(
                x0, y0, x1, y1, fill="#103826", outline="#247150", width=1
            )
            t = self.canvas.create_text(
                (x0 + x1) / 2, (y0 + y1) / 2, text="", font=("Consolas", 13, "bold")
            )
            self.board_rects.append(r)
            self.board_texts.append(t)

        # 6 Seat Pods + Hole Cards + Dealer Button
        self.seat_boxes = []
        self.seat_name_lbls = []
        self.seat_info_lbls = []
        self.seat_card_rects = []
        self.seat_card_texts = []
        self.dealer_badge = self.canvas.create_oval(
            0, 0, 22, 22, fill="#f1c40f", outline="#ffffff", width=2
        )
        self.dealer_txt = self.canvas.create_text(
            0, 0, text="D", fill="#111111", font=("Consolas", 9, "bold")
        )

        for idx, (cx, cy) in enumerate(SEAT_POS):
            box = self.canvas.create_rectangle(
                cx - 76,
                cy - 34,
                cx + 76,
                cy + 36,
                fill="#13261d",
                outline="#2c4a3c",
                width=2,
            )
            n_lbl = self.canvas.create_text(
                cx,
                cy - 18,
                text=self.names[idx],
                fill="#ecf0f1",
                font=("Consolas", 9, "bold"),
            )
            i_lbl = self.canvas.create_text(
                cx, cy + 16, text="$1000", fill="#f4d03f", font=("Consolas", 9)
            )
            self.seat_boxes.append(box)
            self.seat_name_lbls.append(n_lbl)
            self.seat_info_lbls.append(i_lbl)

            c_rects = []
            c_texts = []
            for k in range(2):
                rx0 = cx - 34 + k * 34
                ry0, rx1, ry1 = cy - 10, rx0 + 30, cy + 10
                cr = self.canvas.create_rectangle(
                    rx0, ry0, rx1, ry1, fill="#1c3b2c", outline="#386650"
                )
                ct = self.canvas.create_text(
                    (rx0 + rx1) / 2,
                    (ry0 + ry1) / 2,
                    text="",
                    font=("Consolas", 9, "bold"),
                )
                c_rects.append(cr)
                c_texts.append(ct)
            self.seat_card_rects.append(c_rects)
            self.seat_card_texts.append(c_texts)

        # Bottom Control Bar
        ctrl = tk.Frame(self.root, bg="#111f18", pady=9)
        ctrl.pack(fill="x", side="bottom")

        cfg = {
            "font": ("Consolas", 10, "bold"),
            "width": 11,
            "bd": 0,
            "pady": 6,
            "cursor": "hand2",
        }
        self.btn_fold = tk.Button(
            ctrl, text="Fold", bg="#c0392b", fg="white", command=self.on_fold, **cfg
        )
        self.btn_fold.pack(side="left", padx=(24, 6))

        self.btn_call = tk.Button(
            ctrl, text="Check", bg="#2980b9", fg="white", command=self.on_call, **cfg
        )
        self.btn_call.pack(side="left", padx=6)

        self.btn_raise = tk.Button(
            ctrl,
            text="Raise $40",
            bg="#27ae60",
            fg="white",
            command=self.on_raise,
            **cfg,
        )
        self.btn_raise.pack(side="left", padx=6)

        self.raise_scale = tk.Scale(
            ctrl,
            from_=40,
            to=1000,
            orient="horizontal",
            bg="#111f18",
            fg="white",
            highlightthickness=0,
            length=180,
            showvalue=False,
            command=self._sync_raise_lbl,
        )
        self.raise_scale.pack(side="left", padx=8)

        self.btn_next = tk.Button(
            ctrl,
            text="Next Hand",
            bg="#f39c12",
            fg="black",
            command=self.start_hand,
            **cfg,
        )
        self.btn_next.pack(side="right", padx=24)

    def _sync_raise_lbl(self, val):
        self.btn_raise.config(text=f"Raise ${val}")

    def _active_seats(self) -> list[int]:
        return [i for i in range(6) if not self.folded[i]]

    def _next_seat(self, current: int, predicate) -> int | None:
        for step in range(1, 7):
            nxt = (current + step) % 6
            if predicate(nxt):
                return nxt
        return None

    def start_hand(self):
        for i in range(6):
            if self.stacks[i] < self.bb:
                self.stacks[i] = 1000

        self.deck = [r + s for r in RANKS for s in SUITS]
        random.shuffle(self.deck)

        nxt_dealer = self._next_seat(self.dealer_idx, lambda i: self.stacks[i] > 0)
        if nxt_dealer is None:
            return
        self.dealer_idx = nxt_dealer

        self.holes = [[self.deck.pop(), self.deck.pop()] for _ in range(6)]
        self.board: list[str] = []
        self.folded = [False] * 6
        self.bets = [0] * 6
        self.acted = [False] * 6
        self.pot = 0
        self.stage = 0
        self.hand_over = False
        self.current_turn = None

        sb_seat = self._next_seat(self.dealer_idx, lambda i: self.stacks[i] > 0)
        if sb_seat is None:
            return
        bb_seat = self._next_seat(sb_seat, lambda i: self.stacks[i] > 0)
        if bb_seat is None:
            return

        self._post_blind(sb_seat, self.sb)
        self._post_blind(bb_seat, self.bb)

        self.btn_next.config(state="disabled")
        self.current_turn = self._next_seat(
            bb_seat, lambda i: not self.folded[i] and self.stacks[i] > 0
        )
        self._set_status(
            f"Hand started · {self.names[self.dealer_idx]} has Dealer button."
        )
        self._refresh_table(reveal_all=False)
        self._schedule_turn()

    def _post_blind(self, seat: int, amount: int):
        put = min(self.stacks[seat], amount)
        self.stacks[seat] -= put
        self.bets[seat] += put
        self.pot += put

    def _set_status(self, text: str):
        self.canvas.itemconfig(self.status_text, text=text)

    def _refresh_table(self, reveal_all: bool = False):
        streets = ("PREFLOP", "FLOP", "TURN", "RIVER", "SHOWDOWN")
        self.canvas.itemconfig(self.street_text, text=streets[min(self.stage, 4)])
        self.canvas.itemconfig(self.pot_text, text=f"POT: ${self.pot}")

        # Dealer button placement
        dx, dy = DEALER_OFFSET[self.dealer_idx]
        sx, sy = SEAT_POS[self.dealer_idx]
        bx, by = sx + dx, sy + dy
        self.canvas.coords(self.dealer_badge, bx - 11, by - 11, bx + 11, by + 11)
        self.canvas.coords(self.dealer_txt, bx, by)

        # Board cards
        for i in range(5):
            if i < len(self.board):
                card = self.board[i]
                col = "#c0392b" if card[1] in ("♥", "♦") else "#111111"
                self.canvas.itemconfig(
                    self.board_rects[i], fill="#ffffff", outline="#d5dbdb"
                )
                self.canvas.itemconfig(
                    self.board_texts[i], text=f"{card[0]}{card[1]}", fill=col
                )
            else:
                self.canvas.itemconfig(
                    self.board_rects[i], fill="#103826", outline="#247150"
                )
                self.canvas.itemconfig(self.board_texts[i], text="")

        # Seat cards & status
        for i in range(6):
            is_turn = i == self.current_turn and not self.hand_over
            outline = (
                "#f1c40f" if is_turn else ("#4a235a" if self.folded[i] else "#2c4a3c")
            )
            fill = (
                "#1c382b" if is_turn else ("#121714" if self.folded[i] else "#13261d")
            )
            self.canvas.itemconfig(
                self.seat_boxes[i],
                outline=outline,
                fill=fill,
                width=3 if is_turn else 2,
            )

            status_tag = (
                " [FOLD]"
                if self.folded[i]
                else (f" (${self.bets[i]})" if self.bets[i] > 0 else "")
            )
            self.canvas.itemconfig(
                self.seat_info_lbls[i], text=f"${self.stacks[i]}{status_tag}"
            )

            for k in range(2):
                if self.folded[i]:
                    self.canvas.itemconfig(
                        self.seat_card_rects[i][k], fill="#181c1a", outline="#282d2a"
                    )
                    self.canvas.itemconfig(
                        self.seat_card_texts[i][k], text="", fill="#666"
                    )
                elif i == 0 or reveal_all:
                    c = self.holes[i][k]
                    col = "#c0392b" if c[1] in ("♥", "♦") else "#111111"
                    self.canvas.itemconfig(
                        self.seat_card_rects[i][k], fill="#ffffff", outline="#cccccc"
                    )
                    self.canvas.itemconfig(
                        self.seat_card_texts[i][k], text=f"{c[0]}{c[1]}", fill=col
                    )
                else:
                    self.canvas.itemconfig(
                        self.seat_card_rects[i][k], fill="#24476b", outline="#5dade2"
                    )
                    self.canvas.itemconfig(
                        self.seat_card_texts[i][k], text="♦", fill="#aed6f1"
                    )

        # Live hand readout for player
        if self.folded[0]:
            self.canvas.itemconfig(self.hand_readout, text="You folded this hand.")
        elif len(self.board) >= 3:
            r = best_hand(self.holes[0] + self.board)
            self.canvas.itemconfig(
                self.hand_readout, text=f"Your Hand: {HAND_NAMES[r[0]]}"
            )
        else:
            p = self.holes[0][0][0] == self.holes[0][1][0]
            self.canvas.itemconfig(
                self.hand_readout,
                text=f"Your Hole: {'Pocket Pair' if p else 'High Cards'}",
            )

    def _schedule_turn(self):
        if self.hand_over:
            return
        active = self._active_seats()
        if len(active) == 1:
            winner = active[0]
            self.stacks[winner] += self.pot
            self._end_hand(
                f"{self.names[winner]} wins ${self.pot} (everyone else folded).",
                reveal=False,
            )
            return

        if self.current_turn is None:
            self._advance_round_or_showdown()
            return

        if self.current_turn == 0:
            self._enable_player_controls()
        else:
            self._disable_player_controls()
            seat = self.current_turn
            self._set_status(f"{self.names[seat]} is acting...")
            self.root.after(260, lambda s=seat: self._execute_bot(s))

    def _enable_player_controls(self):
        high_bet = max(self.bets)
        to_call = max(0, high_bet - self.bets[0])
        self.btn_fold.config(state="normal")
        self.btn_call.config(
            state="normal",
            text="Check" if to_call == 0 else f"Call ${min(self.stacks[0], to_call)}",
        )

        min_r = max(self.bb, to_call * 2)
        if self.stacks[0] > to_call:
            self.btn_raise.config(state="normal")
            lo = min(self.stacks[0], min_r)
            hi = self.stacks[0]
            self.raise_scale.config(state="normal", from_=lo, to=hi)
            self.raise_scale.set(lo)
            self._sync_raise_lbl(lo)
        else:
            self.btn_raise.config(state="disabled")
            self.raise_scale.config(state="disabled")

    def _disable_player_controls(self):
        for w in (self.btn_fold, self.btn_call, self.btn_raise, self.raise_scale):
            w.config(state="disabled")

    def on_fold(self):
        self._disable_player_controls()
        self.folded[0] = True
        self.acted[0] = True
        self._after_action(0, "You folded.")

    def on_call(self):
        self._disable_player_controls()
        to_call = min(self.stacks[0], max(0, max(self.bets) - self.bets[0]))
        self.stacks[0] -= to_call
        self.bets[0] += to_call
        self.pot += to_call
        self.acted[0] = True
        self._after_action(
            0, "You checked." if to_call == 0 else f"You called ${to_call}."
        )

    def on_raise(self):
        self._disable_player_controls()
        amt = min(self.stacks[0], int(self.raise_scale.get()))
        self.stacks[0] -= amt
        self.bets[0] += amt
        self.pot += amt
        for i in range(6):
            if i != 0 and not self.folded[i] and self.stacks[i] > 0:
                self.acted[i] = False
        self.acted[0] = True
        self._after_action(0, f"You raised to ${self.bets[0]}.")

    def _execute_bot(self, seat: int):
        if self.hand_over or self.folded[seat]:
            return
        high_bet = max(self.bets)
        to_call = max(0, high_bet - self.bets[seat])
        action, amt = bot_decide(
            self.holes[seat],
            self.board,
            to_call,
            self.pot,
            self.stacks[seat],
            self.bb,
            self.aggros[seat],
            self.bluffs[seat],
        )

        if action == "fold" and to_call > 0:
            self.folded[seat] = True
            self.acted[seat] = True
            msg = f"{self.names[seat]} folds."
        elif action == "raise" and self.stacks[seat] > to_call:
            put = min(self.stacks[seat], amt)
            self.stacks[seat] -= put
            self.bets[seat] += put
            self.pot += put
            for i in range(6):
                if i != seat and not self.folded[i] and self.stacks[i] > 0:
                    self.acted[i] = False
            self.acted[seat] = True
            msg = f"{self.names[seat]} raises to ${self.bets[seat]}."
        else:
            put = min(self.stacks[seat], to_call)
            self.stacks[seat] -= put
            self.bets[seat] += put
            self.pot += put
            self.acted[seat] = True
            msg = (
                f"{self.names[seat]} checks."
                if put == 0
                else f"{self.names[seat]} calls ${put}."
            )

        self._after_action(seat, msg)

    def _after_action(self, seat: int, msg: str):
        self._set_status(msg)
        active = self._active_seats()
        if len(active) == 1:
            self._refresh_table(reveal_all=False)
            self._schedule_turn()
            return

        high_bet = max(self.bets)
        can_act = [i for i in active if self.stacks[i] > 0]
        round_complete = all(
            self.acted[i] and self.bets[i] == high_bet for i in can_act
        )

        if round_complete or len(can_act) <= 1:
            self.current_turn = None
        else:
            self.current_turn = self._next_seat(
                seat, lambda i: not self.folded[i] and self.stacks[i] > 0
            )

        self._refresh_table(reveal_all=False)
        self._schedule_turn()

    def _advance_round_or_showdown(self):
        self.bets = [0] * 6
        self.acted = [False] * 6
        self.stage += 1

        if self.stage == 1:
            self.board.extend([self.deck.pop() for _ in range(3)])
        elif self.stage in (2, 3):
            self.board.append(self.deck.pop())
        else:
            self._showdown()
            return

        can_act = [i for i in self._active_seats() if self.stacks[i] > 0]
        if len(can_act) <= 1:
            self._refresh_table(reveal_all=False)
            self.root.after(300, self._advance_round_or_showdown)
            return

        self.current_turn = self._next_seat(
            self.dealer_idx, lambda i: not self.folded[i] and self.stacks[i] > 0
        )
        self._refresh_table(reveal_all=False)
        self._schedule_turn()

    def _showdown(self):
        while len(self.board) < 5:
            self.board.append(self.deck.pop())

        contenders = self._active_seats()
        scores = {i: best_hand(self.holes[i] + self.board) for i in contenders}
        best_score = max(scores.values())
        winners = [i for i, sc in scores.items() if sc == best_score]

        share = self.pot // len(winners)
        remainder = self.pot - share * len(winners)
        for idx_w, w in enumerate(winners):
            self.stacks[w] += share + (remainder if idx_w == 0 else 0)

        hand_label = HAND_NAMES[best_score[0]]
        if len(winners) == 1:
            w = winners[0]
            msg = f"Showdown: {self.names[w]} wins ${self.pot} with {hand_label}!"
        else:
            names_str = ", ".join(self.names[w] for w in winners)
            msg = f"Split Pot (${self.pot}) between {names_str} ({hand_label})!"

        self._end_hand(msg, reveal=True)

    def _end_hand(self, msg: str, reveal: bool = False):
        self.hand_over = True
        self.current_turn = None
        self._disable_player_controls()
        self._refresh_table(reveal_all=reveal)
        self._set_status(msg)
        self.btn_next.config(state="normal")


if __name__ == "__main__":
    root = tk.Tk()
    SixMaxPokerTable(root)
    root.mainloop()
