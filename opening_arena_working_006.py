#!/usr/bin/env python3
import argparse
import chess
import chess.pgn
import requests
import logging

def setup_logging(verbose):
    if verbose:
        logging.basicConfig(filename="debug.log",
                            level=logging.DEBUG,
                            format="%(asctime)s - %(levelname)s - %(message)s")
        logging.debug("Debug logging enabled.")
    else:
        logging.basicConfig(level=logging.WARNING)

def load_white_repertoire(filename):
    white_lines = []
    with open(filename, 'r') as pgn_file:
        while True:
            game = chess.pgn.read_game(pgn_file)
            if game is None:
                break
            board = chess.Board()
            line = []
            for move in game.mainline_moves():
                if board.turn == chess.WHITE:
                    line.append(move.uci())
                board.push(move)
            if line:
                white_lines.append(line)
            logging.debug(f"Loaded white line: {line}")
    if not white_lines:
        raise ValueError(f"No games found in white PGN file: {filename}")
    logging.debug(f"Total white variations loaded: {len(white_lines)}")
    return white_lines

def load_black_repertoire(filename):
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
            logging.debug(f"Loaded black game: white_moves={white_line}, black_moves={black_line}")
    if not black_lines:
        raise ValueError(f"No games found in black PGN file: {filename}")
    logging.debug(f"Total black games loaded: {len(black_lines)}")
    return black_lines

def simulate_opening(white_book, black_book):
    board = chess.Board()
    played_white = []  # white moves played so far (as UCI strings)
    san_sequence = []  # moves recorded in SAN

    current_white_book = white_book[:]
    current_black_book = black_book[:]

    move_count = 0
    while True:
        move_count += 1
        # WHITE'S TURN:
        white_candidates = []
        for variation in current_white_book:
            if len(variation) > len(played_white) and variation[:len(played_white)] == played_white:
                white_candidates.append(variation[len(played_white)])
        logging.debug(f"After {move_count-1} full moves, White candidates: {white_candidates}")
        if not white_candidates:
            logging.debug("White is out-of-book.")
            break

        # Try all white candidates until one is legal.
        white_move_uci = None
        for candidate in white_candidates:
            try:
                move = chess.Move.from_uci(candidate)
            except Exception as e:
                logging.debug(f"Error converting white candidate {candidate}: {e}")
                continue
            if move in board.legal_moves:
                white_move_uci = candidate
                break
            else:
                logging.debug(f"Candidate white move {candidate} is illegal in current position.")
        if white_move_uci is None:
            logging.debug("No legal white candidate move found; White is out-of-book.")
            break
        move = chess.Move.from_uci(white_move_uci)
        san = board.san(move)
        san_sequence.append(san)
        board.push(move)
        played_white.append(white_move_uci)
        logging.debug(f"White plays {white_move_uci} ({san}); Board FEN: {board.fen()}")
        before = len(current_white_book)
        current_white_book = [variation for variation in current_white_book
                              if len(variation) > len(played_white) and variation[:len(played_white)] == played_white]
        logging.debug(f"Pruned white_book from {before} to {len(current_white_book)} variations.")

        # BLACK'S TURN:
        black_candidates = []
        for game in current_black_book:
            if len(game['white_moves']) >= len(played_white) and game['white_moves'][:len(played_white)] == played_white:
                reply_index = len(played_white) - 1
                if len(game['black_moves']) > reply_index:
                    black_candidates.append(game['black_moves'][reply_index])
        logging.debug(f"After {move_count} full moves, Black candidates: {black_candidates}")
        if not black_candidates:
            logging.debug("Black is out-of-book.")
            break

        # Try all black candidates until one is legal.
        black_move_uci = None
        for candidate in black_candidates:
            try:
                move = chess.Move.from_uci(candidate)
            except Exception as e:
                logging.debug(f"Error converting black candidate {candidate}: {e}")
                continue
            if move in board.legal_moves:
                black_move_uci = candidate
                break
            else:
                logging.debug(f"Candidate black move {candidate} is illegal in current position.")
        if black_move_uci is None:
            logging.debug("No legal black candidate move found; Black is out-of-book.")
            break
        move = chess.Move.from_uci(black_move_uci)
        san = board.san(move)
        san_sequence.append(san)
        board.push(move)
        logging.debug(f"Black plays {black_move_uci} ({san}); Board FEN: {board.fen()}")
        before = len(current_black_book)
        current_black_book = [game for game in current_black_book 
                              if len(game['black_moves']) > (len(played_white)-1) and 
                              game['black_moves'][len(played_white)-1] == black_move_uci]
        logging.debug(f"Pruned black_book from {before} to {len(current_black_book)} games.")
    logging.debug(f"Moves played: {format_san_sequence(san_sequence)}")
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
    logging.debug("Starting Opening Arena simulation.")

    try:
        white_book = load_white_repertoire(args.white)
        black_book = load_black_repertoire(args.black)
    except Exception as ex:
        logging.debug(f"Error loading PGN files: {ex}")
        print("Error loading PGN files:", ex)
        return

    board, san_sequence = simulate_opening(white_book, black_book)
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
