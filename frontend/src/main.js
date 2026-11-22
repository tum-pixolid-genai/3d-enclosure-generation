import './style.css';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js';
import { MOCKS } from './mock.js';

const USE_MOCK = !location.search.includes('real'); // open /?real to use the real backend
const API = ''; // later: a Vite proxy forwards /design to the backend
const $ = (id) => document.getElementById(id);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const EXAMPLES = [
  ['No lid (works)', 'Design a rectangular enclosure for Raspberry Pi 4 with no lid.'],
  ['With lid and ports (not supported yet)', 'Make a rectangular case for Raspberry Pi 4 with a removable lid, USB and Ethernet openings on the front, and two wall-mount holes.'],
  ['Needs a review', 'Make a rectangular case for Raspberry Pi 4.'],
  ['Too vague', 'Generate a case for Raspberry Pi 4.'],
];
const STEPS = ['Request', 'Design spec', 'Geometry and checks', 'Result'];

// ---------- page helpers ----------
function add(parent, tag, text, cls) {
  const e = document.createElement(tag);
  if (text !== undefined) e.textContent = text;
  if (cls) e.className = cls;
  parent.appendChild(e);
  return e;
}
function setSteps(n) {
  $('steps').replaceChildren();
  STEPS.forEach((s, i) => add($('steps'), 'li', s, i < n ? 'on' : ''));
}
function list(title, items) {
  if (!items || !items.length) return;
  add($('messages'), 'h3', title);
  const ul = add($('messages'), 'ul');
  items.forEach((t) => add(ul, 'li', t));
}
function verdict(label, text, cls) {
  const row = add($('verdicts'), 'div', undefined, 'verdict');
  add(row, 'span', label);
  add(row, 'span', text, cls);
}
EXAMPLES.forEach(([name, text]) => {
  const b = add($('chips'), 'button', name, 'chip');
  b.onclick = () => { $('prompt').value = text; };
});
$('prompt').value = EXAMPLES[0][1];
setSteps(0);
if (USE_MOCK) add(document.querySelector('header'), 'p', 'Mock mode: the results are fake. Open /?real to use the real backend.').style.color = 'var(--bad)';

// ---------- 3D viewer ----------
const host = $('viewer');
const scene = new THREE.Scene();
scene.background = new THREE.Color(0xf4f5f2);
const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 3000);
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(window.devicePixelRatio);
host.appendChild(renderer.domElement);
scene.add(new THREE.HemisphereLight(0xffffff, 0x8890a0, 1.2));
const sun = new THREE.DirectionalLight(0xffffff, 1.4);
sun.position.set(80, 150, 100);
scene.add(sun, new THREE.GridHelper(400, 40, 0xc4c9c4, 0xe0e3df));
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
let model = null;
camera.position.set(110, 90, 130);
function resize() {
  renderer.setSize(host.clientWidth, host.clientHeight);
  camera.aspect = host.clientWidth / host.clientHeight;
  camera.updateProjectionMatrix();
}
new ResizeObserver(resize).observe(host);
(function loop() { requestAnimationFrame(loop); controls.update(); renderer.render(scene, camera); })();

const material = new THREE.MeshStandardMaterial({ color: 0x2f7f86, roughness: 0.55 });
function setModel(obj) {
  if (model) scene.remove(model);
  model = obj;
  if (!obj) return;
  scene.add(obj);
  const box = new THREE.Box3().setFromObject(obj);
  const c = box.getCenter(new THREE.Vector3());
  const s = box.getSize(new THREE.Vector3()).length();
  controls.target.copy(c);
  camera.position.copy(c).add(new THREE.Vector3(0.8, 0.7, 1).multiplyScalar(s));
}
// Stand-in case (open-top box from 5 slabs) built from the checked dimensions, until the backend serves a real STL.
function sampleCase(w, l, h, t) {
  const g = new THREE.Group();
  const slab = (sx, sy, sz, x, y, z) => {
    const m = new THREE.Mesh(new THREE.BoxGeometry(sx, sy, sz), material);
    m.position.set(x, y, z);
    g.add(m);
  };
  const wallH = h - t, midY = t + wallH / 2;
  slab(w, t, l, 0, t / 2, 0);
  slab(w, wallH, t, 0, midY, (l - t) / 2);
  slab(w, wallH, t, 0, midY, -(l - t) / 2);
  slab(t, wallH, l - 2 * t, (w - t) / 2, midY, 0);
  slab(t, wallH, l - 2 * t, -(w - t) / 2, midY, 0);
  return g;
}
function loadSTL(url) { // loads the real model from the backend (model_url)
  new STLLoader().load(url, (geo) => {
    geo.rotateX(-Math.PI / 2); // CAD is Z-up, three.js is Y-up
    geo.computeBoundingBox();
    const b = geo.boundingBox;
    geo.translate(-(b.min.x + b.max.x) / 2, -b.min.y, -(b.min.z + b.max.z) / 2); // centre it, bottom on the grid
    setModel(new THREE.Mesh(geo, material));
  }, undefined, (e) => list('Could not load the model', [String((e && e.message) || e)]));
}
$('download').textContent = 'Download STEP';
const stlBtn = add($('download').parentElement, 'button', 'Download STL', 'chip');
stlBtn.disabled = true;

