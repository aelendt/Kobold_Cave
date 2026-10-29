// Draws the picture panel above the log. kobold_cave.py calls show(scene,
// ...) and the page passes those details here as plain objects.
import { SPRITES, PALETTE } from './sprites.js';

const panel = document.getElementById('scene');
const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)');

// Last health seen for each fighter, so updates can animate the change.
// Party members are keyed by name, since the party changes as people join.
let previous = { party: {}, enemy: null };

function sprite(name) {
  const rows = SPRITES[name] || [];
  const canvas = document.createElement('canvas');
  canvas.width = rows[0]?.length || 16;
  canvas.height = rows.length || 16;
  canvas.className = 'sprite';
  canvas.setAttribute('role', 'img');
  canvas.setAttribute('aria-label', name);
  const ctx = canvas.getContext('2d');
  rows.forEach((row, y) => [...row].forEach((ch, x) => {
    if (ch === '.') return;
    ctx.fillStyle = PALETTE[ch];
    ctx.fillRect(x, y, 1, 1);
  }));
  return canvas;
}

function element(tag, className, text) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined) el.textContent = text;
  return el;
}

// A bar that slides from the old value to the new one.
function bar(kind, value, max, from = value) {
  const track = element('div', `bar ${kind}`);
  const fill = element('i');
  const percent = v => `${Math.max(0, Math.min(100, (v / max) * 100))}%`;
  fill.style.width = percent(from);
  track.append(fill);
  if (from !== value) requestAnimationFrame(() => requestAnimationFrame(() => {
    fill.style.width = percent(value);
  }));
  return track;
}

function fighter({ spriteName, title, subtitle, health, maxHealth, mana, maxMana, before, boss, active }) {
  const figure = element('figure', 'fighter');
  if (active) figure.classList.add('active');
  if ((SPRITES[spriteName]?.length || 16) > 16) figure.classList.add('big');
  const portrait = element('div', 'portrait');
  portrait.append(sprite(spriteName));
  figure.append(portrait);

  if (health <= 0) figure.classList.add('fallen');
  if (before !== undefined && health < before) {
    figure.classList.add('hit');
    portrait.append(element('span', 'float', `-${before - health}`));
  } else if (before !== undefined && health > before) {
    portrait.append(element('span', 'float heal', `+${health - before}`));
  }

  const caption = element('figcaption');
  const name = element('div', 'who', title);
  if (boss) name.append(element('span', 'badge', 'Boss'));
  caption.append(name, element('div', 'what', subtitle));
  const hp = element('div', 'meter');
  hp.append(bar('hp', health, maxHealth, before ?? health),
            element('span', 'nums', `${Math.max(0, health)}/${maxHealth}`));
  caption.append(hp);
  if (maxMana) {
    const pips = element('div', 'pips');
    pips.setAttribute('aria-label', `Mana ${mana} of ${maxMana}`);
    for (let i = 0; i < maxMana; i++) pips.append(element('i', i < mana ? 'full' : ''));
    caption.append(pips);
  }
  figure.append(caption);
  return figure;
}

function partySide({ party, active, bandages }, scene) {
  const side = element('div', `side party size-${party.length}`);
  party.forEach((member, i) => {
    side.append(fighter({
      spriteName: member.job.toLowerCase(),
      title: member.name || 'Nameless',
      subtitle: member.job,
      health: member.health,
      maxHealth: member.max_health,
      mana: member.mana,
      maxMana: member.max_mana,
      before: previous.party[member.name],
      active: scene === 'combat' && i === active,
    }));
  });
  previous.party = Object.fromEntries(party.map(member => [member.name, member.health]));
  if (scene === 'victory') side.classList.add('triumph');
  if (bandages !== undefined) {
    const supplies = element('div', 'supplies', `Bandages: ${bandages}`);
    side.append(supplies);
  }
  return side;
}

