#!/bin/bash
# test_opening_arena.sh

echo "===================================="
echo "Test 1: Scholar's Mate Unopposed"
echo "------------------------------------"
./opening_arena.py -w white_scholars_mate.pgn -b black_scholars_mate.pgn -e 1200,1400,1600,1800 -v
echo "===================================="
echo ""

echo "===================================="
echo "Test 2: Scholar's Mate Defended by Black"
echo "------------------------------------"
./opening_arena.py -w white_scholars_mate.pgn -b black_defend_scholars_mate.pgn -e 1200,1400,1600,1800 -v
echo "===================================="
echo ""

echo "===================================="
echo "Test 3: Extended Game (No Mate)"
echo "------------------------------------"
./opening_arena.py -w white_extended.pgn -b black_extended.pgn -e 1200,1400,1600,1800 -v
echo "===================================="
echo ""

echo "===================================="
echo "Test 4: Incomplete Repertoire"
echo "------------------------------------"
./opening_arena.py -w white_incomplete.pgn -b black_incomplete.pgn -e 1200,1400,1600,1800 -v
echo "===================================="
echo ""

echo "===================================="
echo "Test 5: Fool's Mate Unopposed"
echo "------------------------------------"
./opening_arena.py -w white_fools_mate.pgn -b black_fools_mate.pgn -e 1200,1400,1600,1800 -v
echo "===================================="
echo ""

echo "===================================="
echo "Test 6: Fool's Mate Defended by White"
echo "------------------------------------"
./opening_arena.py -w white_defend_fools_mate.pgn -b black_fools_mate.pgn -e 1200,1400,1600,1800 -v
echo "===================================="
echo ""
