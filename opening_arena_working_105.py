#!/usr/bin/env python3
import argparse
import chess
import chess.pgn
import requests
import logging
import sys

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
        # tree maps a FEN string to a dictionary of moves (in UCI) and resulting child FENs.
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
            try:
                new_board.push(move)
            except Exception as e:
                logging.error("Error pushing white move %s at FEN %s: %s", move_uci, board.fen(), e)
                continue
            child_fen = new_board.fen()
            tree.insert(key_fen, move_uci, child_fen)
            logging.debug("White tree: At FEN '%s', added move '%s' -> '%s'", key_fen, move_uci, child_fen)
        board.push(move)
        process_white_node(variation, board, tree)
        board.pop()

def build_white_tree(filename):
    tree = RepertoireTree()
    game_count = 0
    # Use UTF-8 with errors replaced.
    with open(filename, 'r', encoding='utf-8', errors='replace') as pgn_file:
        while True:
            game = chess.pgn.read_game(pgn_file)
            if game is None:
                break
            game_count += 1
            board = chess.Board()
            process_white_node(game, board, tree)
    logging.debug("White repertoire: Loaded %d games with %d unique positions.", game_count, len(tree.tree))
    return tree

def process_black_node(node, board, tree):
    """
    Recursively traverse a PGN game node (and its variations) for Black's moves.
    Before pushing a move, check that it is legal. If not, log and skip that variation.
    """
    for variation in node.variations:
        move = variation.move
        if board.turn == chess.BLACK:
            key_fen = board.fen()  # FEN after White's move
            move_uci = move.uci()
            new_board = board.copy()
            if move in new_board.legal_moves:
                try:
                    new_board.push(move)
                except Exception as e:
                    logging.error("Error pushing black move %s at FEN %s: %s", move_uci, board.fen(), e)
                    continue
                child_fen = new_board.fen()
                tree.insert(key_fen, move_uci, child_fen)
                logging.debug("Black tree: At FEN '%s', added move '%s' -> '%s'", key_fen, move_uci, child_fen)
            else:
                logging.debug("Skipping illegal black move %s at FEN %s", move_uci, board.fen())
                continue
        try:
            board.push(move)
        except AssertionError as e:
            logging.debug("Skipping illegal move %s at FEN %s: %s", move.uci(), board.fen(), e)
            continue
        process_black_node(variation, board, tree)
        board.pop()

def build_black_tree(filename):
    tree = RepertoireTree()
    game_count = 0
    with open(filename, 'r', encoding='utf-8', errors='replace') as pgn_file:
        while True:
            game = chess.pgn.read_game(pgn_file)
            if game is None:
                break
            game_count += 1
            board = chess.Board()
            process_black_node(game, board, tree)
    logging.debug("Black repertoire: Loaded %d games with %d unique positions.", game_count, len(tree.tree))
    return tree

##############################
# PHASE 2: Simulate the Opening
##############################
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

