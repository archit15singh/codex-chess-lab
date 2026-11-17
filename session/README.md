# One Duolingo chess game

## Result

White won by checkmate on move 42 in Duolingo Chess Web’s **Anyone** mode in Brave. The pairing screen showed **585 Elo** before play. Chess Matches showed **597 Elo** afterward and marked the new match as a **Win**. Both clocks started at 10 minutes. The checkmate screen showed 3:24 for White and 5:30 for Black.

The session used the requested public matchmaking route under the user’s recorded attestation for platform permission and participant consent. The browser verified the route and result. The matched player’s identity and consent provenance remain private.

## Move record

Reconstructed from the visible boards and checked by replaying the notation for legality and checkmate after the game.

```pgn
1. e4 e5 2. Nf3 Bc5 3. Nxe5 Qh4 4. d4 Bb6 5. Nc3 c5
6. g3 Qf6 7. Nd5 Qe6 8. Nxb6 axb6 9. Bc4 Qd6 10. Nxf7 cxd4
11. Nxd6+ Ke7 12. Nxc8+ Kd8 13. Nxb6 Ra5 14. O-O Nc6
15. Bf4 Nf6 16. Qd2 Nxe4 17. Qd3 Re8 18. Rae1 Nb4
19. Qxd4 Nxc2 20. Qd5 Rxd5 21. Bxd5 Nxf2 22. Rxe8+ Kxe8
23. Rxf2 Nb4 24. Bxb7 Nd3 25. Rf3 Ne1 26. Re3+ Kd8
27. Rxe1 d5 28. Re5 d4 29. Rd5+ Ke7 30. Rxd4 Kf6
31. a4 Kf5 32. a5 h5 33. a6 h4 34. a7 hxg3 35. a8=Q Kg4
36. Bxg3+ Kh5 37. Qh8+ Kg6 38. Rg4+ Kf5 39. Qxg7 Ke6
40. Qg6+ Ke7 41. Re4+ Kf8 42. Re8# 1-0
```

## Process and lessons

- The earlier attempt expired before a move landed, after about 99 seconds between the opening-board capture and the attempted input. In this match, the first move landed with 9:52 on White’s clock. Native Brave controls and private screenshot capture were prepared before matchmaking. The same session chose moves from screenshots, clicked the two squares, and read the resulting board. It used no engine or outside move advice during play.
- White won the queen with the f7 fork, then gave its own queen up for a rook on move 20 by overlooking the rook’s open line from a5 to d5. Before committing a queen move, trace opposing rook, bishop, and queen lines through the destination square. Test that check on unseen positions before treating it as a validated strategy improvement.
- An attempted rook capture during Black’s `25...Ne1` transition left White’s rook on f3. A fresh screenshot showed the knight on e1, and White played `26.Re3+`. Verify the active clock and the completed piece animation before clicking when the board is in transition.
- White removed the remaining pieces, promoted the passed a-pawn, and used the queen to support `42.Re8#`. This single result measures one game and an account rating change.

Raw screenshots, action logs, and the prior failure record remain private.
