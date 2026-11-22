# November 20 readiness verification

Evidence root is %LOCALAPPDATA%/PixolidVision/readiness/run-20261120-094545-7fab35.
Historical files remain in their original directories.

## Implemented behavior

The primary extraction preserves its original JSON. A second Qwen3-VL
observation receives pixels without that proposed JSON. It records scene
type, visible floor/cover panels, wall cutout bounding boxes, and uncertainty.
This is a consistency check using the same model, not independent ground
truth. Distinct wall cutouts can restore a missed generic-opening record.
Top cavities cannot be counted as wall ports. Flat/uncertain outlines cannot
establish spatial shape or lid state without explicit accompanying text.
Uncorroborated extra features are logged as unverified and require review.
All image-based CAD remains subject to explicit result-hash-bound approval.

The first audit iteration wrongly counted the top cavity as a port and
overrode correct lid observations. The development/ directory preserves
that failed five-case run. Prompts v0.1.2 and audit v0.1 are preserved.
The final primary Prompt is v0.1.3 and the audit Prompt is v0.1.1.

## Final metrics

| Measure | Existing development cases | New held-out cases |
| --- | --- | --- |
| Cases | 5 | 6, from five new original images |
| Schema passes | 5/5 | 6/6 |
| Primary exact reference fields | 3/5 | 3/6 |
| Checked exact reference fields | 5/5 | 6/6 |
| Primary correct fields | 32/37 | 37/44 |
| Checked correct fields | 37/37 | 44/44 |
| Gate as expected | 5/5 | 5/6 |
| Median two-observation latency | 6.29 s | 6.64 s |

New evaluation fixtures were frozen before inference. Their manifest SHA-256
is 4b18d5b87456ce237a283c7ce63e15cc4d1339c964a7a90e8a89b287f41509c4.
Prompt and semantic policy were not changed after examining these results.
The held-out images still have author-proposed reference labels pending
independent team review. Field scores include only the documented reference
fields and do not validate unrestricted visual interpretation.

The primary still missed three visible openings on EVAL-02. Its audit found
them. Two flat evaluation outlines were overinterpreted by the primary and
corrected to unspecified shape and lid. EVAL-05 had correct reference fields
but an unnecessary audit uncertainty about the image being a 2D projection.
It therefore requested clarification instead of review_required. These
failures and the excessive clarification remain in the reports.

## Demonstration verification

Text-to-CAD and T004 were tested with the unchanged isolated Text Agent over
real HTTP on 8012. The simple request generated STEP/STL, with STEP readback
of one valid 91 x 62 x 22 mm solid. T004 returned unsupported, reported four
unsupported capabilities, never called Geometry, and both downloads were 404.

Qianshun explicitly reviewed and approved the final development IMG-05 result
in this conversation. Approval binds result SHA-256
a4b0394bbbee8b1ba192c1ac6ed6189663e0c694eb61684f97f19d69f6b72ed7.
The approval and approved-image-cad/ directory contain the authorization and
actual CadQuery exports. Readback found one valid 91 x 62 x 22 mm solid with
four hollow PCB standoffs. STL had 4,060 triangles and matching bounds.
Physical fit and printing remain unverified.

The local image page serves on 8011. Real HTTP upload invoked both vision
observations. A negative approval returned 409 and both artifact routes
returned 404. Browser automation did not establish a usable connection,
so the browser click-through is pending manual verification.

Twenty offline image tests and all 46 existing Text Agent tests passed.
Controlled offline responses are distinct from the recorded real inference.
The original team MVP ports were not listening when checked. The demo starts
only its own ports and does not diagnose that inactive state as an app error.

## Remaining work

Review the new reference annotations independently, manually exercise browser
upload and approval, agree Backend request/status/review semantics, and prepare
portable setup instructions for another teammate's computer. Both workspaces
are suitable for Draft PR code review with these limitations disclosed.
Publication approval and formal production integration remain separate steps.

## Final individual QA addendum

The final source review reproduced an approval gap that could bypass
additional review reasons or audit-only features. It also reproduced
non-boolean approval coercion and a stale approval-response display race.
The new assertions failed before the fixes and pass afterward.
The final Image suite has 33 tests. Approval checks now enforce these
boundaries, recheck the uploaded image/result hashes, and validate artifact
hashes before download. The fixed QA API uses port 8021.

Qianshun reports a successful manual browser approval/download for
image_d88c05df71fc4673bbaed6e5f4e80d00. Its actual local result, approval,
image and CAD files are available for this QA. Full browser-level negative
and invalidation paths have subsequently passed real headless Chrome
automation. Manual click evidence is not claimed. Controlled provider and
transport cases remain distinguished from real model inference.

That browser sprint reproduced obsolete completion text after input reset.
The focused regression failed first, then passed after a one-line status
reset. The final 33-test suite and targeted real-browser B/E reruns passed.
Positive native CAD reused the exact previously approved result via CLI;
no new browser approval was fabricated.

The six-case evaluation metrics above remain historical measurements of
the frozen run. The final QA did not retune its labels or extraction policy.
See AGENT_FINAL_PR_READINESS_2026-11-20.md in the local final-QA directory
for current real-model tests, publication scope and remaining team decisions.
