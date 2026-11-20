# Image-to-Design integration handoff

Prepared for Peicen Xu and Shanning Xu on 2026-11-20.

## Call and contract

From this isolated project root:

    from image_agent.vision_agent import VisionAgent
    result = VisionAgent(port=11443).extract(
        image_path, task_id=backend_task_id, instructions=optional_english_text)

Input is a local PNG/JPEG, 10 MiB maximum, 16..2048 pixels per side, plus
optional text up to 2000 characters. Backend must validate and isolate
uploads, assign a unique task ID, and retain the original image hash.
The model receives pixels and instructions, with no reference labels.

result.design_spec is the unchanged Design Spec v0.1. Result metadata,
raw model draft, audit observation, evidence, semantic changes, token usage,
and capability decision belong outside that shared output object.
input_mode distinguishes image_only from image_plus_text.

The current primary Prompt is vision_v0.1.3. A separate visual inventory
uses visual_audit_v0.1.1. Both observations use the same fallible Qwen3-VL
model. The inventory has no access to the proposed JSON. It distinguishes
exterior wall cutouts from the top cavity and spatial scenes from flat outlines.

## Response and review

| Result | Backend behavior |
| --- | --- |
| clarification_required | Return questions and unsupported details. No CAD. |
| unsupported | Report each unsupported capability. No CAD. |
| review_required | Display image, exact final JSON, evidence, corrections, and limitations. Require explicit review approval before CAD. |
| Model error | Return an explicit error and preserve its raw reply where available. No Mock fallback or CAD. |
| Approved supported draft | Revalidate Schema and capabilities, invoke Geometry, validate exports, then publish task-specific URLs. |

Even a correct supported image draft has allow_geometry=false until review.
Approval must bind a reviewer and affirmative decision to the SHA-256 of
the exact result file. Changed or unapproved results are blocked. A new
upload resets review. Runtime publication tracks completed tasks, not just
files that happen to exist.

Example review response:

    {"task_id":"image_unique_id","source_result_sha256":"<64 hex characters>",
     "result":{"design_spec":{"schema_version":"0.1","task_id":"image_unique_id",
       "board_id":"raspberry_pi_4","case_shape":"rectangular",
       "lid":{"present":false,"style":"unspecified"},"port_requirements":[],
       "mounting":{"wall_mount_hole_count":null},"wall_thickness_mm":2,
       "needs_clarification":false,"clarification_questions":[],
       "assumptions":["Image interpretation does not verify physical fit."]},
       "capability":{"status":"review_required","allow_geometry":false}}}

The local demo accepts JSON containing filename, image_base64, and
instructions at POST /image. POST /image/{task}/approve requires
approved=true, reviewer, and source_result_sha256. Invalid input maps to
422, service transport errors to 503, and invalid model output to 502.
Peicen should agree the production API envelope and error/status mappings.

## Geometry and reference data

Shanning should confirm supported lid/port/mount features, board registry,
coordinates, dimensions, and checks. Pixel appearance supplies no engineering
scale or verified board identity. Board type and wall thickness require
explicit text in this version. Generic cutouts have unknown connector type
and unspecified physical side until clarified. Apparent absence in a view
does not verify hidden sides. Physical fit and printing remain separate tests.

## Minimum integration regression

Test an image-only open box, a cover, generic openings, a flat ambiguous
outline, and a supported image plus explicit Pi 4/wall text. Verify raw and
corrected results separately. Test malformed image/model responses and
service failure. Before review, downloads must return 404. A missing,
negative, or stale-hash approval must never call CAD. After a valid reviewed
supported request, verify STEP readback, STL dimensions, and task-specific
downloads. A conflicting or unsupported request remains blocked after an
approval attempt.

Historical evidence includes 20 offline image tests and a separate six-case
held-out evaluation. On those six cases, primary extraction matched all
reference fields in 3/6 and checked output in 6/6. A valid case was
over-clarified, giving 5/6 expected gate decisions. Synthetic reference
labels still need independent teammate review. These results are small-sample
evidence for review, not unrestricted vision reliability.

Use READINESS_DEMO.md for exact local commands and evidence locations.

## Final QA addendum

The final suite has 33 tests, including synthetic loopback HTTP lifecycle
tests and a Node test of the actual page handlers. These do not represent
manual browser clicks or real model accuracy. Original primary/audit
Prompts, holdout labels, and old responses remain unchanged.

Approval now requires a literal JSON boolean. The exact result and uploaded
image hashes are rechecked before processing approval. Human approval cannot
override other capability review reasons, outstanding questions, or
uncorroborated visual features. Downloaded artifacts are checked against the
published task's export hashes. The page ignores stale approval responses
after the input view changes.

Reviewer identity is a local audit alias, not an authenticated user account
or a production authorization mechanism. Personal reviewer names and full
approval/runtime records should stay outside the public PR.

Use QA port 8021 for the corrected running instance. An older 8011 Python
process needs a deliberate restart before it picks up server-side fixes.
Backend should implement an explicit production injection interface, review
identity policy, concurrency and artifact lifecycle. These local demo
endpoints do not define a new shared production API.

The subsequent automated acceptance used existing Playwright and real
headless Chrome. Groups A through E passed, including invalidation and
negative browser paths; controlled provider/transport cases are recorded
separately from real vision inference. The only subsequent behavior fix
clears stale completion text on input reset. Native positive regression
replayed the exact pre-existing approved result through CLI. No production
Frontend/Backend ownership or new image approval is implied.

For lightweight extraction install requirements.txt. Optional review API
tests additionally use requirements-qa.txt and Node.js. CAD is imported
only for an approved native test and depends on the separate team stack.

Set PIXOLID_INTEGRATION_ROOT before startup to select a source directory
containing backend/ and geometry/. Both component worktrees and a combined
repository layout are supported. The proposed public layout reuses root
agent/ from the Text branch, omits shared/, and places image requirements
under image_agent/. Historical local orchestration scripts and private
evaluation cases are not part of that minimal PR. See IMAGE_README.md for
the publication mapping; this workspace still names that file README.md.
