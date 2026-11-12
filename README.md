# optcg-sealed-sim

A simulation engine for One Piece TCG prerelease (sealed) events. Bots open packs, build
40-card decks, and play each other to measure which cards in a set perform best.

It is not a playable game. There is no interface and no human player: games run
headless between bots, are reproducible from a seed, and produce data for analysis.

The target set is OP-18 once it appears in the official card list. Until then the engine
runs on OP-17, which has the same data format and rarity distribution.

## Quick start

Requires Python 3.12+.

```bash
make setup                         # create .venv and install
make cards SET=OP-17               # download a set into data/cards/
make test
make pool SEED=4                   # open one sealed pool and show the deck built from it
make sealed GAMES=1000             # games between freshly opened sealed decks
make sim GAMES=1000 P0=heuristic P1=random   # games between two random decks
make show                          # print one game's log, for checking the rules
```

## Sealed pools

`config/pack_model.toml` describes the product: cards per pack, the rarity of each pack
slot, SuperRares per box and SecretRares per case. Hits are scheduled per box, as in real
product, and each player's 6 packs come consecutively from one box. Bandai publishes no
pull rates, so the numbers are assumptions you can change.

The deckbuilder picks a leader from the pool (or a fallback event leader) and 40 cards,
ranked by printed stats with a minimum of cheap plays and a cap on expensive ones. Card
values can be passed in to replace the stat-based ranking.

## How it works

The engine is a state machine. `legal_actions(state)` lists the moves available to the
player who must decide, and `apply(state, action)` advances the game. Bots only ever pick
from that list, which keeps the rules in one place and lets search-based bots copy the
state and explore possible futures.

```
src/optcg/
  cards.py          card definitions and keyword parsing
  loader.py         card data from punk-records -> data/cards/<SET>.json
  packs.py          pack model and case -> box -> pack opening
  deckbuilder.py    sealed deckbuilding
  engine/
    state.py        game state (copyable for search)
    actions.py      the actions bots choose between
    game.py         rules: setup, legal_actions(), apply()
  agents/           bots: random, heuristic
  sim.py            run games and matches
  cli.py            `optcg cards | sim | show | pool | sealed`
config/             pack model
tests/              rules, loader, pack and deckbuilder tests
```

### Rules supported

Mulligan, life setup, the full turn structure (including going-first rules), playing
Characters with the 5-Character limit, DON!! attachment, attacks, blocking, counters,
K.O.s, life damage, Rush, Double Attack, Banish, and win/loss by life or deck-out.
Card effect text (On Play, Triggers, Events, Stages) is not simulated yet.

## Data

Card data comes from [punk-records](https://github.com/buhbbl/punk-records), which is
generated from the official card list. Alt-art printings are merged with their base card,
since they play identically.

## Disclaimer

This is an unofficial fan project and is not affiliated with or endorsed by Bandai or
Eiichiro Oda. One Piece and the One Piece Card Game are trademarks of their respective
owners.
