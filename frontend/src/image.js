import { EXAMPLES, EXAMPLE_LABELS } from './mock_image.js';

const STANDARD_REASON = 'Visual requirements need independent review before CAD.';
const MAX_BYTES = 10 * 1024 * 1024;
const SPEC_FIELDS = ['board_id', 'case_shape', 'lid', 'port_requirements', 'mounting', 'wall_thickness_mm', 'needs_clarification', 'clarification_questions'];

// ---------- pure helpers (no page access) ----------
export function describeIssue(i) {
  const names = {
    unsupported_board: () => `Board not supported: ${i.board_id}`,
    unsupported_shape: () => `Shape not supported: ${i.shape}`,
    lid: () => `Lid (${i.style})`,
    port_opening: () => `${i.port_type} opening (${i.requested_side})`,
    external_wall_mount_holes: () => `${i.count} wall-mount hole(s)`,
  };
  return (names[i.code] || (() => i.code))();
}
export const fmt = (v) => (v === undefined ? '' : typeof v === 'string' ? v : JSON.stringify(v));
export function diffRows(raw = {}, fin = {}) {
  return SPEC_FIELDS.map((f) => ({ field: f, raw: fmt(raw[f]), final: fmt(fin[f]), changed: JSON.stringify(raw[f]) !== JSON.stringify(fin[f]) }));
}
// Reasons why the review cannot be approved. The backend makes the final decision; this only explains it.
export function approvalBlockers(result, instructions) {
  const b = [];
  const s = result.design_spec || {}, c = result.capability || {}, e = result.evidence || {}, a = result.visual_audit || {};
  if (c.status && c.status !== 'review_required') b.push('The agent status is "' + c.status + '", not "review_required".');
  if (!(instructions || '').trim()) b.push('A text requirement is needed: board and wall thickness must be stated in text.');
  (c.unsupported || []).forEach((i) => b.push('Not supported yet: ' + describeIssue(i)));
  if ((c.questions || []).length || s.needs_clarification) b.push('There are open clarification questions.');
  if (s.board_id !== 'raspberry_pi_4') b.push('The board is not confirmed as Raspberry Pi 4.');
  if (s.case_shape !== 'rectangular') b.push('The shape is not confirmed as rectangular.');
  if (!(s.lid && s.lid.present === false)) b.push('An explicit "no lid" request is required.');
  if (s.wall_thickness_mm === null || s.wall_thickness_mm === undefined) b.push('The wall thickness must be stated in the text requirement.');
  if ((e.unrepresented_features || []).length) b.push('Features outside the design spec were seen: ' + e.unrepresented_features.join('; '));
  if ((result.unverified_features || []).length) b.push('Unverified features: ' + result.unverified_features.join('; '));
  if ((a.other_features || []).length) b.push('The second reading found other features: ' + a.other_features.join('; '));
  if (!b.length) (c.review_reasons || []).filter((r) => r !== STANDARD_REASON).forEach((r) => b.push(r));
  return b;
}