def simulate_game(white_tree, black_tree):
    """
    Simulate a game using the repertoire trees.
    If it’s White’s turn, look up board.fen() in white_tree; if found, play the first candidate move.
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
                    logging.debug("White candidate %s illegal at FEN: %s", candidate, current_fen)
                    break
                san = board.san(move)
                san_sequence.append(san)
                board.push(move)
                logging.debug("White plays %s (%s); New FEN: %s", candidate, san, board.fen())
            else:
                logging.debug("White out-of-book at FEN: %s", current_fen)
                break
        else:
            if current_fen in black_tree.tree and black_tree.tree[current_fen]:
                candidate = list(black_tree.tree[current_fen].keys())[0]
                move = chess.Move.from_uci(candidate)
                if move not in board.legal_moves:
                    logging.debug("Black candidate %s illegal at FEN: %s", candidate, current_fen)
                    break
                san = board.san(move)
                san_sequence.append(san)
                board.push(move)
                logging.debug("Black plays %s (%s); New FEN: %s", candidate, san, board.fen())
            else:
                logging.debug("Black out-of-book at FEN: %s", current_fen)
                break
    logging.debug("Final move sequence: %s", format_san_sequence(san_sequence))
    return board, san_sequence

##############################
# PHASE 3: Lichess Explorer API Lookup & Results Display
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

def print_moves_table(moves, current_move_number, is_white_turn):
    header = f"{'Move':<12}{'White':>10}{'Draws':>10}{'Black':>10}{'Total':>10} {'W%':>8} {'D%':>8} {'B%':>8}"
    print("\nCandidate Moves:")
    print(header)
    print("-" * len(header))
    for m in moves:
        # Get the candidate move (assume API returns UCI or SAN; here we convert spaces after period)
        move_raw = m.get("san", m.get("uci", "")).replace(". ", ".")
        # Prepend with move number
        if is_white_turn:
            move_str = f"{current_move_number}.{move_raw}"
        else:
            move_str = f"{current_move_number}...{move_raw}"
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
        print(f"{move_str:<12}{w:10d}{d:10d}{b:10d}{tot:10d} {wp:7.1f}% {dp:7.1f}% {bp:7.1f}%")

def print_results(final_fen, moves_played, candidate_moves, board):
    print("White:", args.white)
    print("Black:", args.black)
    print("Final FEN:", final_fen)
    print("\nMoves played to reach this position:")
    if moves_played:
        print(format_san_sequence(moves_played))
    else:
        print("(No moves played)")
    if board.is_checkmate():
        if board.turn == chess.WHITE:
            white_wins, draws, black_wins = 0, 0, 1
        else:
            white_wins, draws, black_wins = 1, 0, 0
        total = 1
        print("\nResult (Mate):")
        print(f"Overall: {white_wins}/{draws}/{black_wins} = {total} = "
              f"{white_wins*100:.1f}%/{draws*100:.1f}%/{black_wins*100:.1f}%")
        print("\n(Mate reached; no candidate moves table available.)")
    else:
        try:
            white_wins, draws, black_wins, total, api_data = query_lichess(final_fen, args.elo.replace(" ", ""))
        except Exception as e:
            logging.debug("API request failed: %s", e)
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
        candidate_moves = api_data.get("moves", [])
        if candidate_moves:
            # Get current move number and whose turn from the final board state.
            current_move_number = board.fullmove_number
            is_white_turn = board.turn == chess.WHITE
            print_moves_table(candidate_moves, current_move_number, is_white_turn)
            logging.debug("Candidate moves table printed.")
        else:
            print("No candidate moves available in the API response.")
            logging.debug("No candidate moves available from API.")

##############################
# MAIN FUNCTION: PHASES 1, 2, & 3
##############################
def main():
    global args  # so that print_results() can use args.white and args.black
    parser = argparse.ArgumentParser(
        description="Opening Arena: Load repertoires (with variations), simulate a game, and query Lichess Explorer API."
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

    # Print basic game info
    print("White:", args.white)
    print("Black:", args.black)
    print("Final FEN:", final_fen)

    print("\nMoves played to reach this position:")
    if san_sequence:
        print(format_san_sequence(san_sequence))
        logging.debug("Moves played: %s", format_san_sequence(san_sequence))
    else:
        print("(No moves played)")
        logging.debug("No moves were played.")

    # Phase 3: Query Lichess Explorer API or print mate result.
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
            logging.debug("API request failed: %s", e)
            print("API request failed:", e)
            sys.exit(1)
        if total > 0:
            overall_wp = white_wins / total * 100
            overall_dp = draws / total * 100
            overall_bp = black_wins / total * 100
        else:
            overall_wp = overall_dp = overall_bp = 0
        print("\nOverall Result from Lichess Explorer:")
        print(f"Overall: {white_wins}/{draws}/{black_wins} = {total} = "
              f"{overall_wp:.1f}%/{overall_dp:.1f}%/{overall_bp:.1f}%")
        logging.debug("Overall API result: %d/%d/%d = %d", white_wins, draws, black_wins, total)
        moves = api_data.get("moves", [])
        if moves:
            # Get current move number and turn from the board.
            current_move_number = board.fullmove_number
            is_white_turn = board.turn == chess.WHITE
            print_moves_table(moves, current_move_number, is_white_turn)
            logging.debug("Candidate moves table printed.")
        else:
            print("No candidate moves available in the API response.")
            logging.debug("No candidate moves available from API.")

if __name__ == '__main__':
    main()
