#!/usr/bin/env python3
import argparse
import chess
import chess.pgn
import logging

def setup_logging(verbose):
    if verbose:
        logging.basicConfig(filename="debug.log",
                            level=logging.DEBUG,
                            format="%(asctime)s - %(levelname)s - %(message)s")
        logging.debug("Debug logging enabled.")
    else:
        logging.basicConfig(level=logging.WARNING)

def build_white_tree(filename):
    """
    Build a trie (nested dictionary) from the white repertoire PGN file.
    
    For each game, starting from the initial board:
      - When it’s White’s turn, record the board state (FEN) as a key.
      - Save White’s move (as UCI) as a branch, with the child being the new board FEN.
    
    Returns a dictionary representing the tree.
    """
    tree = {}  # tree: { fen: { white_move: child_fen, ... }, ... }
    with open(filename, 'r') as pgn_file:
        game_count = 0
        while True:
            game = chess.pgn.read_game(pgn_file)
            if game is None:
                break
            game_count += 1
            board = chess.Board()
            for move in game.mainline_moves():
                if board.turn == chess.WHITE:
                    fen = board.fen()
                    white_move = move.uci()
                    new_board = board.copy()
                    new_board.push(move)
                    child_fen = new_board.fen()
                    if fen not in tree:
                        tree[fen] = {}
                    # If the same move appears in different games, we simply record the resulting FEN
                    if white_move not in tree[fen]:
                        tree[fen][white_move] = child_fen
                    logging.debug(f"White tree: At FEN '{fen}', added move '{white_move}' -> '{child_fen}'")
                board.push(move)
        logging.debug(f"White repertoire: Loaded {game_count} games with {len(tree)} unique positions.")
    return tree

def build_black_tree(filename):
    """
    Build a trie (nested dictionary) from the black repertoire PGN file.
    
    For each game, starting from the initial board:
      - Play White’s move (to update the board) and then, when it’s Black’s turn, 
        record the board state (FEN) after White’s move as a key.
      - Save Black’s move (as UCI) as the branch, with the child being the new board FEN.
    
    Returns a dictionary representing the tree.
    """
    tree = {}  # tree: { fen: { black_move: child_fen, ... }, ... }
    with open(filename, 'r') as pgn_file:
        game_count = 0
        while True:
            game = chess.pgn.read_game(pgn_file)
            if game is None:
                break
            game_count += 1
            board = chess.Board()
            for move in game.mainline_moves():
                if board.turn == chess.WHITE:
                    board.push(move)
                else:  # Black's turn: record the board state (after White's move) as key.
                    fen = board.fen()
                    black_move = move.uci()
                    new_board = board.copy()
                    new_board.push(move)
                    child_fen = new_board.fen()
                    if fen not in tree:
                        tree[fen] = {}
                    if black_move not in tree[fen]:
                        tree[fen][black_move] = child_fen
                    logging.debug(f"Black tree: At FEN '{fen}', added move '{black_move}' -> '{child_fen}'")
                    board.push(move)
        logging.debug(f"Black repertoire: Loaded {game_count} games with {len(tree)} unique positions.")
    return tree

def main():
    parser = argparse.ArgumentParser(
        description="Phase 1: Load repertoires into tries keyed by board FEN."
    )
    parser.add_argument('-w', '--white', required=True, help="White repertoire PGN file")
    parser.add_argument('-b', '--black', required=True, help="Black repertoire PGN file")
    parser.add_argument('-v', '--verbose', action='store_true', help="Enable verbose debug logging to debug.log")
    args = parser.parse_args()

    setup_logging(args.verbose)

    logging.debug("Building white repertoire tree...")
    white_tree = build_white_tree(args.white)
    logging.debug("Building black repertoire tree...")
    black_tree = build_black_tree(args.black)

    # For demonstration, print out summary info
    print("White repertoire tree:")
    print(f"Total starting positions (keys): {len(white_tree)}")
    for fen, moves in list(white_tree.items())[:5]:
        print(f"FEN: {fen}")
        for move, child in moves.items():
            print(f"  Move: {move} -> Child FEN: {child}")
    print("\nBlack repertoire tree:")
    print(f"Total starting positions (keys): {len(black_tree)}")
    for fen, moves in list(black_tree.items())[:5]:
        print(f"FEN: {fen}")
        for move, child in moves.items():
            print(f"  Move: {move} -> Child FEN: {child}")

if __name__ == '__main__':
    main()
