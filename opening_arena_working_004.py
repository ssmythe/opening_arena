#!/usr/bin/env python3
import argparse
import chess
import chess.pgn
import requests

def load_white_repertoire(filename):
    """
    Load all games from the white repertoire PGN file.
    Each game is treated as one variation (a “line”) and only White’s moves (as UCI strings) are recorded.
    Returns a list of variations (each a list of UCI moves).
    """
    white_lines = []
    with open(filename, 'r') as pgn_file:
        while True:
            game = chess.pgn.read_game(pgn_file)
            if game is None:
                break
            board = chess.Board()
            line = []
            # Record only White's moves.
            for move in game.mainline_moves():
                if board.turn == chess.WHITE:
                    line.append(move.uci())
                board.push(move)
            if line:
                white_lines.append(line)
    if not white_lines:
        raise ValueError(f"No games found in white PGN file: {filename}")
    return white_lines

def load_black_repertoire(filename):
    """
    Load all games from the black repertoire PGN file.
    For each game, record:
      - 'white_moves': the moves played by White (as UCI strings) that trigger Black’s responses.
      - 'black_moves': Black’s planned replies (as UCI strings).
    Returns a list of dictionaries.
    """
    black_lines = []
    with open(filename, 'r') as pgn_file:
        while True:
            game = chess.pgn.read_game(pgn_file)
            if game is None:
                break
            board = chess.Board()
            white_line = []
            black_line = []
            for move in game.mainline_moves():
                if board.turn == chess.WHITE:
                    white_line.append(move.uci())
                else:
                    black_line.append(move.uci())
                board.push(move)
            if white_line or black_line:
                black_lines.append({
                    'white_moves': white_line,
                    'black_moves': black_line
                })
    if not black_lines:
        raise ValueError(f"No games found in black PGN file: {filename}")
    return black_lines

def simulate_opening(white_book, black_book):
    """
    Simulate the opening battle using the two books.
    
    white_book: list of white variations (each a list of UCI moves)
    black_book: list of dicts with keys 'white_moves' and 'black_moves'
    
    On White’s turn:
      - Filter white_book for variations whose prefix matches the moves played so far.
      - If candidate variations exist, pick the next move from the first candidate.
    On Black’s turn:
      - Filter black_book for games whose white_moves prefix matches the played moves.
      - If a candidate game is found and it has a Black reply at that juncture, use that reply.
    
    The simulation stops when one side is out‑of‑book.
    
    Returns a tuple (board, san_sequence) where board is the final chess.Board and
    san_sequence is a list of the moves in SAN order.
    """
    board = chess.Board()
    played_white = []  # White moves played so far (as UCI strings)
    san_sequence = []  # Record moves in SAN as they were played

    # Work on copies of the books that we prune as we progress.
    current_white_book = white_book[:]
    current_black_book = black_book[:]

    while True:
        # WHITE'S TURN:
        white_candidates = []
        for line in current_white_book:
            if len(line) > len(played_white) and line[:len(played_white)] == played_white:
                white_candidates.append(line[len(played_white)])
        if not white_candidates:
            # No White move available – out-of-book.
            break
        white_move_uci = white_candidates[0]  # pick the first candidate
        try:
            move = chess.Move.from_uci(white_move_uci)
        except Exception as e:
            print("Error converting white move:", e)
            break
        if move not in board.legal_moves:
            break
        # Record SAN before pushing.
        san_sequence.append(board.san(move))
        board.push(move)
        played_white.append(white_move_uci)
        # Prune white_book: keep only variations that follow the chosen move.
        current_white_book = [line for line in current_white_book
                              if len(line) > len(played_white) and line[:len(played_white)] == played_white]

        # BLACK'S TURN:
        black_candidates = []
        for game in current_black_book:
            if len(game['white_moves']) >= len(played_white) and game['white_moves'][:len(played_white)] == played_white:
                # Black's reply index is (number of white moves played - 1)
                reply_index = len(played_white) - 1
                if len(game['black_moves']) > reply_index:
                    black_candidates.append(game['black_moves'][reply_index])
        if not black_candidates:
            break  # Black out-of-book.
        black_move_uci = black_candidates[0]
        try:
            move = chess.Move.from_uci(black_move_uci)
        except Exception as e:
            print("Error converting black move:", e)
            break
        if move not in board.legal_moves:
            break
        san_sequence.append(board.san(move))
        board.push(move)
        # Prune black_book to keep only those games that played the chosen Black move.
        current_black_book = [game for game in current_black_book 
                              if len(game['black_moves']) > (len(played_white)-1) and 
                              game['black_moves'][len(played_white)-1] == black_move_uci]
    return board, san_sequence

def format_san_sequence(san_seq):
    """
    Given a list of SAN half-moves, produce a single string with move numbers.
    For example, if san_seq = ['e4', 'e5', 'Nf3', 'Nc6'], then return:
      "1.e4 e5 2.Nf3 Nc6"
    (Note: no space after the move number.)
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
    Given the candidate moves list from the API (each a dict), print a nicely formatted table
    showing for each candidate move its white, draw, and black counts and percentages.
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

def main():
    parser = argparse.ArgumentParser(
        description="Opening Arena: Evaluate opening repertoires via Lichess Explorer API"
    )
    parser.add_argument('-w', '--white', required=True,
                        help="White repertoire PGN file")
    parser.add_argument('-b', '--black', required=True,
                        help="Black repertoire PGN file")
    parser.add_argument('-e', '--elo', required=True,
                        help="Comma separated ELO brackets (e.g. 1200,1400,1600,1800)")
    args = parser.parse_args()

    try:
        white_book = load_white_repertoire(args.white)
        black_book = load_black_repertoire(args.black)
    except Exception as ex:
        print("Error loading PGN files:", ex)
        return

    board, san_sequence = simulate_opening(white_book, black_book)
    fen = board.fen()
    print("White:", args.white)
    print("Black:", args.black)
    print("FEN:", fen)

    if san_sequence:
        print("\nMoves played to reach this position:")
        print(format_san_sequence(san_sequence))
    else:
        print("\nNo moves were played (empty book?)")

    # If the final move delivered mate, force the stats.
    if board.is_checkmate():
        if board.turn == chess.WHITE:
            # White is to move but is mated: Black delivered mate.
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
            white_wins, draws, black_wins, total, api_data = query_lichess(
                fen, args.elo.replace(" ", ""))
        except Exception as e:
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

        moves = api_data.get("moves", [])
        if moves:
            print_moves_table(moves)
        else:
            print("No candidate moves available in the API response.")

if __name__ == '__main__':
    main()
