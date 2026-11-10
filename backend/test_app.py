from pathlib import Path

import cv2
import numpy as np
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


def test_png_watermark_round_trip_with_real_image_processing():
    source = np.random.default_rng(0).integers(0, 256, (64, 64, 3), dtype=np.uint8)
    watermark = np.array([[0, 255, 0], [255, 0, 255]], dtype=np.uint8)
    source_ok, source_png = cv2.imencode(".png", source)
    watermark_ok, watermark_png = cv2.imencode(".png", watermark)
    assert source_ok and watermark_ok

    with TestClient(app) as client:
        embedded = client.post(
            "/api/embed",
            files={
                "image": ("image.png", source_png.tobytes(), "image/png"),
                "watermark": ("image.png", watermark_png.tobytes(), "image/png"),
            },
            data={"password_img": "11", "password_wm": "7"},
        )
        assert embedded.status_code == 200
        embedded_image = cv2.imdecode(
            np.frombuffer(embedded.content, dtype=np.uint8), cv2.IMREAD_COLOR
        )
        assert embedded_image is not None
        assert embedded_image.shape == source.shape

        extracted = client.post(
            "/api/extract",
            files={"image": ("embedded.png", embedded.content, "image/png")},
            data={"wm_width": "3", "wm_height": "2", "password_img": "11", "password_wm": "7"},
        )

    assert extracted.status_code == 200
    extracted_image = cv2.imdecode(
        np.frombuffer(extracted.content, dtype=np.uint8), cv2.IMREAD_GRAYSCALE
    )
    assert extracted_image is not None
    assert extracted_image.shape == watermark.shape
    np.testing.assert_array_equal(extracted_image > 128, watermark > 128)


@pytest.mark.parametrize("output_format", ["jpg", "jpeg"])
def test_embed_produces_decodable_jpeg_with_real_image_processing(output_format):
    source = np.random.default_rng(0).integers(0, 256, (64, 64, 3), dtype=np.uint8)
    watermark = np.array([[0, 255, 0], [255, 0, 255]], dtype=np.uint8)
    source_ok, source_png = cv2.imencode(".png", source)
    watermark_ok, watermark_png = cv2.imencode(".png", watermark)
    assert source_ok and watermark_ok

    response = TestClient(app).post(
        "/api/embed",
        files={
            "image": ("source.png", source_png.tobytes(), "image/png"),
            "watermark": ("watermark.png", watermark_png.tobytes(), "image/png"),
        },
        data={"output_format": output_format},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.headers["content-disposition"] == 'attachment; filename="embedded.jpg"'
    assert response.content.startswith(b"\xff\xd8\xff")
    embedded_image = cv2.imdecode(
        np.frombuffer(response.content, dtype=np.uint8), cv2.IMREAD_COLOR
    )
    assert embedded_image is not None
    assert embedded_image.shape == source.shape


@pytest.mark.parametrize(
    ("watermark_shape", "expected_status"),
    [((7, 9), 200), ((8, 8), 400), ((5, 13), 400)],
    ids=["below-capacity", "at-capacity", "above-capacity"],
)
def test_embed_enforces_real_watermark_capacity(watermark_shape, expected_status):
    # A 64x64 source has 64 transform blocks; watermark bits must be strictly fewer.
    source = np.random.default_rng(0).integers(0, 256, (64, 64, 3), dtype=np.uint8)
    watermark = np.full(watermark_shape, 255, dtype=np.uint8)
    source_ok, source_png = cv2.imencode(".png", source)
    watermark_ok, watermark_png = cv2.imencode(".png", watermark)
    assert source_ok and watermark_ok

    response = TestClient(app).post(
        "/api/embed",
        files={
            "image": ("source.png", source_png.tobytes(), "image/png"),
            "watermark": ("watermark.png", watermark_png.tobytes(), "image/png"),
        },
    )

    assert response.status_code == expected_status
    if expected_status == 200:
        embedded_image = cv2.imdecode(
            np.frombuffer(response.content, dtype=np.uint8), cv2.IMREAD_COLOR
        )
        assert embedded_image is not None
        assert embedded_image.shape == source.shape
    else:
        assert "溢出" in response.json()["detail"]


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
    ("data", "invalid_field"),
    [
        ({"wm_height": "5"}, "wm_width"),
        ({"wm_width": "3"}, "wm_height"),
        ({"wm_width": "abc", "wm_height": "5"}, "wm_width"),
        ({"wm_width": "3", "wm_height": "abc"}, "wm_height"),
        ({"wm_width": "1.5", "wm_height": "5"}, "wm_width"),
        ({"wm_width": "3", "wm_height": "1.5"}, "wm_height"),
    ],
    ids=[
        "missing-width", "missing-height", "non-numeric-width", "non-numeric-height",
        "fractional-width", "fractional-height",
    ],
)
def test_extract_requires_integer_dimensions_before_processing(monkeypatch, data, invalid_field):
    def unexpected_watermark_processing(**_kwargs):
        pytest.fail("Missing or non-integer dimensions must be rejected before processing")

    monkeypatch.setattr("app.WaterMark", unexpected_watermark_processing)
    response = TestClient(app).post(
        "/api/extract",
        files={"image": ("embedded.png", b"image", "image/png")},
        data=data,
    )

    assert response.status_code == 422
    errors = response.json()["detail"]
    assert len(errors) == 1
    assert errors[0]["loc"] == ["body", invalid_field]


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


