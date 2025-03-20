#!/usr/bin/env python3
import argparse
import chess
import chess.pgn
import requests

def load_first_game_moves(filename):
    """Load moves from the first game in a PGN file."""
    with open(filename, 'r') as pgn_file:
        game = chess.pgn.read_game(pgn_file)
    if game is None:
        raise ValueError(f"No game found in PGN file: {filename}")
    return list(game.mainline_moves())

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

    # Load the moves from each repertoire file (first game only).
    try:
        white_moves = load_first_game_moves(args.white)
        black_moves = load_first_game_moves(args.black)
    except Exception as ex:
        print("Error loading PGN files:", ex)
        return

    board = chess.Board()
    white_idx = 0
    black_idx = 0

    # Simulate alternating moves until one side is out-of-book.
    while True:
        if board.turn == chess.WHITE:
            if white_idx < len(white_moves):
                move = white_moves[white_idx]
                white_idx += 1
            else:
                break  # White is out of repertoire moves.
        else:
            if black_idx < len(black_moves):
                move = black_moves[black_idx]
                black_idx += 1
            else:
                break  # Black is out of repertoire moves.
        board.push(move)
    
    fen = board.fen()
    print("White:", args.white)
    print("Black:", args.black)
    print("FEN:", fen)

    # Check if the final move delivered mate.
    if board.is_checkmate():
        # board.turn is the side to move (which is checkmated).
        if board.turn == chess.WHITE:
            # White is checkmated; black wins.
            white_wins, draws, black_wins = 0, 0, 1
        else:
            # Black is checkmated; white wins.
            white_wins, draws, black_wins = 1, 0, 0
        total = 1
        perc_white = white_wins * 100.0
        perc_draws = draws * 100.0
        perc_black = black_wins * 100.0
    else:
        # Otherwise, query the Lichess Explorer API.
        ratings = args.elo.replace(" ", "")
        params = {
            "variant": "standard",
            "speeds": "blitz,rapid,classical",
            "ratings": ratings,
            "fen": fen
        }
        api_url = "https://explorer.lichess.ovh/lichess"
        try:
            response = requests.get(api_url, params=params)
            response.raise_for_status()
        except Exception as e:
            print("API request failed:", e)
            return
        data = response.json()
        white_wins = data.get("white", 0)
        draws = data.get("draws", 0)
        black_wins = data.get("black", 0)
        total = white_wins + draws + black_wins

        if total > 0:
            perc_white = white_wins / total * 100
            perc_draws = draws / total * 100
            perc_black = black_wins / total * 100
        else:
            perc_white = perc_draws = perc_black = 0

    # Print the results.
    print(f"Results: {white_wins}/{draws}/{black_wins} = {total} "
          f"= {perc_white:.1f}%/{perc_draws:.1f}%/{perc_black:.1f}%")

if __name__ == '__main__':
    main()
