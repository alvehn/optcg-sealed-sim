# optcg-sealed-sim

A simulation engine for One Piece TCG prerelease (sealed) events. Bots open packs, build
40-card decks, and play each other to measure which cards in a set perform best.

It is not a playable game. There is no interface and no human player: games run
headless between bots, are reproducible from a seed, and produce data for analysis.

The target set is OP-18 (THE DOMINANCE OF GOD) and its store release event. The plan and
progress are in [docs/PLAN.md](docs/PLAN.md).

## Quick start

Requires Python 3.12+.

```bash
make setup                         # create .venv and install
make fetch                         # clone punk-records into data/raw (optional; else GitHub)
make cards SET=OP-18               # build data/cards/OP-18.json
make test
make pool SEED=4                   # open one sealed pool and show the deck built from it
make pools EVENTS=1000             # pool statistics + per-card pool rates CSV
make sealed GAMES=1000             # games between freshly opened sealed decks
make sim GAMES=1000 P0=heuristic P1=random   # games between two random decks
make show                          # print one game's log, for checking the rules
```

## The event

Every simulated player uses the 4th Anniversary event Luffy (`data/leaders/event_luffy.json`):
5 life, 5000 power, treated as having every card name, type and attribute, and not a
Character. Leaders opened in packs are never played. The event format (16–32 players, Swiss,
best-of-1, the undefeated player wins) is in `config/event.toml`.

## Sealed pools

`config/pack_model.toml` describes the product: the rarity of each pack slot, SuperRares per
box, and per-case counts of SecretRares, alt arts, SPs and Treasure Rares. Hits are scheduled
per case and per box, as in real product, and each player's 6 packs come consecutively from
one box. Bandai publishes no pull rates, so each number is tagged as confirmed, a community
estimate (with its source) or an assumption you can change.

The deckbuilder picks 40 cards ranked by printed stats, with a minimum of cheap plays and a
cap on expensive ones. Card values can be passed in to replace the stat-based ranking.

## How it works

The engine is a state machine. `legal_actions(state)` lists the moves available to the
player who must decide, and `apply(state, action)` advances the game. Bots only ever pick
from that list, which keeps the rules in one place and lets search-based bots copy the
state and explore possible futures.

```
src/optcg/
  cards.py          card definitions and keyword parsing
  loader.py         card data from punk-records -> data/cards/<SET>.json
  event.py          event leader (Luffy) and event format
  packs.py          pack model and case -> box -> pack opening
  deckbuilder.py    sealed deckbuilding
  engine/
    state.py        game state (copyable for search)
    actions.py      the actions bots choose between
    game.py         rules: setup, legal_actions(), apply()
  agents/           bots: random, heuristic
  sim.py            run games and matches
  cli.py            `optcg cards | sim | show | pool | sealed`
config/             pack model, event format
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
