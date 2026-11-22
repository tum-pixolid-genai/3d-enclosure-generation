# Geometry & Automatic Checks — integration contract

## Scope

The current module creates an **open-top, rectangular CAD enclosure** with
optional **one explicitly positioned cutout** on the negative-Y wall. It is a
preliminary enclosure generator, **not a mechanically validated Raspberry Pi 4
case**. It does not model a lid, mounting holes, standoffs, connector keepouts,
or physical fit.

## Python API

```python
from geometry.checks import validate_and_generate

spec = {
    "task_id": "demo-001",
    "board_id": "raspberry_pi_4",
    "case_shape": "rectangular",
    "wall_thickness_mm": 2.0,
    "needs_clarification": False,
    # Optional Geometry-specific extension (not part of Agent v0.1 schema):
    "usb_port": {"width_mm": 10, "height_mm": 4, "x_mm": 0, "z_mm": 0},
}
result = validate_and_generate(spec, output_path="demo.step")
```

The result is a dictionary with `task_id`, `valid`, `dimensions`, `errors`,
`warnings`, and, on successful export, `output_path`. Invalid input returns
`valid=False`; CAD/export errors are reported in `errors`.

## Coordinates and 3 mm change

The enclosure is centered at (0,0,0). `x_mm` is the cutout center along X,
`z_mm` its vertical center, and the cutout is on the **negative-Y wall**.
Changing `usb_port.x_mm` from `x` to `x + 3` shifts the opening 3 mm toward
positive X ("right" in this coordinate convention). This is a *parametric*
change, not verified physical connector alignment. The two STEP outputs are
compared by `tests/test_usb_shift_3mm.py`.

## Raspberry Pi 4 data and limitations

`raspberry_pi_4` uses a nominal ~85 × 56 mm board footprint and a **provisional
18 mm component envelope**. These are not certified fit dimensions. Accurate
USB/Ethernet/HDMI placement requires a verified mechanical drawing and an
agreed coordinate frame. Agent v0.1 `port_requirements` does **not** provide
cutout coordinates; it currently produces a warning rather than automatically
creating physical connector openings. Do not present such outputs as ready to
print or mechanically validated.

## Local checks

```bash
conda activate pixolid-geometry
python -m pytest -q
```

For team acceptance, the Backend owner should separately exercise an actual
Agent -> Backend -> Geometry -> STEP request with `raspberry_pi_4` and confirm
the resulting file can be retrieved by the frontend. Passing Geometry unit
and smoke tests does not establish this end-to-end behavior.
