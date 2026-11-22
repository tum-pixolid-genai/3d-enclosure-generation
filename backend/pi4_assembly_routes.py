import logging
from os import getenv
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated, Literal
from uuid import uuid4

import cadquery as cq
from fastapi import APIRouter, HTTPException, Path as PathParameter
from fastapi.responses import FileResponse

from backend.geometry_service import OUTPUT_DIR
from geometry.assembly_verification import run_port_cutout_experiment


router = APIRouter(prefix="/design/pi4-assembly", tags=["Pi 4 assembly"])
logger = logging.getLogger(__name__)

ARTIFACTS = {
    "enclosure": ("enclosure_candidate_cutouts.step", "model/step"),
    "lid": ("enclosure_lid.step", "model/step"),
    "report": ("final_verification_report.json", "application/json"),
    "enclosure_stl": ("enclosure_candidate_cutouts.stl", "model/stl"),
    "lid_stl": ("enclosure_lid.stl", "model/stl"),
}


@router.post("")
def create_pi4_assembly():
    default_reference = OUTPUT_DIR / "reference-models" / "raspberry-pi-4.step"
    reference = Path(getenv("PIXOLID_PI4_REFERENCE_STEP") or default_reference)
    if not reference.is_file():
        raise HTTPException(status_code=503, detail="Pi 4 reference STEP is unavailable.")

    task_id = f"pi4_{uuid4().hex}"
    assemblies_dir = OUTPUT_DIR / "pi4_assemblies"
    try:
        assemblies_dir.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=assemblies_dir, prefix="working-") as temporary_dir:
            staging_dir = Path(temporary_dir) / "result"
            report = run_port_cutout_experiment(reference, export_dir=staging_dir)
            validated = report["assembly_validated"] is True
            mounting = report["mounting_alignment"]
            lid_fasteners = report["lid_fastener_validation"]
            response = {
                "task_id": task_id,
                "status": "generated" if validated else "geometry_blocked",
                "assembly_validated": validated,
                "verification_summary": report["verification_summary"],
                "verification_metrics": {
                    "baseline_collision_mm3": report["baseline_collision_mm3"],
                    "collision_volume_mm3": report["candidate_collision"]["collision_volume_mm3"],
                    "mounting_hole_alignment_verified": mounting["step_hole_alignment_verified"],
                    "mounting_hole_max_deviation_mm": mounting.get("maximum_step_deviation_mm"),
                    "lid_fasteners_aligned": lid_fasteners["valid"],
                    "lid_fastener_count": lid_fasteners["hole_count"],
                },
            }
            if validated:
                for component in ("enclosure", "lid"):
                    step_name, _ = ARTIFACTS[component]
                    stl_name, _ = ARTIFACTS[f"{component}_stl"]
                    model = cq.importers.importStep(str(staging_dir / step_name))
                    cq.exporters.export(model, str(staging_dir / stl_name), exportType="STL")
                for filename, _ in ARTIFACTS.values():
                    if (staging_dir / filename).stat().st_size == 0:
                        raise OSError(f"Empty assembly artifact: {filename}")
                staging_dir.rename(assemblies_dir / task_id)
    except Exception as error:
        logger.exception("Pi 4 assembly generation failed for %s", task_id)
        raise HTTPException(status_code=500, detail="Pi 4 assembly generation failed.") from error

    if validated:
        response["downloads"] = {
            artifact: f"/design/pi4-assembly/{task_id}/{artifact}" for artifact in ARTIFACTS
        }
    return response


@router.get("/{task_id}/{artifact}")
def download_pi4_artifact(
    task_id: Annotated[str, PathParameter(pattern=r"^pi4_[0-9a-f]{32}$")],
    artifact: Literal["enclosure", "lid", "report", "enclosure_stl", "lid_stl"],
):
    filename, media_type = ARTIFACTS[artifact]
    path = OUTPUT_DIR / "pi4_assemblies" / task_id / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Pi 4 assembly artifact not found.")
    return FileResponse(path, filename=filename, media_type=media_type)
