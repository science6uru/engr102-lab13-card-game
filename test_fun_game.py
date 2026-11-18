"""Headless tests for fun_game.py - Stage 1 harness (issue #1).

No window, no pygame, no sound card needed. Run from this folder:

    python -m unittest -v test_fun_game

Every test is one numbered case from game_plan.txt section 4. A stage is
finished when its tests pass.

Tests written with the help of GLM 5.3 (AI-assisted code, allowed by the
lab rules; the planning document and reflection stay team-written).
"""

import os
import sys
import io
import contextlib
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# Stage 3+ needs pygame headless.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import fun_game as g          # noqa: E402  (after sys.path setup)
import pygame                 # noqa: E402


class Stage1CardsAsData(unittest.TestCase):
    """Issue #1 - make_card and make_deck."""

    def test_1_1_deck_has_52_unique_cards(self):
        """make_deck(): 52 cards, every (suit, rank) pair exactly once."""
        deck = g.make_deck()
        self.assertEqual(len(deck), 52)
        pairs = {(c["suit"], c["rank"]) for c in deck}
        self.assertEqual(pairs, {(s, r) for s in g.SUITS for r in g.RANKS})

    def test_1_2_make_card_starting_values(self):
        """make_card("hearts", "queen") starts with the contract values."""
        card = g.make_card("hearts", "queen")
        self.assertEqual(card["suit"], "hearts")
        self.assertEqual(card["rank"], "queen")
        self.assertEqual(card["zone"], "deck")
        self.assertIsNone(card["slot"])
        self.assertIsNone(card["owner"])
        self.assertFalse(card["face_up"])
        self.assertIsNone(card["motion"])
        self.assertEqual(card["target"], [0.0, 0.0])
        # pos must EQUAL DECK_POS and be a LIST, not the tuple itself
        self.assertEqual(card["pos"], list(g.DECK_POS))
        self.assertIsInstance(card["pos"], list)

    def test_1_3_cards_do_not_share_a_position(self):
        """Moving card A in place must not move card B or the constant.

        The trap: pos=DECK_POS with list(pos) forgotten means every card
        edits the SAME position list.
        """
        a = g.make_card("hearts", "queen")
        b = g.make_card("clubs", "2")
        a["pos"][0] = 5                       # change A's pos IN PLACE
        self.assertEqual(b["pos"], list(g.DECK_POS))
        self.assertEqual(g.DECK_POS, (460, 330))

    def test_1_4_slot_layout_fits_and_does_not_overlap(self):
        """Every grid/hand slot, deck and discard: inside the window,
        card rectangles never overlapping."""
        self.assertEqual(len(g.PLAYER_GRID_SLOTS), g.NUM_PLAYERS)
        centers = []
        for slots in g.PLAYER_GRID_SLOTS:
            self.assertEqual(len(slots), 4)
            centers.extend(slots)
        for slots in g.PLAYER_HAND_SLOTS:
            centers.extend(slots)
        centers.extend([g.DECK_POS, g.DISCARD_POS])
        w, h = g.CARD_SIZE
        win_w, win_h = g.WINDOW_SIZE
        for x, y in centers:
            self.assertTrue(x - w / 2 >= 0 and x + w / 2 <= win_w,
                            f"slot {(x, y)} sticks out sideways")
            self.assertTrue(y - h / 2 >= 0 and y + h / 2 <= win_h,
                            f"slot {(x, y)} sticks out vertically")
        boxes = [(x - w / 2, y - h / 2, x + w / 2, y + h / 2)
                 for x, y in centers]
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                a, b = boxes[i], boxes[j]
                overlaps = (a[0] < b[2] and b[0] < a[2]
                            and a[1] < b[3] and b[1] < a[3])
                self.assertFalse(
                    overlaps,
                    f"card rectangles of {centers[i]} and {centers[j]} overlap")

    def test_1_5_make_card_owner_starts_none(self):
        """A fresh card belongs to no player yet."""
        self.assertIsNone(g.make_card("spades", "10")["owner"])


def card(suit="hearts", rank="queen"):
    """Stand-in for make_card() until Stage 1 merges - same contract.

    Lets the Stage 2 tests run while make_card is still a stub. Once
    Stage 1 lands, these tests could use g.make_card directly.
    """
    return {"suit": suit, "rank": rank, "pos": list(g.DECK_POS),
            "face_up": False, "zone": "deck", "slot": None,
            "owner": None, "motion": None, "target": [0.0, 0.0]}


