// MOCK data in the same shape as the real backend's POST /design response.
// The numbers are fake until the real board data exists. Switch USE_MOCK in main.js when the backend is ready.
const spec = (o = {}) => ({
  schema_version: '0.1', task_id: 'design_mock', board_id: 'raspberry_pi_4', case_shape: 'rectangular',
  lid: { present: true, style: 'removable' },
  port_requirements: [
    { port_type: 'usb', requested_side: 'front', count: null },
    { port_type: 'ethernet', requested_side: 'front', count: null },
  ],
  mounting: { wall_mount_hole_count: 2 }, wall_thickness_mm: null,
  needs_clarification: false, clarification_questions: [],
  assumptions: ['Board dimensions and connector positions require verified reference data.'], ...o,
});
const geo = (o = {}) => ({
  task_id: 'design_mock', valid: true,
  dimensions: { outer_width_mm: 91, outer_length_mm: 62, outer_height_mm: 21 },
  errors: [], warnings: [], ...o,
});
const questions = [
  "Could you specify the enclosure and board using 'Make a case for Raspberry Pi 4'?",
  'Which supported board should the enclosure fit? The Mock currently recognizes Raspberry Pi 4.',
];
export const MOCKS = {
  generated: { status: 'generated', task_id: 'design_mock', design_spec: spec(), geometry_result: geo() },
  warnings: {
    status: 'generated_with_warnings', task_id: 'design_mock', design_spec: spec(),
    geometry_result: geo({ warnings: ['Using default wall thickness of 2.0 mm.', 'Lid geometry is not implemented yet.', 'Port alignment has not been verified.', 'Wall mounting holes are not implemented yet.'] }),
  },
  blocked: {
    status: 'geometry_blocked', task_id: 'design_mock', design_spec: spec(),
    geometry_result: geo({ valid: false, dimensions: null, errors: ['Unknown or unsupported board: raspberry_pi_4'] }),
  },
  clarify: {
    status: 'needs_clarification', task_id: 'design_mock', questions,
    design_spec: spec({ board_id: null, case_shape: 'unspecified', lid: { present: null, style: 'unspecified' }, port_requirements: [], mounting: { wall_mount_hole_count: null }, needs_clarification: true, clarification_questions: questions }),
  },
};