function enemySide(enemy, scene) {
  const side = element('div', 'side enemy');
  if (enemy) {
    side.append(fighter({
      spriteName: enemy.name,
      title: enemy.name,
      subtitle: enemy.boss ? 'Master of the mines' : 'Kobold',
      health: enemy.health,
      maxHealth: enemy.max_health,
      before: previous.enemy,
      boss: enemy.boss,
    }));
    previous.enemy = enemy.health;
  } else {
    previous.enemy = null;
    const quiet = {
      explore: 'The tunnel ahead is quiet. For now.',
      defeat: 'The kobolds drag you off. Nobody is surprised.',
      victory: 'The mines fall silent.',
    }[scene] || '';
    side.append(element('p', `quiet ${scene}`, quiet));
  }
  return side;
}

function jobCards(jobs, pick) {
  const most = stat => Math.max(...jobs.map(job => job[stat]));
  const grid = element('div', 'jobs');
  jobs.forEach((job, i) => {
    const card = element('button', 'job');
    card.type = 'button';
    card.addEventListener('click', () => pick(job.name));
    const portrait = element('div', 'portrait');
    portrait.append(sprite(job.name.toLowerCase()));
    const heading = element('div', 'who');
    heading.append(element('kbd', '', String(i + 1)), document.createTextNode(job.name));
    card.append(portrait, heading);
    for (const [stat, label] of [['health', 'HP'], ['attack', 'ATK'], ['dodge', 'DGE']]) {
      const row = element('div', 'stat-row');
      row.append(element('span', 'label', label), bar('stat', job[stat], most(stat)),
                 element('span', 'nums', String(job[stat])));
      card.append(row);
    }
    card.append(element('div', 'what', job.special || 'No special move'),
                element('div', 'what', `Learns ${job.lessons.join(', ')}`),
                element('div', 'what', job.gear.join(' & ')));
    grid.append(card);
  });
  return grid;
}

function recruitCards({ prisoners, boon }, pick) {
  const grid = element('div', 'jobs recruits');
  const options = [...prisoners.map(p => p.name), 'Power up'];
  prisoners.forEach((prisoner, i) => {
    const card = element('button', 'job');
    card.type = 'button';
    card.addEventListener('click', () => pick(prisoner.name));
    const portrait = element('div', 'portrait');
    portrait.append(sprite(prisoner.job.toLowerCase()));
    const heading = element('div', 'who');
    heading.append(element('kbd', '', String(i + 1)), document.createTextNode(prisoner.name));
    card.append(portrait, heading, element('div', 'what', `${prisoner.job} · ${prisoner.max_health} HP`),
                element('div', 'what', prisoner.special || 'No special move'));
    grid.append(card);
  });
  const chest = element('button', 'job boon');
  chest.type = 'button';
  chest.addEventListener('click', () => pick('Power up'));
  const portrait = element('div', 'portrait');
  portrait.append(sprite('chest'));
  const heading = element('div', 'who');
  heading.append(element('kbd', '', String(options.length)), document.createTextNode('Power up'));
  chest.append(portrait, heading, element('div', 'what', `${boon.name} for ${boon.for}`),
               element('div', 'what', boon.describe));
  if (boon.lesson) {
    const lesson = element('div', 'what lesson', `Learn ${boon.lesson}: ${boon.lesson_describe}`);
    chest.append(lesson);
  }
  grid.append(chest);
  return grid;
}

export function showScene(scene, details, { pick }) {
  panel.hidden = false;
  panel.dataset.scene = scene;
  if (scene === 'jobs') {
    previous = { party: {}, enemy: null };
    panel.replaceChildren(jobCards(details.jobs, pick));
    return;
  }
  if (scene === 'recruit') {
    panel.replaceChildren(recruitCards(details, pick));
    return;
  }
  // Every fight is preceded by an 'explore' scene, which clears the enemy's
  // previous health, so a new kobold's bar starts full rather than sliding.
  const arena = element('div', 'arena');
  arena.append(partySide(details, scene), enemySide(details.enemy, scene));
  panel.replaceChildren(arena);
  if (reduceMotion.matches) panel.querySelectorAll('.float').forEach(el => el.remove());
}

export function clearScene() {
  previous = { party: {}, enemy: null };
  panel.hidden = true;
  panel.replaceChildren();
}
