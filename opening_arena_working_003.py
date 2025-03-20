#!/usr/bin/env python3
import argparse
import chess
import chess.pgn
import requests

def load_white_repertoire(filename):
    """
    Load the first game from the white repertoire file.
    Return its moves as a list of chess.Move objects.
    """
    with open(filename, 'r') as pgn_file:
        game = chess.pgn.read_game(pgn_file)
    if game is None:
        raise ValueError(f"No game found in PGN file: {filename}")
    board = chess.Board()
    white_moves = []
    for move in game.mainline_moves():
        if board.turn == chess.WHITE:
            white_moves.append(move)
        board.push(move)
    return white_moves

def load_black_repertoire(filename):
    """
    Load all games from the black repertoire file.
    For each game record the white moves and black moves as lists of UCI strings.
    Returns a list of dictionaries, each with keys 'white_moves' and 'black_moves'.
    """
    games = []
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
            games.append({'white_moves': white_line, 'black_moves': black_line})
    if not games:
        raise ValueError(f"No games found in PGN file: {filename}")
    return games

def simulate_opening(white_moves, black_games):
    """
    Simulate the opening battle:
      - white_moves: list of chess.Move objects (from white repertoire)
      - black_games: list of dicts from the black repertoire
    On each turn:
      * White plays the next white move from white_moves.
      * Black looks for the first game in black_games where the white moves played so far match
        that game's white_moves prefix. If found and a black move exists, that move is played.
    Stops when one side is out-of-book.
    Returns the final board.
    """
    board = chess.Board()
    white_index = 0
    black_index = 0  # index for black move in the candidate game
    played_white_moves = []  # record white moves in UCI to match against black games

    while True:
        if board.turn == chess.WHITE:
            if white_index < len(white_moves):
                move = white_moves[white_index]
                white_index += 1
                played_white_moves.append(move.uci())
                board.push(move)
            else:
                break  # White out-of-book
        else:  # Black's turn
            candidate = None
            for game in black_games:
                # Only consider candidate if game has at least as many white moves as played so far
                if len(game['white_moves']) >= len(played_white_moves):
                    if game['white_moves'][:len(played_white_moves)] == played_white_moves:
                        candidate = game
                        break
            if candidate is None:
                break  # No matching black repertoire move found
            if black_index < len(candidate['black_moves']):
                move_uci = candidate['black_moves'][black_index]
                try:
                    move = chess.Move.from_uci(move_uci)
                except Exception as e:
                    print("Error converting move:", e)
                    break
                if move not in board.legal_moves:
                    break  # Illegal move found
                black_index += 1
                board.push(move)
            else:
                break  # Candidate game does not provide further black moves

    return board

def query_lichess(fen, ratings):
    """
    Query the Lichess Explorer API with the given FEN and ratings.
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
    Given a list of move candidate dictionaries from the API,
    print a nicely formatted table showing each move's counts and percentages.
    """
    header = (f"{'Move':<12} {'White':>10} {'Draws':>10} {'Black':>10} {'Total':>10} "
              f"{'W%':>8} {'D%':>8} {'B%':>8}")
    print("\nCandidate Moves:")
    print(header)
    print("-" * len(header))
    for m in moves:
        # Use SAN if available; otherwise use UCI.
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
        # Load white repertoire (first game) and all black repertoire games.
        white_moves = load_white_repertoire(args.white)
        black_games = load_black_repertoire(args.black)
    except Exception as ex:
        print("Error loading PGN files:", ex)
        return

    # Simulate the opening battle.
    board = simulate_opening(white_moves, black_games)
    fen = board.fen()
    print("White:", args.white)
    print("Black:", args.black)
    print("FEN:", fen)

    # If the position is mate, force result to 100% for the winning side.
    if board.is_checkmate():
        if board.turn == chess.WHITE:
            # White to move but is mated; Black wins.
            white_wins, draws, black_wins = 0, 0, 1
        else:
            white_wins, draws, black_wins = 1, 0, 0
        total = 1
        print("\nResult (Mate):")
        print(f"Overall: {white_wins}/{draws}/{black_wins} = {total} "
              f"= {white_wins*100:.1f}%/{draws*100:.1f}%/{black_wins*100:.1f}%")
        print("\n(Mate reached; no candidate moves table available.)")
    else:
        try:
            white_wins, draws, black_wins, total, api_data = query_lichess(fen, args.elo.replace(" ", ""))
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
        print(f"Overall: {white_wins}/{draws}/{black_wins} = {total} "
              f"= {overall_wp:.1f}%/{overall_dp:.1f}%/{overall_bp:.1f}%")

        # Print a table for each candidate move from the API.
        moves = api_data.get("moves", [])
        if moves:
            print_moves_table(moves)
        else:
            print("No candidate moves available in the API response.")

if __name__ == '__main__':
    main()
