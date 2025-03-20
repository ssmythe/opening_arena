#!/usr/bin/env python3
import argparse
import chess
import chess.pgn
import requests
import logging

#########################
# TREE BUILDING FUNCTIONS
#########################

class RepertoireTree:
    def __init__(self):
        # The tree is a dictionary mapping a FEN string to a dictionary of moves.
        # For a given FEN, tree[fen] is a dict: { move_uci: new_fen, ... }
        self.tree = {}
    
    def add_line(self, game, side="white"):
        """
        Adds one game (variation) from the PGN into the tree.
        For 'white', only record moves when board.turn==White.
        For 'black', only record moves when board.turn==Black.
        """
        board = chess.Board()
        for move in game.mainline_moves():
            if (side == "white" and board.turn == chess.WHITE) or (side == "black" and board.turn == chess.BLACK):
                fen = board.fen()
                uci_move = move.uci()
                board.push(move)
                new_fen = board.fen()
                if fen not in self.tree:
                    self.tree[fen] = {}
                if uci_move not in self.tree[fen]:
                    self.tree[fen][uci_move] = new_fen
            else:
                board.push(move)
    
    def build_from_file(self, filename, side="white"):
        with open(filename, 'r') as pgn_file:
            while True:
                game = chess.pgn.read_game(pgn_file)
                if game is None:
                    break
                self.add_line(game, side=side)
        logging.debug(f"Built {side} tree with {len(self.tree)} nodes.")

    def get_next_move(self, fen):
        """Return a candidate move (as UCI string) for the given fen, or None if not found."""
        if fen in self.tree and self.tree[fen]:
            # Return the first candidate (dictionary iteration order)
            return list(self.tree[fen].keys())[0]
        return None

#########################
# SIMULATION FUNCTION
#########################

def simulate_opening_tree(white_tree, black_tree):
    """
    Simulate the opening battle using the repertoire trees.
    At each turn, the current board's FEN is used to look up the next move.
    Returns a tuple (board, san_sequence) where san_sequence is the list of moves in SAN.
    """
    board = chess.Board()
    san_sequence = []
    
    while True:
        current_fen = board.fen()
        if board.turn == chess.WHITE:
            candidate = white_tree.get_next_move(current_fen)
            if candidate is None:
                logging.debug(f"White out-of-book at FEN: {current_fen}")
                break
            move = chess.Move.from_uci(candidate)
            if move not in board.legal_moves:
                logging.debug(f"White candidate {candidate} illegal at FEN: {current_fen}")
                break
            san = board.san(move)
            san_sequence.append(san)
            board.push(move)
            logging.debug(f"White plays {candidate} ({san}); New FEN: {board.fen()}")
        else:
            candidate = black_tree.get_next_move(current_fen)
            if candidate is None:
                logging.debug(f"Black out-of-book at FEN: {current_fen}")
                break
            move = chess.Move.from_uci(candidate)
            if move not in board.legal_moves:
                logging.debug(f"Black candidate {candidate} illegal at FEN: {current_fen}")
                break
            san = board.san(move)
            san_sequence.append(san)
            board.push(move)
            logging.debug(f"Black plays {candidate} ({san}); New FEN: {board.fen()}")
    logging.debug(f"Final move sequence: {format_san_sequence(san_sequence)}")
    return board, san_sequence

#########################
# HELPER FUNCTIONS
#########################

def format_san_sequence(san_seq):
    """
    Given a list of SAN half-moves, produce a single string with move numbers.
    For example, if san_seq = ['e4', 'e5', 'Nf3', 'Nc6'] then return:
      "1.e4 e5 2.Nf3 Nc6"
    (No space after the move number.)
    """
    moves = []
    move_num = 1
    i = 0
    while i < len(san_seq):
        if i + 1 < len(san_seq):
            moves.append(f"{move_num}.{san_seq[i]} {san_seq[i+1]}")
            i += 2
        else:
            moves.append(f"{move_num}.{san_seq[i]}")
            i += 1
        move_num += 1
    return " ".join(moves)

def query_lichess(fen, ratings):
    """
    Query the Lichess Explorer API using the given FEN and ratings string.
    Returns a tuple: (white_wins, draws, black_wins, total, api_data)
    where api_data is the full JSON response.
    """
    params = {
        "variant": "standard",
        "speeds": "blitz,rapid,classical",
        "ratings": ratings,
        "fen": fen
    }
    api_url = "https://explorer.lichess.ovh/lichess"
    response = requests.get(api_url, params=params)
    response.raise_for_status()
    data = response.json()
    white_wins = data.get("white", 0)
    draws = data.get("draws", 0)
    black_wins = data.get("black", 0)
    total = white_wins + draws + black_wins
    return white_wins, draws, black_wins, total, data

