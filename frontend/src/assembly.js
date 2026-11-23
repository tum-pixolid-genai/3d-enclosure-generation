// Pi 4 assembly tab: calls POST /design/pi4-assembly (no request body) and shows the verification result.
// Response shape (backend/pi4_assembly_routes.py on integration/pi4-assembly):
//   { task_id, status: 'generated' | 'geometry_blocked', assembly_validated, verification_summary,
//     verification_metrics: { baseline_collision_mm3, collision_volume_mm3, mounting_hole_alignment_verified,
//                             mounting_hole_max_deviation_mm, lid_fasteners_aligned, lid_fastener_count },
//     downloads?: { enclosure, lid, report, enclosure_stl, lid_stl }   // only when validated
//   }
// Errors: 503 (reference STEP missing on the backend computer), 500 (generation failed).

const h = (tag, cls, ...kids) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  e.append(...kids.flat().filter((k) => k !== null && k !== undefined));
  return e;
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const yes = (v) => (v === true ? 'yes' : v === false ? 'no' : 'not reported');
const num = (v, unit) => (typeof v === 'number' ? `${Math.round(v * 1000) / 1000} ${unit}` : 'not reported');

// Mock results: same shape as the real response, numbers from Shanning's local run (2026-11-22).
const MOCKS = {
  validated: {
    task_id: 'pi4_mock',
    status: 'generated',
    assembly_validated: true,
    verification_summary: { assembly_validated: true },
    verification_metrics: {
      baseline_collision_mm3: 230.322109, collision_volume_mm3: 0,
      mounting_hole_alignment_verified: true, mounting_hole_max_deviation_mm: 0,
      lid_fasteners_aligned: true, lid_fastener_count: 4,
    },
    downloads: {},
  },
  blocked: {
    task_id: 'pi4_mock',
    status: 'geometry_blocked',
    assembly_validated: false,
    verification_summary: { assembly_validated: false },
    verification_metrics: {
      baseline_collision_mm3: 230.322109, collision_volume_mm3: 12.5,
      mounting_hole_alignment_verified: false, mounting_hole_max_deviation_mm: null,
      lid_fasteners_aligned: false, lid_fastener_count: 4,
    },
  },
};

export function initAssembly({ api, useMock, addTab, loadAssembly, standInAssembly, saveFile, setDims }) {
  const panel = h('div');
  const go = h('button', '', 'Run Pi 4 assembly check');
  const sel = h('select');
  [['validated', 'Validated'], ['blocked', 'Blocked by geometry']].forEach(([k, t]) => { const o = h('option', '', t); o.value = k; sel.append(o); });
  const out = h('div');
  panel.append(
    h('p', '', 'Builds the reference case for a Raspberry Pi 4 from its STEP model: openings for the connectors are cut automatically (0.5 mm clearance), the lid is fastened with four screws. The result is then checked for collisions and hole alignment.'),
    h('p', 'muted', 'No text request is needed. The backend needs the reference STEP file on its computer (see the backend README).'),
    h('div', 'row', go, useMock ? h('label', 'mock', 'Mock result ', sel) : ''),
    out,
  );
  addTab('Pi 4 assembly', panel, () => setDims(''));

  async function call() {
    if (useMock) { await sleep(1500); return structuredClone(MOCKS[sel.value]); }
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 150000);
    try {
      const r = await fetch(`${api}/design/pi4-assembly`, { method: 'POST', signal: ctrl.signal });
      if (!r.ok) {
        let msg = `The backend answered with status ${r.status}.`;
        try { const d = (await r.json()).detail; if (typeof d === 'string') msg = d; else if (d && d.message) msg = d.message; } catch (e) { /* keep generic */ }
        if (r.status === 503) msg += ' The backend computer needs the Raspberry Pi 4 reference STEP file (see the backend README).';
        throw new Error(msg);
      }
      return await r.json();
    } catch (e) {
      if (e.name === 'AbortError') throw new Error('The backend did not answer within 150 seconds. Is it still running?');
      throw e;
    } finally { clearTimeout(timer); }
  }

  go.onclick = async () => {
    go.disabled = true;
    out.replaceChildren(h('p', 'muted', 'Working... the CAD checks can take a little while.'));
    try { await render(await call()); } catch (e) { out.replaceChildren(h('p', 'err', e.message || String(e))); } finally { go.disabled = false; }
  };

  async function render(d) {
    const m = d.verification_metrics || {};
    const ok = d.assembly_validated === true;
    const row = (label, value, cls) => h('div', 'verdict', h('span', '', label), h('span', cls, value));
    const metrics = [
      ['Collision with the board before the openings', num(m.baseline_collision_mm3, 'mm³')],
      ['Collision after the openings', num(m.collision_volume_mm3, 'mm³')],
      ['Board mounting holes aligned with the model', yes(m.mounting_hole_alignment_verified)],
      ['Largest mounting-hole deviation', num(m.mounting_hole_max_deviation_mm, 'mm')],
      ['Lid screw holes aligned with the case posts', yes(m.lid_fasteners_aligned)],
      ['Number of lid screw holes', m.lid_fastener_count ?? 'not reported'],
    ];
    const table = h('table', '', ...metrics.map(([k, v]) => h('tr', '', h('td', '', k), h('td', '', String(v)))));
    const dl = h('div', 'row');
    const views = h('div', 'row');
    out.replaceChildren(
      row('Automatic checks (CAD)', ok ? 'passed' : 'failed', ok ? 'ok' : 'bad'),
      row('Printed and tested', 'not tested', 'na'),
      h('p', 'muted', `Status: ${d.status || 'unknown'} · task ${d.task_id || ''}`),
      h('h3', '', 'Verification'), h('div', 'tablewrap', table),
      h('details', '', h('summary', '', 'Full verification summary'), h('pre', '', JSON.stringify(d.verification_summary ?? null, null, 2))),
      h('p', 'muted', 'The checks cover CAD geometry and collisions only. Screw fit, connector access and printing tolerances are not verified.'),
      views, dl,
    );
    if (!ok) {
      out.append(h('p', 'err', 'No files are offered: the backend only publishes files when all checks pass.'));
      return;
    }
    const files = d.downloads || {};
    [['enclosure', 'STEP case', 'step'], ['lid', 'STEP lid', 'step'], ['enclosure_stl', 'STL case', 'stl'], ['lid_stl', 'STL lid', 'stl'], ['report', 'Report (JSON)', 'json']].forEach(([k, label, ext]) => {
      const b = h('button', 'chip', 'Download ' + label);
      if (!files[k] || useMock) { b.disabled = true; b.title = useMock ? 'Available once the backend is connected' : 'Not offered by the backend'; }
      b.onclick = () => saveFile(api + files[k], `${d.task_id}_${k}.${ext}`);
      dl.append(b);
    });
    // 3D view of case and lid
    let setView = null;
    try {
      if (useMock) setView = standInAssembly(91, 62, 23.6, 2);
      else if (files.enclosure_stl && files.lid_stl) setView = await loadAssembly(api + files.enclosure_stl, api + files.lid_stl);
    } catch (e) { out.append(h('p', 'err', e.message)); }
    if (setView) {
      [['closed', 'Case and lid'], ['exploded', 'Lid lifted'], ['enclosure', 'Case only'], ['lid', 'Lid only']].forEach(([mode, label]) => {
        const b = h('button', 'chip', label);
        b.onclick = () => setView(mode);
        views.append(b);
      });
      setView('closed');
    }
  }
}