@pytest.mark.parametrize(
    ("output_format", "extension", "media_type"),
    [
        ("png", ".png", "image/png"),
        ("jpg", ".jpg", "image/jpeg"),
        ("jpeg", ".jpg", "image/jpeg"),
        (" PNG ", ".png", "image/png"),
        (" JPEG ", ".jpg", "image/jpeg"),
    ],
)
def test_embed_output_format_matches_file_extension_and_response_headers(
    monkeypatch, output_format, extension, media_type
):
    class StubWaterMark:
        def __init__(self, **_kwargs):
            pass

        def read_img(self, _path):
            pass

        def read_wm(self, _path):
            pass

        def embed(self, output_path):
            assert Path(output_path).suffix == extension
            Path(output_path).write_bytes(b"embedded-output")

    monkeypatch.setattr("app.WaterMark", StubWaterMark)
    response = TestClient(app).post(
        "/api/embed",
        files={
            "image": ("source.png", b"source", "image/png"),
            "watermark": ("watermark.png", b"watermark", "image/png"),
        },
        data={"output_format": output_format},
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == media_type
    assert response.headers["content-disposition"] == (
        f'attachment; filename="embedded{extension}"'
    )
    assert response.content == b"embedded-output"


@pytest.mark.parametrize(
    ("endpoint", "files", "data", "missing_fields"),
    [
        ("/api/embed", {}, {}, {"image", "watermark"}),
        (
            "/api/embed",
            {"image": ("source.png", b"source", "image/png")},
            {},
            {"watermark"},
        ),
        (
            "/api/embed",
            {"watermark": ("watermark.png", b"watermark", "image/png")},
            {},
            {"image"},
        ),
        ("/api/extract", {}, {"wm_width": 3, "wm_height": 5}, {"image"}),
    ],
    ids=["embed-no-files", "embed-no-watermark", "embed-no-image", "extract-no-image"],
)
def test_required_uploads_are_validated_before_processing(
    monkeypatch, endpoint, files, data, missing_fields
):
    def unexpected_watermark_processing(**_kwargs):
        pytest.fail("Missing uploads must be rejected before watermark processing")

    monkeypatch.setattr("app.WaterMark", unexpected_watermark_processing)
    response = TestClient(app).post(endpoint, files=files, data=data)

    assert response.status_code == 422
    errors = response.json()["detail"]
    assert len(errors) == len(missing_fields)
    assert {tuple(error["loc"]) for error in errors} == {
        ("body", field) for field in missing_fields
    }