def deck_of_52():
    """52 fresh cards via the stand-in (avoids the make_deck stub)."""
    return [card(s, r) for s in g.SUITS for r in g.RANKS]


class Stage2ZonesShufflingDealing(unittest.TestCase):
    """Issue #2 - reset_card_zone, shuffle_deck, deal_card, make_state."""

    def test_2_1_reset_zone_without_pos(self):
        """zone/slot/face_up change; motion is left alone."""
        c = card()
        c["motion"] = "glide"                     # must NOT be touched
        g.reset_card_zone(c, "grid", slot=2, face_up=True)
        self.assertEqual(c["zone"], "grid")
        self.assertEqual(c["slot"], 2)
        self.assertTrue(c["face_up"])
        self.assertEqual(c["motion"], "glide")

    def test_2_2_reset_zone_with_pos_teleports_and_clears_motion(self):
        """Giving a pos moves the card there and clears motion."""
        c = card()
        c["motion"] = "glide"
        c["pos"] = [0.0, 0.0]
        g.reset_card_zone(c, "discard", pos=g.DISCARD_POS)
        self.assertEqual(c["pos"], list(g.DISCARD_POS))
        self.assertIsNone(c["motion"])
        self.assertEqual(c["zone"], "discard")

    def test_2_3_shuffle_keeps_same_cards_different_order(self):
        """Same 52 (suit, rank) pairs, different order. Needs the real
        make_deck, so this test stays RED until Stage 1 merges."""
        deck = g.make_deck()
        before = sorted((c["suit"], c["rank"]) for c in deck)
        g.shuffle_deck(deck)
        after = sorted((c["suit"], c["rank"]) for c in deck)
        self.assertEqual(before, after)
        self.assertNotEqual([c["suit"] for c in deck],
                            [c["suit"] for c in sorted(
                                deck, key=lambda c: (c["suit"], c["rank"]))])

    def test_2_4_deal_from_empty_deck_returns_none(self):
        """Empty deck: None, no crash, hand unchanged."""
        hand = [None] * 5
        self.assertIsNone(g.deal_card([], hand))
        self.assertEqual(hand, [None] * 5)

    def test_2_5_deal_moves_top_card_into_the_hand(self):
        """Fresh deck into an empty hand: hand[0] is the card, it is
        face up in zone "hand" slot 0, and the deck shrinks by 1."""
        deck = deck_of_52()
        top = deck[0]
        hand = [None] * 1
        dealt = g.deal_card(deck, hand)
        self.assertIs(dealt, top)
        self.assertIs(hand[0], top)
        self.assertEqual(top["zone"], "hand")
        self.assertEqual(top["slot"], 0)
        self.assertTrue(top["face_up"])
        self.assertEqual(len(deck), 51)

    def test_2_6_deal_into_full_hand_returns_none(self):
        """Full hand: None, nothing changes anywhere."""
        deck = deck_of_52()
        full = [card() for _ in range(2)]
        self.assertIsNone(g.deal_card(deck, full))
        self.assertEqual(len(deck), 52)

    def test_2_7_dealing_to_player_1_leaves_player_0_alone(self):
        """deal_card into player 1's hand: player 0's hand stays empty."""
        state = g.make_state(2)
        deck = deck_of_52()
        g.deal_card(deck, state["players"][1]["hand_occ"])
        self.assertIsNotNone(state["players"][1]["hand_occ"][0])
        self.assertEqual(state["players"][0]["hand_occ"], [None])

    def test_2_8_make_state_players_are_separate(self):
        """Two players, OWN lists each, current starts at 0."""
        state = g.make_state(2)
        self.assertEqual(len(state["players"]), 2)
        self.assertEqual(state["current"], 0)
        state["players"][0]["grid_occ"][0] = "x"
        self.assertIsNone(state["players"][1]["grid_occ"][0])

    def test_2_9_reset_zone_sets_and_clears_owner(self):
        """owner=1 sticks in "grid"; moving to "discard" clears it."""
        c = card()
        g.reset_card_zone(c, "grid", slot=1, owner=1)
        self.assertEqual(c["owner"], 1)
        g.reset_card_zone(c, "discard")
        self.assertIsNone(c["owner"])


