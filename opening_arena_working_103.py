#!/usr/bin/env python3
import argparse
import chess
import chess.pgn
import requests
import logging

##############################
# Helper: Setup Logging
##############################
def setup_logging(verbose):
    if verbose:
        logging.basicConfig(filename="debug.log",
                            level=logging.DEBUG,
                            format="%(asctime)s - %(levelname)s - %(message)s")
        logging.debug("Debug logging enabled.")
    else:
        logging.basicConfig(level=logging.WARNING)

##############################
# PHASE 1: Build Repertoire Trees (with variations)
##############################
class RepertoireTree:
    def __init__(self):
        # tree maps a FEN string to a dictionary of moves (UCI) and resulting child FENs.
        self.tree = {}
    
    def insert(self, key_fen, move_uci, child_fen):
        if key_fen not in self.tree:
            self.tree[key_fen] = {}
        if move_uci not in self.tree[key_fen]:
            self.tree[key_fen][move_uci] = child_fen

def process_white_node(node, board, tree):
    """Recursively traverse a PGN node and record White's moves."""
    for variation in node.variations:
        move = variation.move
        if board.turn == chess.WHITE:
            key_fen = board.fen()
            move_uci = move.uci()
            new_board = board.copy()
            new_board.push(move)
            child_fen = new_board.fen()
            tree.insert(key_fen, move_uci, child_fen)
            logging.debug(f"White tree: At FEN '{key_fen}', added move '{move_uci}' -> '{child_fen}'")
        board.push(move)
        process_white_node(variation, board, tree)
        board.pop()

def build_white_tree(filename):
    tree = RepertoireTree()
    game_count = 0
    with open(filename, 'r', encoding='latin1') as pgn_file:
        while True:
            game = chess.pgn.read_game(pgn_file)
            if game is None:
                break
            game_count += 1
            board = chess.Board()
            process_white_node(game, board, tree)
    logging.debug(f"White repertoire: Loaded {game_count} games with {len(tree.tree)} unique positions.")
    return tree

def process_black_node(node, board, tree):
    """Recursively traverse a PGN node and record Black's moves."""
    for variation in node.variations:
        move = variation.move
        if board.turn == chess.BLACK:
            key_fen = board.fen()  # board FEN after White's move
            move_uci = move.uci()
            new_board = board.copy()
            new_board.push(move)
            child_fen = new_board.fen()
            tree.insert(key_fen, move_uci, child_fen)
            logging.debug(f"Black tree: At FEN '{key_fen}', added move '{move_uci}' -> '{child_fen}'")
        board.push(move)
        process_black_node(variation, board, tree)
        board.pop()

def build_black_tree(filename):
    tree = RepertoireTree()
    game_count = 0
    with open(filename, 'r', encoding='latin1') as pgn_file:
        while True:
            game = chess.pgn.read_game(pgn_file)
            if game is None:
                break
            game_count += 1
            board = chess.Board()
            process_black_node(game, board, tree)
    logging.debug(f"Black repertoire: Loaded {game_count} games with {len(tree.tree)} unique positions.")
    return tree

##############################
# PHASE 2: Simulate the Opening
##############################
def simulate_game(white_tree, black_tree):
    """
    Simulate a game using the repertoire trees.
    If it's White's turn, look up board.fen() in white_tree; if found, play the first candidate move.
    Similarly for Black.
    """
    board = chess.Board()
    san_sequence = []
    while True:
        current_fen = board.fen()
        if board.turn == chess.WHITE:
            if current_fen in white_tree.tree and white_tree.tree[current_fen]:
                candidate = list(white_tree.tree[current_fen].keys())[0]
                move = chess.Move.from_uci(candidate)
                if move not in board.legal_moves:
                    logging.debug(f"White candidate {candidate} illegal at FEN: {current_fen}")
                    break
                san = board.san(move)
                san_sequence.append(san)
                board.push(move)
                logging.debug(f"White plays {candidate} ({san}); New FEN: {board.fen()}")
            else:
                logging.debug(f"White out-of-book at FEN: {current_fen}")
                break
        else:
            if current_fen in black_tree.tree and black_tree.tree[current_fen]:
                candidate = list(black_tree.tree[current_fen].keys())[0]
                move = chess.Move.from_uci(candidate)
                if move not in board.legal_moves:
                    logging.debug(f"Black candidate {candidate} illegal at FEN: {current_fen}")
                    break
                san = board.san(move)
                san_sequence.append(san)
                board.push(move)
                logging.debug(f"Black plays {candidate} ({san}); New FEN: {board.fen()}")
            else:
                logging.debug(f"Black out-of-book at FEN: {current_fen}")
                break
    logging.debug(f"Final move sequence: {format_san_sequence(san_sequence)}")
    return board, san_sequence

def format_san_sequence(san_seq):
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

##############################
# PHASE 3: Lichess Explorer API Lookup
##############################
def query_lichess(fen, ratings):
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

##############################
# MAIN FUNCTION: PHASES 1, 2, & 3
##############################
def main():
    parser = argparse.ArgumentParser(
        description="Opening Arena: Load repertoires (including variations), simulate game, and query Lichess Explorer API."
    )
    parser.add_argument('-w', '--white', required=True, help="White repertoire PGN file")
    parser.add_argument('-b', '--black', required=True, help="Black repertoire PGN file")
    parser.add_argument('-e', '--elo', required=True,
                        help="Comma separated ELO brackets (e.g. 1200,1400,1600,1800)")
    parser.add_argument('-v', '--verbose', action='store_true',
                        help="Enable verbose debug logging to debug.log")
    args = parser.parse_args()

    setup_logging(args.verbose)

    # Phase 1: Build the repertoire trees.
    logging.debug("Building white repertoire tree...")
    white_tree = build_white_tree(args.white)
    logging.debug("Building black repertoire tree...")
    black_tree = build_black_tree(args.black)

    # Phase 2: Simulate the game.
    board, san_sequence = simulate_game(white_tree, black_tree)
    final_fen = board.fen()
    print("White:", args.white)
    print("Black:", args.black)
    print("Final FEN:", final_fen)

    if san_sequence:
        moves_played = format_san_sequence(san_sequence)
        print("\nMoves played to reach this position:")
        print(moves_played)
        logging.debug(f"Moves played: {moves_played}")
    else:
        print("\nNo moves were played (empty repertoire?)")
        logging.debug("No moves were played.")

    # Phase 3: Query Lichess Explorer API.
    if board.is_checkmate():
        if board.turn == chess.WHITE:
            white_wins, draws, black_wins = 0, 0, 1
        else:
            white_wins, draws, black_wins = 1, 0, 0
        total = 1
        print("\nResult (Mate):")
        print(f"Overall: {white_wins}/{draws}/{black_wins} = {total} = "
              f"{white_wins*100:.1f}%/{draws*100:.1f}%/{black_wins*100:.1f}%")
        logging.debug("Mate reached; simulation ended.")
        print("\n(Mate reached; no candidate moves table available.)")
    else:
        try:
            white_wins, draws, black_wins, total, api_data = query_lichess(final_fen, args.elo.replace(" ", ""))
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
