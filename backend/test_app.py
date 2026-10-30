from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import app, safe_name, upload_path


@pytest.mark.parametrize("route", ["/", "/workspace/extract"])
def test_frontend_serves_index_for_root_and_client_routes(monkeypatch, tmp_path, route):
    index_content = "<!doctype html><html><body>Watermark workspace</body></html>"
    (tmp_path / "index.html").write_text(index_content, encoding="utf-8")
    monkeypatch.setattr("app.FRONTEND_DIST", tmp_path)

    response = TestClient(app).get(route)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.text == index_content


@pytest.mark.parametrize("route", ["/", "/workspace/extract"])
def test_frontend_reports_missing_build(monkeypatch, tmp_path, route):
    monkeypatch.setattr("app.FRONTEND_DIST", tmp_path)

    response = TestClient(app).get(route)

    assert response.status_code == 404
    assert response.json() == {
        "detail": (
            "Frontend build not found. Run `npm run build` in the frontend directory first."
        )
    }


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


def test_embed_keeps_same_named_upload_contents_separate(monkeypatch):
    input_paths = []

    class StubWaterMark:
        def __init__(self, **_kwargs):
            pass

        def read_img(self, filename):
            input_paths.append(Path(filename))
            assert Path(filename).read_bytes() == b"source-image"

        def read_wm(self, filename):
            input_paths.append(Path(filename))
            assert Path(filename).read_bytes() == b"watermark-image"

        def embed(self, output_path):
            assert input_paths[0] != input_paths[1]
            assert Path(output_path) not in input_paths
            Path(output_path).write_bytes(b"embedded-image")

    monkeypatch.setattr("app.WaterMark", StubWaterMark)
    response = TestClient(app).post(
        "/api/embed",
        files={
            "image": ("embedded.png", b"source-image", "image/png"),
            "watermark": ("embedded.png", b"watermark-image", "image/png"),
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers["content-disposition"] == 'attachment; filename="embedded.png"'
    assert response.content == b"embedded-image"
    assert len(input_paths) == 2
    assert all(not path.exists() for path in input_paths)


@pytest.mark.parametrize(
    ("width", "height"),
    [(0, 1), (1, 0), (-1, 1), (1, -1), (0, 0)],
)
def test_extract_rejects_non_positive_dimensions_before_processing(monkeypatch, width, height):
    def unexpected_watermark_processing(**_kwargs):
        pytest.fail("Invalid dimensions must be rejected before watermark processing")

    monkeypatch.setattr("app.WaterMark", unexpected_watermark_processing)
    response = TestClient(app).post(
        "/api/extract",
        files={"image": ("embedded.png", b"image", "image/png")},
        data={"wm_width": width, "wm_height": height},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "wm_width and wm_height must be positive"}


@pytest.mark.parametrize(
    ("endpoint", "files", "data", "empty_filename"),
    [
        (
            "/api/embed",
            {
                "image": ("source.png", b"", "image/png"),
                "watermark": ("watermark.png", b"watermark", "image/png"),
            },
            {},
            "source.png",
        ),
        (
            "/api/embed",
            {
                "image": ("source.png", b"source", "image/png"),
                "watermark": ("watermark.png", b"", "image/png"),
            },
            {},
            "watermark.png",
        ),
        (
            "/api/extract",
            {"image": ("embedded.png", b"", "image/png")},
            {"wm_width": 1, "wm_height": 1},
            "embedded.png",
        ),
    ],
    ids=["empty-source", "empty-watermark", "empty-extraction-image"],
)
def test_empty_uploads_are_rejected_before_processing(
    monkeypatch, endpoint, files, data, empty_filename
):
    def unexpected_watermark_processing(**_kwargs):
        pytest.fail("Empty uploads must be rejected before watermark processing")

    monkeypatch.setattr("app.WaterMark", unexpected_watermark_processing)
    response = TestClient(app).post(endpoint, files=files, data=data)

    assert response.status_code == 400
    assert response.json() == {"detail": f"{empty_filename} is empty"}


@pytest.mark.parametrize(("width", "height"), [(3, 5), (5, 3)])
def test_extract_preserves_rectangular_watermark_dimensions(monkeypatch, width, height):
    class StubWaterMark:
        def __init__(self, *, password_wm, password_img):
            assert password_wm == 7
            assert password_img == 11

        def extract(self, *, filename, wm_shape, out_wm_name):
            assert Path(filename).read_bytes() == b"embedded-image"
            assert wm_shape == (height, width)
            Path(out_wm_name).write_bytes(b"extracted-watermark")

    monkeypatch.setattr("app.WaterMark", StubWaterMark)
    response = TestClient(app).post(
        "/api/extract",
        files={"image": ("embedded.png", b"embedded-image", "image/png")},
        data={
            "wm_width": str(width),
            "wm_height": str(height),
            "password_wm": "7",
            "password_img": "11",
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers["content-disposition"] == (
        'attachment; filename="extracted-watermark.png"'
    )
    assert response.content == b"extracted-watermark"


@pytest.mark.parametrize(
    ("endpoint", "files", "data"),
    [
        (
            "/api/embed",
            {
                "image": ("source.png", b"invalid-image", "image/png"),
                "watermark": ("watermark.png", b"watermark", "image/png"),
            },
            {},
        ),
        (
            "/api/extract",
            {"image": ("embedded.png", b"invalid-image", "image/png")},
            {"wm_width": 3, "wm_height": 5},
        ),
    ],
    ids=["embed", "extract"],
)
def test_watermark_processing_errors_return_bad_request(monkeypatch, endpoint, files, data):
    input_paths = []

    class InvalidImageWaterMark:
        def __init__(self, **_kwargs):
            pass

        def read_img(self, filename):
            input_paths.append(Path(filename))
            assert Path(filename).read_bytes() == b"invalid-image"
            raise ValueError("Unable to decode image")

        def extract(self, *, filename, **_kwargs):
            self.read_img(filename)

    monkeypatch.setattr("app.WaterMark", InvalidImageWaterMark)
    response = TestClient(app).post(endpoint, files=files, data=data)

    assert response.status_code == 400
    assert response.json() == {"detail": "Unable to decode image"}
    assert len(input_paths) == 1
    assert not input_paths[0].exists()
    assert not input_paths[0].parent.exists()


@pytest.mark.parametrize("output_format", ["gif", "webp", "svg", "   "])
def test_embed_rejects_unsupported_output_formats_before_processing(monkeypatch, output_format):
    def unexpected_watermark_processing(**_kwargs):
        pytest.fail("Unsupported formats must be rejected before watermark processing")

    monkeypatch.setattr("app.WaterMark", unexpected_watermark_processing)
    response = TestClient(app).post(
        "/api/embed",
        files={
            "image": ("source.png", b"source", "image/png"),
            "watermark": ("watermark.png", b"watermark", "image/png"),
        },
        data={"output_format": output_format},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "output_format must be png or jpg"}


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
