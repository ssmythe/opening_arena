#!/bin/bash
set -e

# Define white repertoire files (Colle System and London)
WHITE_REPERTOIRES=(
  "lichess_study_chessimple-colle-system_chessimple-colle-system-annotated_by_ComBinaural_2025.01.06.pgn"
  "chessgoalslondon20230422-230422-215609.pgn"
)

# Define black repertoire files (French, Sicilian, QGD Main Course, DynamicSlav)
BLACK_REPERTOIRES=(
  "ChessGoals_French_20231018.pgn"
  "ChessGoalsSicilian20230803-230803-073014.pgn"
  "QGD Main Course - V3.pgn"
  "DynamicSlav_Chessable-220629-175801.pgn"
)

# Elo brackets to use
ELO="1200,1400,1600,1800"

# Loop over each white and black file combination
for white in "${WHITE_REPERTOIRES[@]}"; do
  for black in "${BLACK_REPERTOIRES[@]}"; do
    echo "===================================="
    echo "Match: ${white} (White) vs. ${black} (Black)"
    echo "------------------------------------"
    ./opening_arena.py -w "$white" -b "$black" -e "$ELO" -v
    echo "===================================="
    echo ""
  done
done
