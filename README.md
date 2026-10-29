# Kobold Cave Text-Based RPG

This is my humble attempt at designing a simple game in order to teach myself Python.

Pick a warrior, rogue or wizard and fight your way through the Kobold Mines. The
more kobolds you slay, the nastier they get. Slay ten and you reach the Kobold
Leader's chamber, where you win by defeating it.

Each class carries different gear and finds loot to match:

| Class   | Gear            | Special                                         |
|---------|-----------------|-------------------------------------------------|
| Warrior | Sword & shield  | None, just a lot of health                      |
| Rogue   | Two swords      | Flee (not from the Leader)                      |
| Wizard  | Staff & shield  | Fireball, which costs mana; staves add spell power or mana |

Swords add attack and shields add max HP. When you find something for a full
slot, you choose whether to swap it in. After every fight you rest, recovering
some health and all of your mana.

## Playing

Requires Python 3.10 or newer, with no other dependencies.

```bash
python3 kobold_cave.py
```

To see every dice roll, set `DEBUG = True` at the top of `kobold_cave.py`.

### In the browser

`index.html` runs the same `kobold_cave.py` in Chrome using
[Pyodide](https://pyodide.org) (Python compiled to WebAssembly). Menus become
buttons, and number keys pick options. Serve the folder, then open
http://localhost:8000 in Chrome 137 or newer:

```bash
python3 -m http.server 8000
```

Opening `index.html` straight from disk won't work, because the browser blocks
it from reading `kobold_cave.py`. The page loads Pyodide from the jsDelivr CDN;
to play offline, put a copy of Pyodide (from `npm install pyodide@314.0.7`) in
a `pyodide/` folder next to `index.html`.

## Tests

```bash
python3 -m unittest
```