// ---------- backend ----------
if (!USE_MOCK) { // show whether the real backend is reachable
  const label = document.querySelector('.mock');
  label.textContent = 'Real backend: checking...';
  fetch(`${API}/health`).then((r) => r.json())
    .then(() => { label.textContent = 'Real backend: online'; })
    .catch(() => { label.textContent = 'Real backend: not reachable. Is it running?'; });
}
async function fetchDesign(prompt) {
  if (USE_MOCK) { await sleep(1800); return structuredClone(MOCKS[$('scenario').value]); }
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 150000);
  try {
    const r = await fetch(`${API}/design`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ prompt }), signal: ctrl.signal,
    });
    if (!r.ok) {
    let msg = `The backend answered with status ${r.status}.`;
    try {
      const d = (await r.json()).detail;
      if (Array.isArray(d)) msg = 'Please enter a longer request (at least 10 characters).';
      else if (d && d.message) msg = d.message;
      else if (typeof d === 'string') msg = d;
    } catch (e) { /* keep the generic message */ }
    throw new Error(msg);
  }
    return await r.json();
  } catch (e) {
    if (e.name === 'AbortError') throw new Error('The backend did not answer within 150 seconds. Is it still running?');
    throw e;
  } finally { clearTimeout(timer); }
}

function saveFile(url, name) {
  const a = document.createElement('a');
  a.href = url; a.download = name;
  document.body.appendChild(a); a.click(); a.remove();
}

// ---------- show a result ----------
const yesNo = (v) => (v === null || v === undefined ? 'unspecified' : v ? 'yes' : 'no');
function showSpec(s) {
  $('spec').replaceChildren();
  const ports = s.port_requirements.map((p) => `${p.port_type} (${p.requested_side}${p.count ? ', x' + p.count : ''})`).join(', ');
  [
    ['Board', s.board_id ?? 'unknown'],
    ['Shape', s.case_shape],
    ['Lid', s.lid.present ? `yes, ${s.lid.style}` : yesNo(s.lid.present)],
    ['Openings', ports || 'none'],
    ['Wall-mount holes', s.mounting.wall_mount_hole_count ?? 'unspecified'],
    ['Wall thickness', s.wall_thickness_mm ? `${s.wall_thickness_mm} mm` : 'default (2.0 mm)'],
  ].forEach(([k, v]) => { add($('spec'), 'dt', k); add($('spec'), 'dd', String(v)); });
  $('raw').textContent = JSON.stringify(s, null, 2);
}
function describeIssue(i) {
  const names = {
    unsupported_board: () => `Board not supported: ${i.board_id}`,
    unsupported_shape: () => `Shape not supported: ${i.shape}`,
    lid: () => `Lid (${i.style})`,
    port_opening: () => `${i.port_type} opening (${i.requested_side})`,
    external_wall_mount_holes: () => `${i.count} wall-mount hole(s)`,
  };
  return (names[i.code] || (() => i.code))();
}
function show(data) {
  const g = data.geometry_result;
  const cap = data.capability || null;
  const questions = data.questions || (cap && cap.questions) || [];
  setSteps(4);
  $('verdicts').replaceChildren();
  $('messages').replaceChildren();
  verdict('AI says the case works', 'not reported yet', 'na'); // filled in once Retry exists
  if (!g) {
    const why = { unsupported: 'not run: request not supported yet', review_required: 'not run: needs a review' }[data.status];
    verdict('Automatic checks', why || 'not run', why ? 'warn' : 'na');
  }
  else if (g.valid) verdict('Automatic checks', g.warnings.length ? 'passed, with warnings' : 'passed', g.warnings.length ? 'warn' : 'ok');
  else verdict('Automatic checks', 'failed', 'bad');
  verdict('Printed and tested', 'not tested', 'na');
  list('Questions from the AI', questions);
  list('Not supported yet', cap && (cap.unsupported || []).map(describeIssue));
  list('Why a review is needed', data.status === 'needs_clarification' ? [] : cap && cap.review_reasons);
  list('Errors', g && g.errors);
  list('Warnings', g && g.warnings);
  list('Assumptions', data.design_spec && data.design_spec.assumptions);
  if (data.design_spec) showSpec(data.design_spec);

  const d = g && g.dimensions;
  if (d && g.valid) {
    const wall = data.design_spec.wall_thickness_mm || 2;
    if (data.model_url) loadSTL(API + data.model_url); // the real model from the backend
    else setModel(sampleCase(d.outer_width_mm, d.outer_length_mm, d.outer_height_mm, wall)); // stand-in (mock mode)
    $('dims').textContent = `${d.outer_width_mm} x ${d.outer_length_mm} x ${d.outer_height_mm} mm`;
  } else { setModel(null); $('dims').textContent = ''; }

  const ok = g && g.valid && !USE_MOCK;
  $('download').disabled = !ok;
  $('download').title = USE_MOCK ? 'Available once the backend is connected' : '';
  stlBtn.disabled = USE_MOCK || !data.model_url;
  stlBtn.onclick = () => saveFile(API + data.model_url, `${data.task_id}.stl`);
  $('download').onclick = () => saveFile(`${API}/design/${data.task_id}/download`, `${data.task_id}.step`);
}

$('go').onclick = async () => {
  $('go').disabled = true;
  $('verdicts').replaceChildren();
  $('messages').replaceChildren();
  setModel(null); $('dims').textContent = '';
  $('download').disabled = true; stlBtn.disabled = true;
  setSteps(1);
  const hint = setTimeout(() => list('Still working', ['A request to the real language model can take up to a minute or two.']), 8000);
  const timer = setTimeout(() => setSteps(2), 900);
  try {
    show(await fetchDesign($('prompt').value));
  } catch (e) {
    setSteps(0);
    $('messages').replaceChildren();
    list('Something went wrong', [e.message || String(e)]);
  } finally {
    clearTimeout(timer);
    clearTimeout(hint);
    $('go').disabled = false;
  }
};
