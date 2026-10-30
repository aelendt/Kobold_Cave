// The hall of legends, in a dialog of its own: every run finished in this
// browser (best first, or newest first) and the shared leaderboard. Each
// run's record comes from kobold_cave.py (run_record) with its grade, tier
// and how the grade adds up. The hall keeps them in localStorage, if the
// browser lets it. The leaderboard is leaderboard.json in the repository:
// Submit opens a GitHub issue with the run, and a workflow adds it.

const STORE = 'kobold-cave-hall';
const KEEP = 200;  // runs remembered; the oldest are forgotten first
const REPO = 'aelendt/Kobold_Cave';
// Read straight from the repository, so a new entry shows up without the
// site being rebuilt; the copy next to the page is the fallback.
const LEADERBOARD = [`https://raw.githubusercontent.com/${REPO}/main/leaderboard.json`, './leaderboard.json'];
const FACTS = ['name', 'job', 'level', 'recruits', 'won', 'stage', 'depth', 'killer', 'slain',
               'bosses', 'ratings', 'relics', 'gold', 'hoards', 'fled'];
const TIERS = [[500, 'Legend'], [400, 'Grandmaster'], [300, 'Master'], [200, 'Gold'],
               [100, 'Silver'], [0, 'Bronze']];

const dialog = document.getElementById('hall-dialog');
let runs = load();
let view = 'best';  // 'recent' or 'board'
let latest = null;  // when the run just finished ended, to highlight it
let open = null;  // the run whose grade breakdown is showing
let board = null;  // the shared leaderboard once fetched, or an Error

function load() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORE));
    // Runs from before grading have no grade to rank them by.
    return Array.isArray(saved) ? saved.filter(run => typeof run.grade === 'number') : [];
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

const byGrade = (a, b) => b.grade - a.grade || b.when - a.when;

// Remember a finished run. Returns its place by grade, and how many runs there are.
export function addRun(run) {
  const record = { ...run, when: Date.now() };
  latest = record.when;
  runs = [...runs, record].slice(-KEEP);
  save();
  return { place: [...runs].sort(byGrade).indexOf(record) + 1, of: runs.length };
}

function element(tag, className, text) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined) el.textContent = text;
  return el;
}

function button(className, text, onClick) {
  const el = element('button', className, text);
  el.type = 'button';
  el.addEventListener('click', onClick);
  return el;
}

export function tierBadge(tier) {
  return element('span', `tier ${tier.toLowerCase()}`, tier);
}

function outcome(run) {
  return run.won ? 'Slew Cinderjaw' : `Fell to the ${run.killer} in the ${run.stage}`;
}

