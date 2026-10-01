from pathlib import Path

from fastapi.testclient import TestClient

from app import app, safe_name, upload_path


def test_safe_name_strips_posix_and_windows_directories():
    assert safe_name("/tmp/photo.png", "fallback.png") == "photo.png"
    assert safe_name(r"C:\fakepath\photo.png", "fallback.png") == "photo.png"


def test_safe_name_uses_fallback_for_missing_or_directory_only_names():
    assert safe_name(None, "fallback.png") == "fallback.png"
    assert safe_name("", "fallback.png") == "fallback.png"
    assert safe_name("/", "fallback.png") == "fallback.png"
    assert safe_name("\\", "fallback.png") == "fallback.png"
    assert safe_name(".", "fallback.png") == "fallback.png"
    assert safe_name("..", "fallback.png") == "fallback.png"
    assert safe_name("../", "fallback.png") == "fallback.png"


def test_upload_path_keeps_same_named_inputs_separate():
    directory = Path("/tmp/uploads")

    image_path = upload_path(directory, "photo.png", "image.png", "source")
    watermark_path = upload_path(directory, "photo.png", "watermark.png", "watermark")

    assert image_path == directory / "source-photo.png"
    assert watermark_path == directory / "watermark-photo.png"
    assert image_path != watermark_path


def test_embed_accepts_output_format_with_surrounding_whitespace(monkeypatch):
    class StubWaterMark:
        def __init__(self, **_kwargs):
            pass

        def read_img(self, _path):
            pass

        def read_wm(self, _path):
            pass

        def embed(self, output_path):
            Path(output_path).write_bytes(b"jpeg-output")

    monkeypatch.setattr("app.WaterMark", StubWaterMark)
    response = TestClient(app).post(
        "/api/embed",
        files={
            "image": ("source.png", b"source", "image/png"),
            "watermark": ("watermark.png", b"watermark", "image/png"),
        },
        data={"output_format": " JPEG "},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.content == b"jpeg-output"
