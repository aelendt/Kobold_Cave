// The hall of legends: every run finished in this browser, best first or
// newest first, in a dialog of its own. kobold_cave.py sends each run's
// record (see run_record) when it ends; the hall keeps them in
// localStorage, if the browser lets it.

const STORE = 'kobold-cave-hall';
const KEEP = 200;  // runs remembered; the oldest are forgotten first
const dialog = document.getElementById('hall-dialog');
let runs = load();
let view = 'best';  // or 'recent'
let latest = null;  // when the run just finished ended, to highlight it

function load() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORE));
    return Array.isArray(saved) ? saved : [];
  } catch {
    return [];
  }
}

function save() {
  try {
    localStorage.setItem(STORE, JSON.stringify(runs));
  } catch {
    // Storage is blocked; the hall lasts until the page reloads.
  }
}

const byScore = (a, b) => b.score - a.score || b.when - a.when;

// Remember a finished run. Returns its place by score, and how many runs there are.
export function addRun(run) {
  const record = { ...run, when: Date.now() };
  latest = record.when;
  runs = [...runs, record].slice(-KEEP);
  save();
  return { place: [...runs].sort(byScore).indexOf(record) + 1, of: runs.length };
}

function element(tag, className, text) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined) el.textContent = text;
  return el;
}

function outcome(run) {
  return run.won ? 'Slew Cinderjaw' : `Fell to the ${run.killer} in the ${run.stage}`;
}

function when(time) {
  return new Date(time).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

function runRow(run, rank) {
  const isLatest = run.when === latest;
  const row = element('li', `hall-run${run.won ? ' won' : ''}${isLatest ? ' latest' : ''}`);
  row.append(element('span', 'hall-rank', rank ? `${rank}` : ''));
  const body = element('div', 'hall-body');
  const top = element('div', 'hall-top');
  top.append(element('span', 'who', run.name),
             element('span', 'what', `Lv ${run.level} ${run.job}`));
  if (isLatest) top.append(element('span', 'tag', 'This run'));
  body.append(top, element('div', 'hall-outcome', outcome(run)));
  const details = [`${run.slain} slain`, `${run.gold} gold`];
  if (run.recruits.length) details.push(`with ${run.recruits.join(', ')}`);
  details.push(when(run.when));
  body.append(element('div', 'what', details.join(' · ')));
  row.append(body, element('span', 'hall-score', run.score.toLocaleString()));
  return row;
}

function totals() {
  const list = element('dl', 'hall-totals');
  const best = runs.length ? Math.max(...runs.map(run => run.score)) : 0;
  [['Runs', runs.length],
   ['Dragons slain', runs.filter(run => run.won).length],
   ['Kobolds slain', runs.reduce((sum, run) => sum + run.slain, 0)],
   ['Best score', best.toLocaleString()]]
    .forEach(([label, value]) => {
      const box = element('div');
      box.append(element('dt', '', label), element('dd', '', String(value)));
      list.append(box);
    });
  return list;
}

function draw() {
  const head = element('div', 'hall-head');
  const close = element('button', 'hall-close', 'Close');
  close.type = 'button';
  close.addEventListener('click', () => dialog.close());
  head.append(element('h2', '', 'Hall of Legends'), close);

  const tabs = element('div', 'tabs');
  tabs.setAttribute('role', 'tablist');
  [['best', 'Best'], ['recent', 'Recent']].forEach(([key, label]) => {
    const tab = element('button', 'tab', label);
    tab.type = 'button';
    tab.setAttribute('role', 'tab');
    tab.setAttribute('aria-selected', String(view === key));
    tab.addEventListener('click', () => { view = key; draw(); });
    tabs.append(tab);
  });

  const list = element('ol', 'hall-list');
  if (!runs.length) {
    list.append(element('li', 'hall-empty', 'No runs yet. The mines are waiting.'));
  } else if (view === 'best') {
    [...runs].sort(byScore).slice(0, 20).forEach((run, i) => list.append(runRow(run, i + 1)));
  } else {
    [...runs].reverse().slice(0, 20).forEach(run => list.append(runRow(run)));
  }

  const note = element('p', 'what hall-note',
    'Score: XP earned, plus gold found, plus 25 for each Flawless, Swift or Overkill win, '
    + 'plus 500 for slaying Cinderjaw. Runs are kept in this browser.');
  dialog.replaceChildren(head, element('p', 'what', 'Every run that ended in this browser.'),
                         totals(), tabs, list, note);
}

export function showHall() {
  const saved = load();  // another tab may have added runs
  if (saved.length >= runs.length) runs = saved;
  draw();
  if (!dialog.open) dialog.showModal();
  dialog.querySelector('.hall-close').focus();
}
