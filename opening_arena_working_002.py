#!/usr/bin/env python3
import argparse
import chess
import chess.pgn
import requests

def load_white_repertoire(filename):
    """
    Load the first game from the white repertoire file.
    Returns a list of white moves (as chess.Move objects) for that game.
    """
    with open(filename, 'r') as pgn_file:
        game = chess.pgn.read_game(pgn_file)
    if game is None:
        raise ValueError(f"No game found in PGN file: {filename}")
    board = chess.Board()
    white_moves = []
    for move in game.mainline_moves():
        # Record move if it's White's move.
        if board.turn == chess.WHITE:
            white_moves.append(move)
        board.push(move)
    return white_moves

def load_black_repertoire(filename):
    """
    Load all games from the black repertoire file.
    For each game, record the moves made by White and by Black
    (each as a list of UCI strings).
    Returns a list of dictionaries with keys: 'white_moves' and 'black_moves'.
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
            games.append({
                'white_moves': white_line,
                'black_moves': black_line
            })
    if not games:
        raise ValueError(f"No games found in PGN file: {filename}")
    return games

def simulate_opening(white_moves, black_games):
    """
    Simulate an opening battle:
      - white_moves: list of chess.Move objects (from white repertoire's first game)
      - black_games: list of dictionaries (each with keys 'white_moves' and 'black_moves')
    The simulation proceeds as follows:
      1. Start with an empty board.
      2. On White's turn, play the next move from white_moves if available.
      3. On Black's turn, search black_games for a candidate game where the
         white moves played so far (as UCI strings) match the candidate's white_moves prefix.
         If found and if a black move is available in that candidate, play it.
      4. Stop as soon as one side is "out-of-book".
    Returns the final board position.
    """
    board = chess.Board()
    white_index = 0
    black_index = 0  # counts black moves played in the simulation
    # We'll record the white moves played (as UCI strings) to match against black games.
    played_white_moves = []

    while True:
        if board.turn == chess.WHITE:
            # White's move comes from the white repertoire (first game)
            if white_index < len(white_moves):
                move = white_moves[white_index]
                white_index += 1
                played_white_moves.append(move.uci())
                board.push(move)
            else:
                # White is out-of-book.
                break
        else:  # Black's turn.
            # Look for a black game candidate whose white_moves prefix matches what White has played.
            candidate = None
            for game in black_games:
                # To have a candidate, the game must have at least as many white moves as played.
                if len(game['white_moves']) >= len(played_white_moves):
                    if game['white_moves'][:len(played_white_moves)] == played_white_moves:
                        candidate = game
                        break
            if candidate is None:
                # No matching black repertoire available.
                break
            # Determine the next black move index.
            if black_index < len(candidate['black_moves']):
                # Get the candidate black move as UCI and convert it back to a Move object.
                move_uci = candidate['black_moves'][black_index]
                try:
                    move = chess.Move.from_uci(move_uci)
                except Exception as e:
                    print("Error converting move:", e)
                    break
                # Verify that the move is legal in the current board.
                if move not in board.legal_moves:
                    # If it isn't legal, break out.
                    break
                black_index += 1
                board.push(move)
            else:
                # Candidate does not provide a move; black is out-of-book.
                break

    return board

def query_lichess(fen, ratings):
    """
    Given a FEN and ratings string, query the Lichess Explorer API.
    Returns a tuple (white_wins, draws, black_wins, total).
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
    return white_wins, draws, black_wins, total

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
        # Load white moves (first game only) and all black games.
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

    # If the last move delivered mate, force the stats.
    if board.is_checkmate():
        # board.turn is the side to move (who is checkmated).
        if board.turn == chess.WHITE:
            # White is checkmated; Black wins.
            white_wins, draws, black_wins = 0, 0, 1
        else:
            # Black is checkmated; White wins.
            white_wins, draws, black_wins = 1, 0, 0
        total = 1
    else:
        # Otherwise, query the Lichess Explorer API.
        try:
            white_wins, draws, black_wins, total = query_lichess(fen, args.elo.replace(" ", ""))
        except Exception as e:
            print("API request failed:", e)
            return

    # Calculate percentages.
    if total > 0:
        perc_white = white_wins / total * 100
        perc_draws = draws / total * 100
        perc_black = black_wins / total * 100
    else:
        perc_white = perc_draws = perc_black = 0

    print(f"Results: {white_wins}/{draws}/{black_wins} = {total} "
          f"= {perc_white:.1f}%/{perc_draws:.1f}%/{perc_black:.1f}%")

if __name__ == '__main__':
    main()
