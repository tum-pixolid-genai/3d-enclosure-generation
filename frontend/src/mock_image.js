// Mock data for the image review page: four REAL outputs of the Image Agent (provided by Qianshun).
// Each one is the `result` object that the backend wraps in {task_id, source_result_sha256, result}.
export const EXAMPLE_LABELS = {
  "review": "Image + text: can be approved",
  "openings": "Image only: openings seen, info missing",
  "outline": "Image only: flat outline",
  "lid": "Image only: lid, clarification needed"
};
export const EXAMPLES = {
 "review": {
  "task_id": "IMG-05",
  "design_spec": {
   "schema_version": "0.1",
   "task_id": "IMG-05",
   "board_id": "raspberry_pi_4",
   "case_shape": "rectangular",
   "lid": {
    "present": false,
    "style": "unspecified"
   },
   "port_requirements": [],
   "mounting": {
    "wall_mount_hole_count": null
   },
   "wall_thickness_mm": 2.0,
   "needs_clarification": false,
   "clarification_questions": [],
   "assumptions": [
    "Image interpretation does not verify dimensions, physical fit, or printability."
   ]
  },
  "raw_design_spec": {
   "schema_version": "0.1",
   "task_id": "IMG-05",
   "board_id": "raspberry_pi_4",
   "case_shape": "rectangular",
   "lid": {
    "present": false,
    "style": "unspecified"
   },
   "port_requirements": [],
   "mounting": {
    "wall_mount_hole_count": null
   },
   "wall_thickness_mm": 2,
   "needs_clarification": false,
   "clarification_questions": [],
   "assumptions": [
    "Image interpretation does not verify dimensions, physical fit, or printability."
   ]
  },
  "raw_reply": "{\n  \"design\": {\n    \"board_id\": \"raspberry_pi_4\",\n    \"case_shape\": \"rectangular\",\n    \"lid\": {\n      \"present\": false,\n      \"style\": \"unspecified\"\n    },\n    \"port_requirements\": [],\n    \"mounting\": {\n      \"wall_mount_hole_count\": null\n    },\n    \"wall_thickness_mm\": 2,\n    \"needs_clarification\": false,\n    \"clarification_questions\": []\n  },\n  \"visual_evidence\": {\n    \"case_shape\": \"rectangular enclosure with open top\",\n    \"lid\": \"absent\",\n    \"port_requirements\": \"none visible\",\n    \"mounting\": \"no external mounting holes visible\"\n  },\n  \"unrepresented_features\": [],\n  \"image_questions\": []\n}",
  "evidence": {
   "visual_evidence": {
    "case_shape": "rectangular enclosure with open top",
    "lid": "absent",
    "port_requirements": "none visible",
    "mounting": "no external mounting holes visible"
   },
   "unrepresented_features": [],
   "image_questions": []
  },
  "changes": [],
  "capability": {
   "status": "review_required",
   "allow_geometry": false,
   "unsupported": [],
   "questions": [],
   "review_reasons": [
    "Visual requirements need independent review before CAD."
   ],
   "unrepresented_features": []
  },
  "image": {
   "sha256": "d377f7ab247a9dd1239685837e1484fb290be026e7ec367ef1fd073dfb3e75da",
   "bytes": 5192,
   "width": 640,
   "height": 480,
   "format": "PNG"
  },
  "visual_audit": {
   "scene": "enclosure_3d",
   "scene_evidence": "A 3D enclosure with a visible interior cavity and exterior walls. The top is open, revealing the interior floor and rim. No cover panel is visible on the top. The interior floor is visible as a flat surface within the cavity.",
   "lid_state": "open",
   "lid_evidence": "The top is open, with no cover panel visible. The interior floor and rim are visible, indicating an open cavity.",
   "cover_panel_visible": false,
   "interior_floor_visible": true,
   "opening_certainty": "none",
   "openings": [],
   "other_features": [],
   "uncertainties": []
  },
  "audit_raw_reply": "{\n  \"scene\": \"enclosure_3d\",\n  \"scene_evidence\": \"A 3D enclosure with a visible interior cavity and exterior walls. The top is open, revealing the interior floor and rim. No cover panel is visible on the top. The interior floor is visible as a flat surface within the cavity.\",\n  \"lid_state\": \"open\",\n  \"lid_evidence\": \"The top is open, with no cover panel visible. The interior floor and rim are visible, indicating an open cavity.\",\n  \"cover_panel_visible\": false,\n  \"interior_floor_visible\": true,\n  \"opening_certainty\": \"none\",\n  \"openings\": [],\n  \"other_features\": [],\n  \"uncertainties\": []\n}",
  "unverified_features": [],
  "input_mode": "image_plus_text",
  "audit_usage": {
   "total_duration": 2239660700,
   "load_duration": 4527000,
   "prompt_eval_count": 1414,
   "prompt_eval_duration": 37923000,
   "eval_count": 156,
   "eval_duration": 2034266000,
   "done_reason": "stop"
  },
  "instructions": "Make a rectangular case for Raspberry Pi 4 with no lid; 2 mm wall thickness.",
  "usage": {
   "total_duration": 2936316100,
   "load_duration": 5413500,
   "prompt_eval_count": 1687,
   "prompt_eval_duration": 646972000,
   "eval_count": 167,
   "eval_duration": 2129960000,
   "done_reason": "stop"
  },
  "latency_ms": 5193.078,
  "schema_valid": true
 },
 "openings": {
  "task_id": "IMG-03",
  "design_spec": {
   "schema_version": "0.1",
   "task_id": "IMG-03",
   "board_id": null,
   "case_shape": "rectangular",
   "lid": {
    "present": false,
    "style": "unspecified"
   },
   "port_requirements": [
    {
     "port_type": "unknown",
     "requested_side": "unspecified",
     "count": 2
    }
   ],
   "mounting": {
    "wall_mount_hole_count": null
   },
   "wall_thickness_mm": null,
   "needs_clarification": true,
   "clarification_questions": [
    "Please identify the observed openings and confirm their count and physical side.",
    "Which exact board should this enclosure fit? Its type cannot be determined from appearance.",
    "Please identify the connector type and physical side for unknown openings."
   ],
   "assumptions": [
    "Image interpretation does not verify dimensions, physical fit, or printability."
   ]
  },
  "raw_design_spec": {
   "schema_version": "0.1",
   "task_id": "IMG-03",
   "board_id": null,
   "case_shape": "rectangular",
   "lid": {
    "present": false,
    "style": "unspecified"
   },
   "port_requirements": [],
   "mounting": {
    "wall_mount_hole_count": null
   },
   "wall_thickness_mm": null,
   "needs_clarification": false,
   "clarification_questions": [],
   "assumptions": [
    "Image interpretation does not verify dimensions, physical fit, or printability."
   ]
  },
  "raw_reply": "{\n  \"design\": {\n    \"board_id\": null,\n    \"case_shape\": \"rectangular\",\n    \"lid\": {\n      \"present\": false,\n      \"style\": \"unspecified\"\n    },\n    \"port_requirements\": [],\n    \"mounting\": {\n      \"wall_mount_hole_count\": null\n    },\n    \"wall_thickness_mm\": null,\n    \"needs_clarification\": false,\n    \"clarification_questions\": []\n  },\n  \"visual_evidence\": {\n    \"case_shape\": \"rectangular enclosure with open top and bottom\",\n    \"lid\": \"no lid visible\",\n    \"port_requirements\": \"no visible openings or port requirements\",\n    \"mounting\": \"no external mounting holes visible\"\n  },\n  \"unrepresented_features\": [],\n  \"image_questions\": []\n}",
  "evidence": {
   "visual_evidence": {
    "case_shape": "rectangular enclosure with open top and bottom",
    "lid": "no lid visible",
    "port_requirements": "no visible openings or port requirements",
    "mounting": "no external mounting holes visible"
   },
   "unrepresented_features": [],
   "image_questions": []
  },
  "changes": [
   {
    "field": "port_requirements",
    "model": [],
    "corrected": [
     {
      "port_type": "unknown",
      "requested_side": "unspecified",
      "count": 2
     }
    ],
    "reason": "A separate pixel inventory identified distinct generic openings."
   },
   {
    "field": "clarification_questions",
    "model": [
     "Please identify the observed openings and confirm their count and physical side."
    ],
    "corrected": [
     "Please identify the observed openings and confirm their count and physical side.",
     "Which exact board should this enclosure fit? Its type cannot be determined from appearance.",
     "Please identify the connector type and physical side for unknown openings."
    ],
    "reason": "Conservative evidence questions."
   }
  ],
  "capability": {
   "status": "clarification_required",
   "allow_geometry": false,
   "unsupported": [
    {
     "code": "port_opening",
     "port_type": "unknown",
     "requested_side": "unspecified",
     "count": 2
    }
   ],
   "questions": [
    "Please identify the observed openings and confirm their count and physical side.",
    "Which exact board should this enclosure fit? Its type cannot be determined from appearance.",
    "Please identify the connector type and physical side for unknown openings."
   ],
   "review_reasons": [
    "Board and enclosure shape must be known.",
    "The original request is required for automatic generation."
   ],
   "unrepresented_features": []
  },
  "image": {
   "sha256": "9d46cf2abe26085996ca6daf2b1e089f08d6fceba905b598c20fe18e0d079ca4",
   "bytes": 5471,
   "width": 640,
   "height": 480,
   "format": "PNG"
  },
  "visual_audit": {
   "scene": "enclosure_3d",
   "scene_evidence": "A rectangular enclosure with an open top and visible interior floor. The exterior walls are light blue with two dark rectangular cutouts on the front face. The interior cavity is visible, with no cover panel present.",
   "lid_state": "open",
   "lid_evidence": "The top is open, revealing the interior floor and rim. There is no separate cover panel or lid visible.",
   "cover_panel_visible": false,
   "interior_floor_visible": true,
   "opening_certainty": "clear",
   "openings": [
    {
     "description": "Dark rectangular cutout on the front exterior wall, positioned on the left side.",
     "surface": "exterior_wall",
     "bbox": [
      470,
      600,
      580,
      700
     ]
    },
    {
     "description": "Dark rectangular cutout on the front exterior wall, positioned on the right side.",
     "surface": "exterior_wall",
     "bbox": [
      640,
      530,
      750,
      650
     ]
    }
   ],
   "other_features": [],
   "uncertainties": []
  },
  "audit_raw_reply": "{\n  \"scene\": \"enclosure_3d\",\n  \"scene_evidence\": \"A rectangular enclosure with an open top and visible interior floor. The exterior walls are light blue with two dark rectangular cutouts on the front face. The interior cavity is visible, with no cover panel present.\",\n  \"lid_state\": \"open\",\n  \"lid_evidence\": \"The top is open, revealing the interior floor and rim. There is no separate cover panel or lid visible.\",\n  \"cover_panel_visible\": false,\n  \"interior_floor_visible\": true,\n  \"opening_certainty\": \"clear\",\n  \"openings\": [\n    {\n      \"description\": \"Dark rectangular cutout on the front exterior wall, positioned on the left side.\",\n      \"surface\": \"exterior_wall\",\n      \"bbox\": [\n        470,\n        600,\n        580,\n        700\n      ]\n    },\n    {\n      \"description\": \"Dark rectangular cutout on the front exterior wall, positioned on the right side.\",\n      \"surface\": \"exterior_wall\",\n      \"bbox\": [\n        640,\n        530,\n        750,\n        650\n      ]\n    }\n  ],\n  \"other_features\": [],\n  \"uncertainties\": []\n}",
  "unverified_features": [],
  "input_mode": "image_only",
  "audit_usage": {
   "total_duration": 4389567700,
   "load_duration": 13824800,
   "prompt_eval_count": 1414,
   "prompt_eval_duration": 785211000,
   "eval_count": 278,
   "eval_duration": 3453625000,
   "done_reason": "stop"
  },
  "instructions": "",
  "usage": {
   "total_duration": 3121831300,
   "load_duration": 7615700,
   "prompt_eval_count": 1668,
   "prompt_eval_duration": 680743000,
   "eval_count": 167,
   "eval_duration": 2247328000,
   "done_reason": "stop"
  },
  "latency_ms": 7528.837,
  "schema_valid": true
 },
 "outline": {
  "task_id": "IMG-04",
  "design_spec": {
   "schema_version": "0.1",
   "task_id": "IMG-04",
   "board_id": null,
   "case_shape": "unspecified",
   "lid": {
    "present": null,
    "style": "unspecified"
   },
   "port_requirements": [],
   "mounting": {
    "wall_mount_hole_count": null
   },
   "wall_thickness_mm": null,
   "needs_clarification": true,
   "clarification_questions": [
    "Please clarify the three-dimensional shape and whether the image shows a lid or open cavity.",
    "No depth or 3D structure is visible; the outline is ambiguous as to whether it represents a 2D shape or a 3D object with hidden surfaces.",
    "Which exact board should this enclosure fit? Its type cannot be determined from appearance.",
    "Which enclosure shape is intended by the image?",
    "Does the image require an open top or a lid?"
   ],
   "assumptions": [
    "Image interpretation does not verify dimensions, physical fit, or printability."
   ]
  },
  "raw_design_spec": {
   "schema_version": "0.1",
   "task_id": "IMG-04",
   "board_id": null,
   "case_shape": "rectangular",
   "lid": {
    "present": false,
    "style": "unspecified"
   },
   "port_requirements": [],
   "mounting": {
    "wall_mount_hole_count": null
   },
   "wall_thickness_mm": null,
   "needs_clarification": false,
   "clarification_questions": [],
   "assumptions": [
    "Image interpretation does not verify dimensions, physical fit, or printability."
   ]
  },
  "raw_reply": "{\n  \"design\": {\n    \"board_id\": null,\n    \"case_shape\": \"rectangular\",\n    \"lid\": {\n      \"present\": false,\n      \"style\": \"unspecified\"\n    },\n    \"port_requirements\": [],\n    \"mounting\": {\n      \"wall_mount_hole_count\": null\n    },\n    \"wall_thickness_mm\": null,\n    \"needs_clarification\": false,\n    \"clarification_questions\": []\n  },\n  \"visual_evidence\": {\n    \"case_shape\": \"rectangular with rounded corners\",\n    \"lid\": \"no visible lid or closure mechanism\",\n    \"port_requirements\": \"no visible openings or port requirements\",\n    \"mounting\": \"no visible mounting holes or attachment points\"\n  },\n  \"unrepresented_features\": [],\n  \"image_questions\": []\n}",
  "evidence": {
   "visual_evidence": {
    "case_shape": "rectangular with rounded corners",
    "lid": "no visible lid or closure mechanism",
    "port_requirements": "no visible openings or port requirements",
    "mounting": "no visible mounting holes or attachment points"
   },
   "unrepresented_features": [],
   "image_questions": []
  },
  "changes": [
   {
    "field": "case_shape",
    "model": "rectangular",
    "corrected": "unspecified",
    "reason": "Independent observation does not establish spatial geometry."
   },
   {
    "field": "lid",
    "model": {
     "present": false,
     "style": "unspecified"
    },
    "corrected": {
     "present": null,
     "style": "unspecified"
    },
    "reason": "A flat outline cannot establish a cavity or lid."
   },
   {
    "field": "clarification_questions",
    "model": [
     "Please clarify the three-dimensional shape and whether the image shows a lid or open cavity.",
     "No depth or 3D structure is visible; the outline is ambiguous as to whether it represents a 2D shape or a 3D object with hidden surfaces."
    ],
    "corrected": [
     "Please clarify the three-dimensional shape and whether the image shows a lid or open cavity.",
     "No depth or 3D structure is visible; the outline is ambiguous as to whether it represents a 2D shape or a 3D object with hidden surfaces.",
     "Which exact board should this enclosure fit? Its type cannot be determined from appearance.",
     "Which enclosure shape is intended by the image?",
     "Does the image require an open top or a lid?"
    ],
    "reason": "Conservative evidence questions."
   }
  ],
  "capability": {
   "status": "clarification_required",
   "allow_geometry": false,
   "unsupported": [],
   "questions": [
    "Please clarify the three-dimensional shape and whether the image shows a lid or open cavity.",
    "No depth or 3D structure is visible; the outline is ambiguous as to whether it represents a 2D shape or a 3D object with hidden surfaces.",
    "Which exact board should this enclosure fit? Its type cannot be determined from appearance.",
    "Which enclosure shape is intended by the image?",
    "Does the image require an open top or a lid?"
   ],
   "review_reasons": [
    "Board and enclosure shape must be known.",
    "The automatic path requires an explicit no-lid request.",
    "The original request is required for automatic generation."
   ],
   "unrepresented_features": []
  },
  "image": {
   "sha256": "125f776b47cdbafe7000b70de434e781d81ee548d631f020b0ccee9a734e68bc",
   "bytes": 9442,
   "width": 640,
   "height": 480,
   "format": "JPEG"
  },
  "visual_audit": {
   "scene": "outline_2d",
   "scene_evidence": "A single dark outline of a rounded rectangle on a white background. No depth, no interior cavity, no cover panel, no visible openings or other features. No evidence of 3D enclosure or spatial faces beyond the 2D outline.",
   "lid_state": "uncertain",
   "lid_evidence": "No lid panel or cover is visible. The outline is flat and lacks any indication of a top panel or closure mechanism.",
   "cover_panel_visible": false,
   "interior_floor_visible": false,
   "opening_certainty": "none",
   "openings": [],
   "other_features": [],
   "uncertainties": [
    "No depth or 3D structure is visible; the outline is ambiguous as to whether it represents a 2D shape or a 3D object with hidden surfaces."
   ]
  },
  "audit_raw_reply": "{\n  \"scene\": \"outline_2d\",\n  \"scene_evidence\": \"A single dark outline of a rounded rectangle on a white background. No depth, no interior cavity, no cover panel, no visible openings or other features. No evidence of 3D enclosure or spatial faces beyond the 2D outline.\",\n  \"lid_state\": \"uncertain\",\n  \"lid_evidence\": \"No lid panel or cover is visible. The outline is flat and lacks any indication of a top panel or closure mechanism.\",\n  \"cover_panel_visible\": false,\n  \"interior_floor_visible\": false,\n  \"opening_certainty\": \"none\",\n  \"openings\": [],\n  \"other_features\": [],\n  \"uncertainties\": [\n    \"No depth or 3D structure is visible; the outline is ambiguous as to whether it represents a 2D shape or a 3D object with hidden surfaces.\"\n  ]\n}",
  "unverified_features": [],
  "input_mode": "image_only",
  "audit_usage": {
   "total_duration": 3331752900,
   "load_duration": 3887500,
   "prompt_eval_count": 1414,
   "prompt_eval_duration": 734677000,
   "eval_count": 194,
   "eval_duration": 2481444000,
   "done_reason": "stop"
  },
  "instructions": "",
  "usage": {
   "total_duration": 3091278600,
   "load_duration": 3876000,
   "prompt_eval_count": 1668,
   "prompt_eval_duration": 654672000,
   "eval_count": 169,
   "eval_duration": 2219204000,
   "done_reason": "stop"
  },
  "latency_ms": 6449.461,
  "schema_valid": true
 },
 "lid": {
  "task_id": "IMG-02",
  "design_spec": {
   "schema_version": "0.1",
   "task_id": "IMG-02",
   "board_id": null,
   "case_shape": "rectangular",
   "lid": {
    "present": true,
    "style": "unspecified"
   },
   "port_requirements": [],
   "mounting": {
    "wall_mount_hole_count": null
   },
   "wall_thickness_mm": null,
   "needs_clarification": true,
   "clarification_questions": [
    "Which exact board should this enclosure fit? Its type cannot be determined from appearance."
   ],
   "assumptions": [
    "Image interpretation does not verify dimensions, physical fit, or printability."
   ]
  },
  "raw_design_spec": {
   "schema_version": "0.1",
   "task_id": "IMG-02",
   "board_id": null,
   "case_shape": "rectangular",
   "lid": {
    "present": true,
    "style": "unspecified"
   },
   "port_requirements": [],
   "mounting": {
    "wall_mount_hole_count": null
   },
   "wall_thickness_mm": null,
   "needs_clarification": false,
   "clarification_questions": [],
   "assumptions": [
    "Image interpretation does not verify dimensions, physical fit, or printability."
   ]
  },
  "raw_reply": "{\n  \"design\": {\n    \"board_id\": null,\n    \"case_shape\": \"rectangular\",\n    \"lid\": {\n      \"present\": true,\n      \"style\": \"unspecified\"\n    },\n    \"port_requirements\": [],\n    \"mounting\": {\n      \"wall_mount_hole_count\": null\n    },\n    \"wall_thickness_mm\": null,\n    \"needs_clarification\": false,\n    \"clarification_questions\": []\n  },\n  \"visual_evidence\": {\n    \"case_shape\": \"rectangular box with a separate lid\",\n    \"lid\": \"lid is shown detached and resting on the case, indicating it is removable\",\n    \"port_requirements\": \"no visible openings or port requirements\",\n    \"mounting\": \"no visible external mounting holes or internal standoffs\"\n  },\n  \"unrepresented_features\": [],\n  \"image_questions\": []\n}",
  "evidence": {
   "visual_evidence": {
    "case_shape": "rectangular box with a separate lid",
    "lid": "lid is shown detached and resting on the case, indicating it is removable",
    "port_requirements": "no visible openings or port requirements",
    "mounting": "no visible external mounting holes or internal standoffs"
   },
   "unrepresented_features": [],
   "image_questions": []
  },
  "changes": [
   {
    "field": "clarification_questions",
    "model": [],
    "corrected": [
     "Which exact board should this enclosure fit? Its type cannot be determined from appearance."
    ],
    "reason": "Conservative evidence questions."
   },
   {
    "field": "needs_clarification",
    "model": false,
    "corrected": true,
    "reason": "Unresolved image requirements need confirmation."
   }
  ],
  "capability": {
   "status": "clarification_required",
   "allow_geometry": false,
   "unsupported": [
    {
     "code": "lid",
     "style": "unspecified"
    }
   ],
   "questions": [
    "Which exact board should this enclosure fit? Its type cannot be determined from appearance."
   ],
   "review_reasons": [
    "Board and enclosure shape must be known.",
    "The automatic path requires an explicit no-lid request.",
    "The original request is required for automatic generation."
   ],
   "unrepresented_features": []
  },
  "image": {
   "sha256": "a6483ea662a7cd39810ca1132754d85d1b206f10083295b8367dce79cb8198db",
   "bytes": 5902,
   "width": 640,
   "height": 480,
   "format": "PNG"
  },
  "visual_audit": {
   "scene": "enclosure_3d",
   "scene_evidence": "A rectangular box with a separate lid, shown open. The lid is hinged and lifted, revealing an interior cavity. The interior floor is visible as a flat surface. The box has a defined rim and walls. No other features are visible beyond the box and lid.",
   "lid_state": "open",
   "lid_evidence": "A separate lid is visible, lifted and resting on the box's rim. The lid is not attached to the box's walls, indicating it is a removable cover.",
   "cover_panel_visible": true,
   "interior_floor_visible": true,
   "opening_certainty": "none",
   "openings": [],
   "other_features": [],
   "uncertainties": []
  },
  "audit_raw_reply": "{\n  \"scene\": \"enclosure_3d\",\n  \"scene_evidence\": \"A rectangular box with a separate lid, shown open. The lid is hinged and lifted, revealing an interior cavity. The interior floor is visible as a flat surface. The box has a defined rim and walls. No other features are visible beyond the box and lid.\",\n  \"lid_state\": \"open\",\n  \"lid_evidence\": \"A separate lid is visible, lifted and resting on the box's rim. The lid is not attached to the box's walls, indicating it is a removable cover.\",\n  \"cover_panel_visible\": true,\n  \"interior_floor_visible\": true,\n  \"opening_certainty\": \"none\",\n  \"openings\": [],\n  \"other_features\": [],\n  \"uncertainties\": []\n}",
  "unverified_features": [],
  "input_mode": "image_only",
  "audit_usage": {
   "total_duration": 2941391400,
   "load_duration": 4386700,
   "prompt_eval_count": 1414,
   "prompt_eval_duration": 729281000,
   "eval_count": 171,
   "eval_duration": 2097436000,
   "done_reason": "stop"
  },
  "instructions": "",
  "usage": {
   "total_duration": 3218733000,
   "load_duration": 5033700,
   "prompt_eval_count": 1668,
   "prompt_eval_duration": 642364000,
   "eval_count": 181,
   "eval_duration": 2372964000,
   "done_reason": "stop"
  },
  "latency_ms": 6165.276,
  "schema_valid": true
 }
};