// ---------- page ----------
const CSS = `
.tabs{display:flex;gap:8px;margin-bottom:14px}
.tabs button{background:#eef1ee;color:#1c2321;border:1px solid #d9dcd7}
.tabs button[aria-pressed=true]{background:#0b6e6e;color:#fff;border-color:#0b6e6e}
.imgwrap{position:relative;max-width:480px;margin:8px 0;border:1px solid #d9dcd7}
.imgwrap img{display:block;width:100%}
.imgph{aspect-ratio:4/3;background:#e8ebe7;color:#5d6763;display:flex;align-items:center;justify-content:center}
.box{position:absolute;border:2px solid #b3261e;background:rgba(179,38,30,.12);color:#b3261e;font-size:12px;font-weight:700}
.tablewrap{overflow-x:auto}
.tablewrap table{border-collapse:collapse;width:100%;font-size:13px}
.tablewrap th,.tablewrap td{border:1px solid #d9dcd7;padding:4px 8px;text-align:left;vertical-align:top;word-break:break-word}
.tablewrap tr.chg td{background:#fff4d6}
.muted{color:#5d6763;font-size:13px}.err{color:#b3261e;font-weight:600}
.approve{margin-top:16px;padding-top:8px;border-top:1px solid #d9dcd7}
.approve input[type=text]{padding:8px;border:1px solid #d9dcd7;border-radius:6px;font:inherit;margin-right:8px}
`;
const h = (tag, cls, ...kids) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  e.append(...kids.flat().filter((k) => k !== null && k !== undefined));
  return e;
};
const section = (title, items) => (items && items.length ? [h('h3', '', title), h('ul', '', ...items.map((t) => h('li', '', t)))] : []);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export function initImage({ api, useMock, loadSTL, clearModel, saveFile }) {
  document.head.append(h('style', '', CSS));
  const left = document.querySelector('main > section');
  const dlRow = document.getElementById('download').parentElement;
  const textPanel = h('div');
  while (left.firstChild) textPanel.append(left.firstChild);
  const imagePanel = h('div');
  const tabBar = h('div', 'tabs');
  const tabs = [];
  function select(i) {
    tabs.forEach((t, j) => {
      t.panel.style.display = i === j ? '' : 'none';
      t.btn.setAttribute('aria-pressed', String(i === j));
    });
    dlRow.style.display = i === 0 ? '' : 'none'; // the text tab owns the STEP/STL download row
    clearModel();
    if (tabs[i].onShow) tabs[i].onShow();
  }
  function addTab(label, panel, onShow) {
    const btn = h('button', '', label);
    const i = tabs.length;
    btn.onclick = () => select(i);
    tabs.push({ btn, panel, onShow });
    tabBar.append(btn);
    left.append(panel);
  }
  left.append(tabBar);
  addTab('Text request', textPanel);
  addTab('Image request', imagePanel);
  select(0);

  // ----- form -----
  const state = { file: null, url: null };
  const input = h('input');
  input.type = 'file';
  input.accept = 'image/png,image/jpeg';
  const formMsg = h('p', 'err');
  const preview = h('div');
  const text = h('textarea');
  text.rows = 3;
  text.maxLength = 2000;
  text.placeholder = 'Text requirement, for example: Make a rectangular case for Raspberry Pi 4 with no lid; 2 mm wall thickness.';
  const mockSel = h('select');
  Object.entries(EXAMPLE_LABELS).forEach(([k, label]) => { const o = h('option', '', label); o.value = k; mockSel.append(o); });
  const go = h('button', '', 'Analyze image');
  const out = h('div');
  imagePanel.append(
    h('label', '', 'Image (PNG or JPEG, 16 to 2048 pixels per side, up to 10 MiB)'),
    useMock ? h('p', 'muted', 'Mock mode: no upload needed. The result below is one of four real outputs of the image agent.') : input,
    formMsg, preview,
    h('label', '', 'Text requirement'),
    text,
    h('p', 'muted', 'Approval needs a text requirement that names the board and the wall thickness.'),
    h('div', 'row', go, useMock ? h('label', 'mock', 'Mock example ', mockSel) : ''),
    out,
  );

  input.onchange = () => {
    state.file = null; state.url = null; preview.replaceChildren(); out.replaceChildren(); formMsg.textContent = '';
    const f = input.files[0];
    if (!f) return;
    if (!['image/png', 'image/jpeg'].includes(f.type)) { formMsg.textContent = 'Only PNG or JPEG images are accepted.'; return; }
    if (f.size > MAX_BYTES) { formMsg.textContent = 'The image is larger than 10 MiB.'; return; }
    const url = URL.createObjectURL(f);
    const img = new Image();
    img.onload = () => {
      if (Math.min(img.naturalWidth, img.naturalHeight) < 16 || Math.max(img.naturalWidth, img.naturalHeight) > 2048) { formMsg.textContent = 'The image must be 16 to 2048 pixels on each side.'; return; }
      state.file = f; state.url = url;
      img.style.maxWidth = '240px';
      preview.append(img);
    };
    img.src = url;
  };

  const LIMIT_S = 300; // the real vision model needed about 170 s in Peicen's test
  async function post(path, body) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), LIMIT_S * 1000);
    try {
      const r = await fetch(api + path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal: ctrl.signal });
      if (!r.ok) {
        let msg = `The backend answered with status ${r.status}.`;
        try {
          const d = (await r.json()).detail;
          if (typeof d === 'string') msg = d;
          else if (d && d.message) msg = d.message;
          else if (Array.isArray(d)) msg = 'The request was not accepted. Check the image and the text.';
        } catch (e) { /* keep the generic message */ }
        if (r.status === 404 && path === '/image') msg = 'This backend has no image routes. They are only switched on when the backend is started with the image model (PIXOLID_IMAGE_AGENT_PORT), which is the case on Peicen\'s computer, not on a local backend.';
        throw new Error(msg);
      }
      return await r.json();
    } catch (e) {
      if (e.name === 'AbortError') throw new Error(`The backend did not answer within ${LIMIT_S} seconds. Is it still running?`);
      throw e;
    } finally { clearTimeout(timer); }
  }
  const toBase64 = (file) => new Promise((res, rej) => {
    const r = new FileReader();
    r.onload = () => res(String(r.result).slice(String(r.result).indexOf(',') + 1));
    r.onerror = () => rej(new Error('Could not read the image file.'));
    r.readAsDataURL(file);
  });

  go.onclick = async () => {
    go.disabled = true; out.replaceChildren(); clearModel();
    if (!useMock) out.append(h('p', 'muted', 'Analysing the image with the real vision model. This usually takes 2 to 3 minutes, please keep the page open.'));
    try {
      let env;
      if (useMock) { await sleep(1200); env = { task_id: 'image_mock', source_result_sha256: 'mock-sha256', result: structuredClone(EXAMPLES[mockSel.value]) }; }
      else {
        if (!state.file) throw new Error('Choose a valid image first.');
        env = await post('/image', { filename: state.file.name, image_base64: await toBase64(state.file), instructions: text.value });
      }
      if (!env || !env.result) throw new Error('The backend returned an unexpected answer.');
      renderReview(env);
    } catch (e) { out.replaceChildren(h('p', 'err', e.message || String(e))); } finally { go.disabled = false; }
  };

  // ----- review screen -----
  function renderReview(env) {
    const r = env.result, c = r.capability || {}, a = r.visual_audit || {}, ev = r.evidence || {}, spec = r.design_spec || {}, raw = r.raw_design_spec || {};
    const blockers = approvalBlockers(r, r.instructions);
    const row = (label, value, cls) => h('div', 'verdict', h('span', '', label), h('span', cls, value));
    const wrap = h('div', 'imgwrap');
    if (state.url) { const im = document.createElement('img'); im.src = state.url; im.alt = 'Uploaded image'; wrap.append(im); } else wrap.append(h('div', 'imgph', 'No image in mock mode'));
    (a.openings || []).forEach((o, i) => {
      const [x1, y1, x2, y2] = o.bbox;
      const b = h('div', 'box', String(i + 1));
      b.style.cssText = `left:${x1 / 10}%;top:${y1 / 10}%;width:${(x2 - x1) / 10}%;height:${(y2 - y1) / 10}%`;
      wrap.append(b);
    });
    const im = r.image || {};
    const tbl = h('table', '', h('tr', '', ...['Field', 'First reading', 'Checked result'].map((t) => h('th', '', t))),
      ...diffRows(raw, spec).map((d) => h('tr', d.changed ? 'chg' : '', h('td', '', d.field), h('td', '', d.raw), h('td', '', d.final))));
    const disagree = (raw.port_requirements || []).length === 0 && (a.openings || []).length > 0;

    out.replaceChildren(
      h('h3', '', 'Image and request'), wrap,
      h('p', 'muted', `Input: ${r.input_mode || '?'} · ${im.format || ''} ${im.width || ''}x${im.height || ''} · ${im.bytes || ''} bytes · analysed in ${r.latency_ms ? Math.round(r.latency_ms / 100) / 10 : '?'} s`),
      a.openings && a.openings.length ? h('p', 'muted', 'The red boxes mark the openings found by the second reading.') : '',
      h('p', '', 'Text requirement: ', h('b', '', (r.instructions || '').trim() || '(none)')),
      row('Agent status', c.status || 'unknown', c.status === 'review_required' ? 'warn' : 'bad'),
      row('Can be approved now', blockers.length ? 'no' : 'yes, after your review', blockers.length ? 'bad' : 'ok'),
      ...section('Questions from the agent', c.questions),
      ...section('Not supported yet', (c.unsupported || []).map(describeIssue)),
      ...section('Why a review is needed', c.review_reasons),
      h('h3', '', 'Design spec: first reading and checked result'), h('div', 'tablewrap', tbl), h('p', 'muted', 'Highlighted rows differ between the two.'),
      ...section('What the agent changed, and why', (r.changes || []).map((x) => `${x.field}: ${fmt(x.model)} → ${fmt(x.corrected)}. ${x.reason}`)),
      disagree ? h('p', 'warn', `The two readings disagree: the first found no openings, the second found ${a.openings.length}.`) : '',
      ...section('Visual evidence (first reading)', Object.entries(ev.visual_evidence || {}).map(([k, v]) => `${k}: ${v || '(empty)'}`)),
      ...section('Second reading', [`scene: ${a.scene} (${a.scene_evidence || ''})`, `lid state: ${a.lid_state} (${a.lid_evidence || ''})`, `openings: ${a.opening_certainty}, ${(a.openings || []).length} found`].concat((a.openings || []).map((o, i) => `opening ${i + 1}: ${o.description} (${o.surface})`))),
      ...section('Uncertainties', a.uncertainties),
      ...section('Features outside the design spec', ev.unrepresented_features),
      ...section('Unverified features', r.unverified_features),
      ...section('Open image questions', ev.image_questions),
    );

    const box = h('div', 'approve', h('h3', '', 'Review'));
    if (blockers.length) box.append(h('p', 'err', 'This request cannot be approved yet:'), h('ul', '', ...blockers.map((t) => h('li', '', t))));
    const name = h('input');
    name.type = 'text'; name.maxLength = 80; name.placeholder = 'Your name';
    const btn = h('button', '', 'Approve and generate CAD');
    const msg = h('p', 'muted');
    const sync = () => { btn.disabled = blockers.length > 0 || !name.value.trim() || !env.source_result_sha256; };
    name.oninput = sync; sync();
    btn.onclick = async () => {
      btn.disabled = true; msg.className = 'muted'; msg.textContent = 'Generating... this can take a while.';
      try {
        const resp = useMock
          ? (await sleep(1000), { status: 'generated_after_review', dimensions: { outer_width_mm: 91, outer_length_mm: 62, outer_height_mm: 23.6 } })
          : await post(`/image/${env.task_id}/approve`, { approved: true, reviewer: name.value.trim(), source_result_sha256: env.source_result_sha256 });
        renderApproved(box, env, resp);
      } catch (e) { msg.className = 'err'; msg.textContent = e.message || String(e); sync(); }
    };
    box.append(name, btn, msg);
    out.append(box);
  }

  function renderApproved(box, env, resp) {
    box.replaceChildren(h('h3', '', 'Generated after review'), h('p', 'ok', `Status: ${resp.status}`));
    if (resp.dimensions) box.append(h('p', '', 'Size: ' + Object.entries(resp.dimensions).map(([k, v]) => `${k} ${v}`).join(', ')));
    [['step_url', 'Download STEP', 'step'], ['stl_url', 'Download STL', 'stl']].forEach(([k, label, ext]) => {
      if (!resp[k]) return;
      const b = h('button', 'chip', label);
      b.onclick = () => saveFile(api + resp[k], `${env.task_id}.${ext}`);
      box.append(b);
    });
    if (resp.stl_url) loadSTL(api + resp.stl_url); else box.append(h('p', 'muted', 'Mock mode: no files are generated.'));
  }
  return { addTab };
}