class Stage3Loading(unittest.TestCase):
    """Issue #3 - loading pictures and sounds (ported from
    test_resource_loader.py, unittest + numbering per team harness)."""

    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))   # convert_alpha needs a display

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_3_1_deck_faces_has_52_entries(self):
        faces = g.load_deck_faces()
        self.assertEqual(len(faces), 52)
        for suit in g.SUITS:
            for rank in g.RANKS:
                self.assertIn((suit, rank), faces)

    def test_3_2_every_picture_is_card_size(self):
        faces = g.load_deck_faces()
        back = g.load_card_back()
        for face in faces.values():
            self.assertEqual(face.get_size(), g.CARD_SIZE)
        self.assertEqual(back.get_size(), g.CARD_SIZE)

    def test_3_3_load_sfx_returns_every_kind(self):
        sfx = g.load_sfx()
        for kind in ["slide", "place", "shove", "fan", "shuffle",
                     "pack_open", "pack_take_out"]:
            self.assertIn(kind, sfx)
            self.assertIsInstance(sfx[kind], list)
            self.assertTrue(sfx[kind], f"no sounds loaded for {kind!r}")

    def test_3_4_play_never_repeats_a_variant(self):
        class FakeSound:
            def __init__(self, name):
                self.name = name
                self.play_count = 0

            def play(self):
                self.play_count += 1

        sounds = {"slide": [FakeSound("sound1"), FakeSound("sound2")]}
        g._last_played.clear()

        previous = None
        for _ in range(100):
            g.play(sounds, "slide")
            played = sounds["slide"][g._last_played["slide"]].name
            self.assertNotEqual(played, previous)
            previous = played

        # No sounds / unknown kind: play() does nothing, no crash.
        g.play({}, "slide")
        g.play({"slide": []}, "slide")
        g.play({"place": []}, "slide")


class Stage4Drawing(unittest.TestCase):
    """Issue #4 - drawing a still table."""

    def test_4_1_card_rect_size_and_center(self):
        card = g.make_card("hearts", "queen")
        card["pos"] = [123.4, 77.7]
        rect = g.card_rect(card)
        self.assertEqual(rect.size, g.CARD_SIZE)
        self.assertEqual(rect.center, (123, 78))

    def test_4_2_current_texture_face_or_back(self):
        face = pygame.Surface((7, 7))    # dummy "face" surface
        back = pygame.Surface((9, 9))    # dummy "back" surface
        faces = {("hearts", "queen"): face}
        card = g.make_card("hearts", "queen")

        card["face_up"] = True
        self.assertIs(g.current_texture(card, faces, back), face)
        card["face_up"] = False
        self.assertIs(g.current_texture(card, faces, back), back)