function when(time) {
  return new Date(time).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

// The same link the terminal prints (kobold_cave.submit_link).
function submitLink(run) {
  const facts = Object.fromEntries(FACTS.map(key => [key, run[key]]));
  const body = 'Adding a run to the Kobold Cave leaderboard. Leave the block below as it is.\n\n'
    + '```json\n' + JSON.stringify(facts) + '\n```\n';
  const query = new URLSearchParams({ title: `Run: ${run.name}, ${run.tier} (${run.grade})`, body });
  return `https://github.com/${REPO}/issues/new?${query}`;
}

function runRow(run, rank, { local }) {
  const key = local ? `local-${run.when}` : `board-${run.issue}`;
  const isLatest = local && run.when === latest;
  const row = element('li', `hall-run${run.won ? ' won' : ''}${isLatest ? ' latest' : ''}`);
  row.append(element('span', 'hall-rank', rank ? `${rank}` : ''));

  const body = element('div', 'hall-body');
  const top = element('div', 'hall-top');
  top.append(element('span', 'who', run.name), element('span', 'what', `Lv ${run.level} ${run.job}`));
  if (isLatest) top.append(element('span', 'tag', 'This run'));
  body.append(top, element('div', 'hall-outcome', outcome(run)));
  const details = [`${run.slain} slain`, `${run.gold} gold`];
  if (run.recruits.length) details.push(`with ${run.recruits.join(', ')}`);
  details.push(local ? when(run.when) : `by ${run.player}, ${run.date}`);
  body.append(element('div', 'what', details.join(' · ')));

  const actions = element('div', 'hall-actions');
  actions.append(button('hall-small', open === key ? 'Hide grade' : 'How graded',
                        () => { open = open === key ? null : key; draw(); }));
  if (local) {
    const link = element('a', 'hall-small', run.submitted ? 'Submitted' : 'Submit');
    link.href = submitLink(run);
    link.target = '_blank';
    link.rel = 'noopener';
    link.title = 'Opens a GitHub issue with this run; submitting it adds the run to the leaderboard';
    link.addEventListener('click', () => {
      run.submitted = true;
      save();
      setTimeout(draw);
    });
    actions.append(link);
  }
  body.append(actions);
  if (open === key) {
    const parts = element('dl', 'hall-parts');
    run.parts.forEach(([label, points]) => {
      parts.append(element('dt', '', label), element('dd', '', `${points > 0 ? '+' : ''}${points}`));
    });
    body.append(parts);
  }

  const grade = element('div', 'hall-grade');
  grade.append(element('span', 'hall-score', String(run.grade)), tierBadge(run.tier));
  row.append(body, grade);
  return row;
}

function totals() {
  const list = element('dl', 'hall-totals');
  const best = runs.length ? [...runs].sort(byGrade)[0] : null;
  [['Runs', runs.length],
   ['Dragons slain', runs.filter(run => run.won).length],
   ['Kobolds slain', runs.reduce((sum, run) => sum + run.slain + run.bosses, 0)],
   ['Best grade', best ? `${best.grade} ${best.tier}` : '—']]
    .forEach(([label, value]) => {
      const box = element('div');
      box.append(element('dt', '', label), element('dd', '', String(value)));
      list.append(box);
    });
  return list;
}

async function fetchBoard() {
  for (const url of LEADERBOARD) {
    try {
      const response = await fetch(url, { cache: 'no-cache' });
      if (response.ok) return await response.json();
    } catch {
      // Try the next copy.
    }
  }
  return new Error('The leaderboard could not be reached.');
}

function boardList() {
  const list = element('ol', 'hall-list');
  if (board === null) {
    list.append(element('li', 'hall-empty', 'Fetching the leaderboard…'));
    fetchBoard().then(result => { board = result; if (view === 'board') draw(); });
  } else if (board instanceof Error) {
    list.append(element('li', 'hall-empty', board.message));
  } else if (!board.length) {
    list.append(element('li', 'hall-empty', 'Nobody has sent a run yet. Be the first: Submit one from Best or Recent.'));
  } else {
    board.slice(0, 50).forEach((run, i) => list.append(runRow(run, i + 1, { local: false })));
  }
  return list;
}

function draw() {
  const head = element('div', 'hall-head');
  head.append(element('h2', '', 'Hall of Legends'), button('hall-close', 'Close', () => dialog.close()));

  const tabs = element('div', 'tabs');
  tabs.setAttribute('role', 'tablist');
  [['best', 'Best'], ['recent', 'Recent'], ['board', 'Leaderboard']].forEach(([key, label]) => {
    const tab = button('tab', label, () => { view = key; open = null; draw(); });
    tab.setAttribute('role', 'tab');
    tab.setAttribute('aria-selected', String(view === key));
    tabs.append(tab);
  });

  let list;
  if (view === 'board') {
    list = boardList();
  } else {
    list = element('ol', 'hall-list');
    if (!runs.length) list.append(element('li', 'hall-empty', 'No runs yet. The mines are waiting.'));
    const shown = view === 'best' ? [...runs].sort(byGrade) : [...runs].reverse();
    shown.slice(0, 20).forEach((run, i) =>
      list.append(runRow(run, view === 'best' ? i + 1 : 0, { local: true })));
  }

  const ladder = element('p', 'hall-tiers');
  [...TIERS].reverse().forEach(([floor, name], i, all) => {
    const next = all[i + 1];
    const step = element('span', 'hall-tier');
    step.append(tierBadge(name), document.createTextNode(next ? ` ${floor}–${next[0] - 1}` : ` ${floor}+`));
    ladder.append(step);
  });
  const note = element('p', 'what hall-note', view === 'board'
    ? 'Runs sent with Submit, graded again when they arrive. Anyone with a GitHub account can send one.'
    : "Every run that ended in this browser. A run's grade counts everything it did: open How graded to see it add up.");
  dialog.replaceChildren(...[head, view === 'board' ? null : totals(), tabs, list, ladder, note]
    .filter(Boolean));
}

export function showHall() {
  const saved = load();  // another tab may have added runs
  if (saved.length >= runs.length) runs = saved;
  if (view === 'board') board = null;  // fetch it fresh
  draw();
  if (!dialog.open) dialog.showModal();
  dialog.querySelector('.hall-close').focus();
}
