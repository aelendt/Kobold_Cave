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

function fighter({ spriteName, title, subtitle, health, maxHealth, mana, maxMana, before, boss, active,
                   xp, effects = [] }) {
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
  if (effects.length) {
    const chips = element('div', 'effects');
    effects.forEach(effect => chips.append(
      element('span', effect.startsWith('Winding up') ? 'chip warning' : 'chip', effect)));
    caption.append(chips);
  }
  if (xp) {
    // A thin bar of progress through the current level.
    const progress = xp.to ? (xp.now - xp.from) / (xp.to - xp.from) : 1;
    const track = bar('xp', progress, 1);
    track.title = xp.to ? `${xp.now} / ${xp.to} XP` : 'Max level';
    caption.append(track);
  }
  figure.append(caption);
  return figure;
}

function partySide({ party, active }, scene) {
  const side = element('div', `side party size-${party.length}`);
  party.forEach((member, i) => {
    side.append(fighter({
      spriteName: member.job.toLowerCase(),
      title: member.name || 'Nameless',
      subtitle: `${member.job} · Lv ${member.level}`,
      xp: { now: member.xp, from: member.xp_from, to: member.xp_to },
      effects: member.effects,
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
      before: previous.enemy ?? undefined,  // no previous health: a new enemy, nothing to animate
      boss: enemy.boss,
      effects: enemy.effects,
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
    card.append(element('div', 'what', job.special ? `Signature: ${job.special}` : 'No signature move'),
                element('div', 'what', `Skills: 1 of ${job.skills.join(', ')}`),
                element('div', 'what lesson', `Boons: ${job.boon_abilities.join(', ')}`),
                element('div', 'what', job.gear.join(' & ')));
    grid.append(card);
  });
  return grid;
}

// A card button with a picture, a numbered heading and some lines of text.
function choiceCard(spriteName, number, title, lines, onPick, extraClass = '') {
  const card = element('button', `job ${extraClass}`.trim());
  card.type = 'button';
  card.addEventListener('click', onPick);
  if (spriteName) {
    const portrait = element('div', 'portrait');
    portrait.append(sprite(spriteName));
    card.append(portrait);
  }
  const heading = element('div', 'who');
  heading.append(element('kbd', '', String(number)), document.createTextNode(title));
  card.append(heading);
  lines.forEach(([text, cls]) => card.append(element('div', cls || 'what', text)));
  return card;
}

function skillCards({ job, skills }, pick) {
  const grid = element('div', 'jobs');
  skills.forEach((skill, i) => grid.append(
    choiceCard(job.toLowerCase(), i + 1, skill.name, [[skill.description]], () => pick(skill.name))));
  return grid;
}

function recruitCards({ prisoners, boon, abilities }, pick) {
  const grid = element('div', 'jobs recruits');
  prisoners.forEach((prisoner, i) => grid.append(choiceCard(
    prisoner.job.toLowerCase(), i + 1, prisoner.name,
    [[`${prisoner.job} · Lv ${prisoner.level} · ${prisoner.max_health} HP`],
     [`Knows ${prisoner.skills.join(', ')}`]],
    () => pick(prisoner.name))));
  abilities.forEach((ability, i) => grid.append(choiceCard(
    'chest', prisoners.length + i + 1, ability.name,
    [[ability.description, 'what lesson'], [`${boon.name} for ${boon.for}: ${boon.describe}`]],
    () => pick(ability.name), 'boon')));
  return grid;
}

// What a win paid out, as [label, text, class] rows, for the card and the pop-up.
function spoilsRows(spoils, partySize = 1) {
  const rows = [['XP', `+${spoils.xp}${partySize > 1 ? ' each' : ''}`, 'gain']];
  spoils.levelled.forEach(line => rows.push(['Level up', line, 'gain']));
  if (spoils.gold) rows.push(['Gold', `+${spoils.gold}`, 'gold']);
  // Finds come as "Item: where it went"; anything else is a plain note.
  const found = spoils.found.includes(': ');
  rows.push(['Loot', found ? spoils.found.replace(/: (.*)/, ' ($1)') : spoils.found, found ? 'loot' : '']);
  if (spoils.trophy) rows.push(['Trophy', spoils.trophy.text, spoils.trophy.complete ? 'gain' : 'loot']);
  if (spoils.bandages) rows.push(['Bandages', `+${spoils.bandages}`, '']);
  const rested = Object.entries(spoils.healing).filter(([, hp]) => hp > 0)
    .map(([name, hp]) => `${name} +${hp} HP`);
  if (rested.length) rows.push(['Rested', rested.join(', '), '']);
  return rows;
}

function spoilsCard(spoils, partySize) {
  const card = element('div', 'side venue-notes');
  card.append(element('div', 'who', `${spoils.monster} defeated`));
  const list = element('ul', 'spoils');
  if (spoils.ratings.length) {
    list.append(element('li', 'gain', spoils.ratings.map(rating => rating.name).join(' · ')));
  }
  spoilsRows(spoils, partySize).forEach(([label, text, cls]) =>
    list.append(element('li', cls, `${label}: ${text}`)));
  card.append(list);
  return card;
}

// A boss's XP bar for one hero: it fills from where they were, flashes
// "Level N!" each time it tops out, and ends where they are now.
function xpMeter(hero, levelXp) {
  const progress = (level, xp) => level >= levelXp.length ? 1
    : (xp - levelXp[level - 1]) / (levelXp[level] - levelXp[level - 1]);
  const width = fraction => `${Math.round(fraction * 100)}%`;
  const box = element('span', 'xp-meter');
  const track = element('span', 'bar xp');
  const fill = element('i');
  const tag = element('span', 'xp-tag', `Lv ${hero.level_before}`);
  track.append(fill);
  box.append(track, tag);
  fill.style.width = width(progress(hero.level_before, hero.xp_before));
  const jump = to => {  // move without the slide, then let it slide again
    fill.style.transition = 'none';
    fill.style.width = to;
    void fill.offsetWidth;
    fill.style.transition = '';
  };
  const levelled = level => { box.classList.add('levelled'); tag.textContent = `Level ${level}!`; };
  const timers = [];
  return {
    node: box,
    start() {
      let wait = 0;
      const later = (delay, run) => timers.push(setTimeout(run, wait += delay));
      for (let level = hero.level_before + 1; level <= hero.level; level++) {
        later(50, () => { fill.style.width = '100%'; });
        later(650, () => { levelled(level); jump('0%'); });
      }
      later(50, () => { fill.style.width = width(progress(hero.level, hero.xp)); });
    },
    end() {
      timers.forEach(clearTimeout);
      jump(width(progress(hero.level, hero.xp)));
      if (hero.level > hero.level_before) levelled(hero.level);
    },
  };
}

// A number that counts up from one value to another.
function counter(from, to) {
  const node = element('span', 'count', String(from));
  let frame;
  return {
    node,
    start() {
      const began = performance.now();
      const tick = now => {
        const t = Math.min(1, (now - began) / 900);
        node.textContent = String(Math.round(from + (to - from) * t));
        if (t < 1) frame = requestAnimationFrame(tick);
      };
      frame = requestAnimationFrame(tick);
    },
    end() { cancelAnimationFrame(frame); node.textContent = String(to); },
  };
}

// The pop-up's rows. A boss's are livelier: an XP bar per hero, a gold
// total that counts up, and loot compared with what is worn. Each row is
// { label, value (text or node), cls, note, start, end }.
function popupRows(spoils, details) {
  const rows = spoilsRows(spoils, details.party.length)
    .map(([label, value, cls]) => ({ label, value, cls }));
  if (!spoils.boss) return rows;
  const lively = [];
  for (const row of rows) {
    if (row.label === 'XP') {
      spoils.heroes.forEach(hero => {
        const meter = xpMeter(hero, spoils.level_xp);
        lively.push({ label: hero.name, value: meter.node, cls: 'gain', note: `+${spoils.xp} XP`,
                      start: meter.start, end: meter.end });
      });
    } else if (row.label === 'Gold') {
      const total = counter(spoils.gold_before, details.gold);
      const value = element('span', '', `${row.value}, now `);
      value.append(total.node);
      lively.push({ ...row, value, start: total.start, end: total.end });
    } else if (row.label === 'Loot') {
      lively.push({ ...row, note: spoils.against });
    } else if (row.label !== 'Level up') {  // the XP bars show those
      lively.push(row);
    }
  }
  return lively;
}

// After a win, a pop-up shows its ratings, the narrator's verdict and the
// rewards one at a time, and waits to be closed; the returned promise
// resolves when it is. Closing it before it has finished shows the rest at once.
const ROW_DELAY = 0.3;  // seconds between rewards appearing
export function showSpoils(spoils, details) {
  const dialog = document.getElementById('spoils-dialog');
  dialog.classList.toggle('boss', Boolean(spoils.boss));
  const stamps = element('div', 'stamps');
  spoils.ratings.forEach(({ name, bonus }, i) => {
    const stamp = element('span', `stamp ${name.toLowerCase()}`, name);
    stamp.append(element('small', '', bonus));
    stamp.style.animationDelay = `${0.15 + i * 0.25}s`;
    stamps.append(stamp);
  });
  const offset = spoils.ratings.length * 0.25 + 0.2;  // rewards follow the stamps
  const rows = popupRows(spoils, details);
  const list = element('ul', 'reward-list');
  const timers = [];
  rows.forEach((row, i) => {
    const item = element('li', row.cls);
    item.style.animationDelay = `${offset + i * ROW_DELAY}s`;
    const value = element('span', 'value');
    value.append(row.value);
    if (row.note) value.append(element('span', 'note', row.note));
    item.append(element('span', 'label', row.label), value);
    list.append(item);
    if (row.start) timers.push(setTimeout(row.start, (offset + i * ROW_DELAY) * 1000));
  });
  const totals = element('p', 'totals', `Gold ${details.gold} · Bandages ${details.bandages}`
                                        + ` · Bag ${details.bag.length}/${details.bag_size}`);
  const collect = element('button', 'collect', 'Collect');
  collect.type = 'button';
  dialog.replaceChildren(element('h2', '', `${spoils.monster} defeated`),
                         element('p', 'what', spoils.boss ? 'A hoard of spoils' : 'Spoils of battle'),
                         stamps, element('p', 'verdict', spoils.verdict), list, totals, collect);

  let ready = false;
  const finish = () => {
    ready = true;
    timers.forEach(clearTimeout);
    rows.forEach(row => row.end?.());
    dialog.classList.add('shown');
  };
  dialog.classList.remove('shown');
  const settle = (offset + rows.length * ROW_DELAY + (spoils.boss ? 1.4 : 0)) * 1000;
  if (reduceMotion.matches) finish();
  const timer = setTimeout(() => { ready = true; }, settle);
  return new Promise(resolve => {
    const close = () => {
      if (!ready) return finish();
      clearTimeout(timer);
      dialog.close();
    };
    collect.addEventListener('click', close);
    dialog.oncancel = event => { event.preventDefault(); close(); };  // Escape
    dialog.addEventListener('close', resolve, { once: true });
    dialog.showModal();
    collect.focus();
  });
}

function forkCards(pick) {
  const grid = element('div', 'jobs');
  [['anvil', 'Forge', 'Break old gear into scrap. Spend scrap to reforge equipped gear, up to +3.'],
   ['trader', 'Trader', 'Spend gold on bandages, vials, trinkets and skill tomes. Sell old gear.'],
   ['tunnel', 'Tunnel', 'A forgotten cache of gold and loot. Or an ambush.']]
    .forEach(([spriteName, title, text], i) => grid.append(
      choiceCard(spriteName, i + 1, title, [[text]], () => pick(title))));
  return grid;
}

function venue(spriteName, title, purse, sections) {
  const box = element('div', 'venue');
  const portrait = element('div', 'portrait');
  portrait.append(sprite(spriteName));
  const body = element('div', 'venue-notes');
  body.append(element('div', 'who', title), element('div', 'gold', purse));
  sections.forEach(([heading, rows]) => {
    if (!rows.length) return;
    body.append(element('div', 'what venue-heading', heading));
    const list = element('ul', 'spoils');
    rows.forEach(([main, note]) => {
      const row = element('li', '', main);
      if (note) row.append(element('span', 'what', ` ${note}`));
      list.append(row);
    });
    body.append(list);
  });
  box.append(portrait, body);
  return box;
}

export function showScene(scene, details, { pick }) {
  panel.hidden = false;
  panel.dataset.scene = scene;
  if (scene === 'jobs') {
    previous = { party: {}, enemy: null };
    panel.replaceChildren(jobCards(details.jobs, pick));
    return;
  }
  if (scene === 'skills') {
    panel.replaceChildren(skillCards(details, pick));
    return;
  }
  if (scene === 'recruit') {
    panel.replaceChildren(recruitCards(details, pick));
    return;
  }
  if (scene === 'fork') {
    panel.replaceChildren(forkCards(pick));
    return;
  }
  if (scene === 'forge') {
    const { scrap, salvage, reforge } = details.forge;
    panel.replaceChildren(venue('anvil', 'The Forge', `Scrap: ${scrap}`, [
      ['Salvage from the bag', salvage.map(item => [item.name, `${item.scrap} scrap`])],
      ['Reforge', reforge.map(row => [row.label, `${row.cost} scrap: ${row.into}`])],
    ]));
    return;
  }
  if (scene === 'trader') {
    const { gold, stock, sell } = details.trader;
    panel.replaceChildren(venue('trader', 'The Trader', `Gold: ${gold}`, [
      ['For sale', stock.map(row => [`${row.label}, ${row.price} gold`, row.note])],
      ['He would buy', sell.map(item => [item.name, `${item.gold} gold`])],
    ]));
    return;
  }
  if (scene === 'spoils') {
    previous.enemy = null;
    const arena = element('div', 'arena');
    arena.append(partySide(details, scene), spoilsCard(details.spoils, details.party.length));
    panel.replaceChildren(arena);
    return;
  }
  // Every fight is preceded by an 'explore' scene, which clears the enemy's
  // previous health, so a new kobold's bar starts full rather than sliding.
  const arena = element('div', 'arena');
  arena.append(partySide(details, scene), enemySide(details.enemy, scene));
  panel.replaceChildren(arena);
  if (reduceMotion.matches) panel.querySelectorAll('.float').forEach(el => el.remove());
}

// The killing blow: the battle panel shakes, the enemy's sprite bursts into
// its pixels, gold coins fly, and a banner goes up. Resolves when it's done,
// so the log waits for it.
export function celebrate(enemy) {
  const banner = element('div', 'victory-banner', enemy.boss ? 'Boss slain!' : 'Victory!');
  panel.append(banner);
  const canvas = panel.querySelector('.enemy .portrait canvas');
  if (reduceMotion.matches || !canvas) return new Promise(resolve => setTimeout(resolve, 500));

  panel.classList.remove('shake');
  void panel.offsetWidth;
  panel.classList.add('shake');
  const rows = SPRITES[enemy.name] || [];
  const box = canvas.getBoundingClientRect();
  const cell = box.width / (rows[0]?.length || 16);
  const margin = 120;
  const burst = document.createElement('canvas');
  burst.className = 'burst';
  burst.width = box.width + margin * 2;
  burst.height = box.height + margin * 2;
  Object.assign(burst.style, { left: `${box.left - margin}px`, top: `${box.top - margin}px` });
  document.body.append(burst);
  canvas.style.visibility = 'hidden';

  const pieces = [];
  rows.forEach((row, y) => [...row].forEach((ch, x) => {
    if (ch === '.') return;
    pieces.push({ x: margin + x * cell, y: margin + y * cell, size: cell, color: PALETTE[ch],
                  vx: (x - row.length / 2) * 0.25 + (Math.random() - 0.5) * 2,
                  vy: -1 - Math.random() * 3.5 });
  }));
  for (let i = 0; i < (enemy.boss ? 26 : 12); i++) {
    pieces.push({ x: margin + box.width / 2, y: margin + box.height / 2, size: cell * 1.3,
                  color: i % 3 ? '#f4d27a' : '#fff3c4', coin: true,
                  vx: (Math.random() - 0.5) * 7, vy: -5 - Math.random() * 4 });
  }
  const ctx = burst.getContext('2d');
  const duration = enemy.boss ? 1700 : 1100;
  const began = performance.now();
  return new Promise(resolve => {
    let last = began;
    const frame = now => {
      const steps = (now - last) / 16.7;  // move at the same speed at any frame rate
      last = now;
      const t = (now - began) / duration;
      ctx.clearRect(0, 0, burst.width, burst.height);
      ctx.globalAlpha = Math.max(0, 1 - t * t);
      for (const piece of pieces) {
        piece.vy += 0.3 * steps;
        piece.x += piece.vx * steps;
        piece.y += piece.vy * steps;
        ctx.fillStyle = piece.color;
        ctx.fillRect(piece.x, piece.y, piece.size, piece.coin ? piece.size * (0.4 + Math.abs(Math.sin(now / 90 + piece.vx))) : piece.size);
      }
      if (t < 1) return requestAnimationFrame(frame);
      burst.remove();
      resolve();
    };
    requestAnimationFrame(frame);
  });
}

export function clearScene() {
  previous = { party: {}, enemy: null };
  panel.hidden = true;
  panel.replaceChildren();
}