class Stage5LoopAndVsync(unittest.TestCase):
    """Issue #5 - the game loop, time and vsync."""

    def test_5_1_main_runs_120_frames_headless(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            g.main(frames=120)
        out = buf.getvalue()
        self.assertTrue(out.startswith("pacing:"), out)
        self.assertIn("120 frames", out)


def placed(suit, rank, zone="hand", slot=0, owner=0, pos=(100, 100),
           face_up=True):
    """A real make_card put on the table the official way."""
    c = g.make_card(suit, rank, face_up=face_up)
    g.reset_card_zone(c, zone, pos=pos, slot=slot, owner=owner)
    return c


class Stage6PickingUp(unittest.TestCase):
    """Issue #8 - blend, top_card_at, begin_drag, update_drag."""

    def test_6_0_make_card_has_the_announced_keys(self):
        """Contract: the new drag keys exist with their starting values."""
        c = g.make_card("hearts", "queen")
        self.assertFalse(c["dragging"])
        self.assertEqual(c["drag_offset"], (0.0, 0.0))
        self.assertEqual(c["press_pos"], (0.0, 0.0))

    def test_6_1_top_card_wins_empty_table_gives_none(self):
        """Two overlapping cards: the LATER one in the list is on top."""
        a = placed("hearts", "queen", slot=0, pos=(100, 100))
        b = placed("clubs", "2", slot=1, pos=(110, 100))
        point = (105, 100)                   # inside both rectangles
        self.assertIs(g.top_card_at([a, b], point), b)
        self.assertIs(g.top_card_at([b, a], point), a)
        self.assertIsNone(g.top_card_at([a, b], (900, 600)))
        self.assertIsNone(g.top_card_at([], point))

    def test_6_2_deck_cards_are_never_returned(self):
        """A card in zone "deck" cannot be grabbed, even under the point."""
        c = g.make_card("hearts", "queen")   # zone "deck" at DECK_POS
        self.assertIsNone(g.top_card_at([c], g.DECK_POS))

    def test_6_3_begin_drag_remembers_grab_offset(self):
        """Card at [100,100], mouse (110,90): offset is (-10, 10)."""
        c = placed("hearts", "queen", pos=(100, 100))
        g.begin_drag(c, (110, 90), {})
        self.assertTrue(c["dragging"])
        self.assertEqual(c["drag_offset"], (-10, 10))
        self.assertEqual(c["press_pos"], (110, 90))

    def test_6_4_update_drag_eases_toward_the_cursor(self):
        """One frame: strictly between start and target. Two seconds:
        within 1 pixel of the target."""
        c = placed("hearts", "queen", pos=(100, 100))
        g.begin_drag(c, (100, 100), {})      # offset (0, 0)
        g.update_drag(c, (200, 100), 1 / 120)
        self.assertGreater(c["pos"][0], 100)
        self.assertLess(c["pos"][0], 200)
        for _ in range(240):                 # 240 frames x 1/120 s = 2 s
            g.update_drag(c, (200, 100), 1 / 120)
        self.assertAlmostEqual(c["pos"][0], 200, delta=1)

    def test_6_5_blend_is_frame_rate_independent(self):
        """One second of frames leaves the same distance at 60 and 240 fps."""
        rate = 12
        left_60 = 1.0
        for _ in range(60):
            left_60 *= 1 - g.blend(rate, 1 / 60)
        left_240 = 1.0
        for _ in range(240):
            left_240 *= 1 - g.blend(rate, 1 / 240)
        self.assertAlmostEqual(left_60, left_240, delta=1e-9)

    def test_6_6_top_card_at_respects_the_owner_filter(self):
        """owner=1 ignores player 0's card under the point."""
        mine = placed("hearts", "queen", owner=0, slot=0, pos=(100, 100))
        theirs = placed("clubs", "2", owner=1, slot=0, pos=(100, 100))
        point = (100, 100)
        # player 0's card is LATER (on top), yet owner=1 must skip it
        self.assertIs(g.top_card_at([theirs, mine], point, owner=1), theirs)
        self.assertIsNone(g.top_card_at([mine], point, owner=1))
        self.assertIs(g.top_card_at([theirs, mine], point), mine)


class Stage7FlippingAndClicking(unittest.TestCase):
    """Issue #14 - flip_card, pickup_flip, release_card (click vs drag)."""

    def setUp(self):
        self.state = g.make_state(2)
        self.state["sfx"] = {}

    def test_7_0_pickup_flip_key_starts_false(self):
        """Contract: make_card gains pickup_flip, starting False."""
        self.assertFalse(g.make_card("hearts", "queen")["pickup_flip"])

    def test_7_1_flip_card_toggles_immediately(self):
        c = placed("hearts", "queen", face_up=True)
        g.flip_card(c, {})
        self.assertFalse(c["face_up"])
        g.flip_card(c, {})
        self.assertTrue(c["face_up"])

    def test_7_2_click_on_a_face_up_card_flips_it_down(self):
        c = placed("hearts", "queen", face_up=True, pos=(100, 100))
        g.begin_drag(c, (100, 100), {})
        g.release_card(c, (100, 100), self.state)
        self.assertFalse(c["face_up"])
        self.assertFalse(c["dragging"])

    def test_7_3_click_on_a_face_down_card_reveals_it_once(self):
        c = placed("hearts", "queen", face_up=False, pos=(100, 100))
        g.begin_drag(c, (100, 100), {})
        self.assertTrue(c["face_up"])        # flipped as it was lifted
        self.assertTrue(c["pickup_flip"])
        g.release_card(c, (100, 100), self.state)
        self.assertTrue(c["face_up"])        # NOT flipped back down
        self.assertFalse(c["pickup_flip"])

    def test_7_4_a_real_drag_is_not_a_click(self):
        """Extra: moving 8 px or more before release never flips."""
        up = placed("hearts", "queen", face_up=True, pos=(100, 100))
        g.begin_drag(up, (100, 100), {})
        g.release_card(up, (100 + g.CLICK_DIST, 100), self.state)
        self.assertTrue(up["face_up"])       # a drag leaves it as it was
        down = placed("clubs", "2", face_up=False, pos=(100, 100))
        g.begin_drag(down, (100, 100), {})
        g.release_card(down, (300, 100), self.state)
        self.assertTrue(down["face_up"])     # revealed by lifting, once


if __name__ == "__main__":
    unittest.main()
