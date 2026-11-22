import pytest
from fastapi import HTTPException

from backend import pi4_assembly_routes as assembly


def test_missing_reference_returns_503(monkeypatch, tmp_path):
    monkeypatch.setattr(assembly, "OUTPUT_DIR", tmp_path)
    monkeypatch.delenv("PIXOLID_PI4_REFERENCE_STEP", raising=False)

    with pytest.raises(HTTPException) as error:
        assembly.create_pi4_assembly()

    assert error.value.status_code == 503
    assert not (tmp_path / "pi4_assemblies").exists()


@pytest.mark.parametrize("validated", [False, True])
def test_incomplete_assembly_is_not_published(monkeypatch, tmp_path, validated):
    reference = tmp_path / "reference.step"
    reference.touch()
    monkeypatch.setenv("PIXOLID_PI4_REFERENCE_STEP", str(reference))
    monkeypatch.setattr(assembly, "OUTPUT_DIR", tmp_path)

    def incomplete_generation(step_path, export_dir):
        assert step_path == reference
        export_dir.mkdir()
        (export_dir / "enclosure_candidate_cutouts.step").write_bytes(b"enclosure")
        return {
            "assembly_validated": validated,
            "verification_summary": {"assembly_validated": validated},
        }

    monkeypatch.setattr(assembly, "run_port_cutout_experiment", incomplete_generation)

    if validated:
        with pytest.raises(HTTPException) as error:
            assembly.create_pi4_assembly()
        assert error.value.status_code == 500
    else:
        response = assembly.create_pi4_assembly()
        assert response["status"] == "geometry_blocked"
        assert response["assembly_validated"] is False
        assert "downloads" not in response

    assert list((tmp_path / "pi4_assemblies").iterdir()) == []