def print_moves_table(moves):
    """
    Given the candidate moves list from the API (each a dict), print a formatted table
    showing for each candidate move its white/draw/black counts and percentages.
    """
    header = (f"{'Move':<12} {'White':>10} {'Draws':>10} {'Black':>10} {'Total':>10} "
              f"{'W%':>8} {'D%':>8} {'B%':>8}")
    print("\nCandidate Moves:")
    print(header)
    print("-" * len(header))
    for m in moves:
        move_str = m.get("san", m.get("uci", ""))
        w = m.get("white", 0)
        d = m.get("draws", 0)
        b = m.get("black", 0)
        tot = w + d + b
        if tot > 0:
            wp = w / tot * 100
            dp = d / tot * 100
            bp = b / tot * 100
        else:
            wp = dp = bp = 0
        print(f"{move_str:<12} {w:10} {d:10} {b:10} {tot:10} "
              f"{wp:7.1f}% {dp:7.1f}% {bp:7.1f}%")

#########################
# MAIN FUNCTION
#########################

def setup_logging(verbose):
    if verbose:
        logging.basicConfig(filename="debug.log",
                            level=logging.DEBUG,
                            format="%(asctime)s - %(levelname)s - %(message)s")
        logging.debug("Debug logging enabled.")
    else:
        logging.basicConfig(level=logging.WARNING)

def main():
    parser = argparse.ArgumentParser(
        description="Opening Arena: Evaluate opening repertoires via Lichess Explorer API"
    )
    parser.add_argument('-w', '--white', required=True, help="White repertoire PGN file")
    parser.add_argument('-b', '--black', required=True, help="Black repertoire PGN file")
    parser.add_argument('-e', '--elo', required=True,
                        help="Comma separated ELO brackets (e.g. 1200,1400,1600,1800)")
    parser.add_argument('-v', '--verbose', action='store_true',
                        help="Enable verbose debug logging to debug.log")
    args = parser.parse_args()

    setup_logging(args.verbose)
    logging.debug("Starting Opening Arena simulation (tree-based).")

    # Build the repertoire trees.
    white_tree = RepertoireTree()
    white_tree.build_from_file(args.white, side="white")
    black_tree = RepertoireTree()
    black_tree.build_from_file(args.black, side="black")

    # Simulate the opening battle.
    board, san_sequence = simulate_opening_tree(white_tree, black_tree)
    fen = board.fen()
    print("White:", args.white)
    print("Black:", args.black)
    print("FEN:", fen)

    if san_sequence:
        san_moves = format_san_sequence(san_sequence)
        print("\nMoves played to reach this position:")
        print(san_moves)
        logging.debug(f"Moves played: {san_moves}")
    else:
        print("\nNo moves were played (empty book?)")
        logging.debug("No moves were played.")

    # If the final move delivered mate, force the result.
    if board.is_checkmate():
        if board.turn == chess.WHITE:
            white_wins, draws, black_wins = 0, 0, 1
        else:
            white_wins, draws, black_wins = 1, 0, 0
        total = 1
        print("\nResult (Mate):")
        print(f"Overall: {white_wins}/{draws}/{black_wins} = {total} = "
              f"{white_wins*100:.1f}%/{draws*100:.1f}%/{black_wins*100:.1f}%")
        logging.debug("Mate reached. Simulation ended.")
        print("\n(Mate reached; no candidate moves table available.)")
    else:
        try:
            white_wins, draws, black_wins, total, api_data = query_lichess(
                fen, args.elo.replace(" ", ""))
        except Exception as e:
            logging.debug(f"API request failed: {e}")
            print("API request failed:", e)
            return

        if total > 0:
            overall_wp = white_wins / total * 100
            overall_dp = draws / total * 100
            overall_bp = black_wins / total * 100
        else:
            overall_wp = overall_dp = overall_bp = 0

        print("\nOverall Result from Lichess Explorer:")
        print(f"Overall: {white_wins}/{draws}/{black_wins} = {total} = "
              f"{overall_wp:.1f}%/{overall_dp:.1f}%/{overall_bp:.1f}%")
        logging.debug(f"Overall API result: {white_wins}/{draws}/{black_wins} = {total}")

        moves = api_data.get("moves", [])
        if moves:
            print_moves_table(moves)
            logging.debug("Candidate moves table printed.")
        else:
            print("No candidate moves available in the API response.")
            logging.debug("No candidate moves available from API.")

if __name__ == '__main__':
    main()
