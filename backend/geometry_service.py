
from pathlib import Path
import re
import cadquery as cq

from geometry.checks import validate_and_generate


# Store generated CAD files outside the Git repository
OUTPUT_DIR = (
    Path(__file__).resolve().parents[2]
    / "pixolid-demo-outputs"
)


def run_geometry(design_spec: dict) -> dict:
    # Step 1: Get and validate the task ID
    task_id = design_spec["task_id"]

    if not isinstance(task_id, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_-]*", task_id
    ):
        raise ValueError("Invalid task_id")

    # Step 2: Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Step 3: Define STEP file path
    output_path = OUTPUT_DIR / f"{task_id}.step"

    # Step 4: Call the Geometry module
    result = validate_and_generate(
        design_spec,
        output_path=output_path
    )

    
    # Step 5: Convert STEP to STL for frontend preview
    if result.get("valid") and output_path.is_file():
        stl_path = OUTPUT_DIR / f"{task_id}.stl"

        try:
            model = cq.importers.importStep(str(output_path))

            cq.exporters.export(
                model,
                str(stl_path),
                exportType="STL"
            )

            if not stl_path.is_file() or stl_path.stat().st_size == 0:
                raise RuntimeError("STL file is missing or empty")

            result["stl_path"] = str(stl_path)

        except Exception as error:
            stl_path.unlink(missing_ok=True)
            result.setdefault("warnings", []).append(
                f"STL export failed: {error}"
            )

    # Step 6: Return the Geometry result
    return result

