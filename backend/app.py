from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from blind_watermark import WaterMark


app = FastAPI(title="Blind Watermark API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIST = BASE_DIR / "static"
ASSETS_DIR = FRONTEND_DIST / "assets"

if ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")


@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/embed")
async def embed(
    image: UploadFile = File(...),
    watermark: UploadFile = File(...),
    password_img: int = Form(1),
    password_wm: int = Form(1),
    output_format: str = Form("png"),
):
    output_format = output_format.strip().lower()
    if output_format not in {"png", "jpg", "jpeg"}:
        raise HTTPException(status_code=400, detail="output_format must be png or jpg")

    suffix = ".jpg" if output_format in {"jpg", "jpeg"} else ".png"
    with TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        image_path = upload_path(tmp, image.filename, "image.png", "source")
        watermark_path = upload_path(tmp, watermark.filename, "watermark.png", "watermark")
        output_path = tmp / f"embedded{suffix}"

        await save_upload(image, image_path)
        await save_upload(watermark, watermark_path)

        try:
            bwm = WaterMark(password_wm=password_wm, password_img=password_img)
            bwm.read_img(str(image_path))
            bwm.read_wm(str(watermark_path))
            bwm.embed(str(output_path))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        return Response(
            content=output_path.read_bytes(),
            media_type=f"image/{'jpeg' if suffix == '.jpg' else 'png'}",
            headers={"Content-Disposition": f'attachment; filename="{output_path.name}"'},
        )


@app.post("/api/extract")
async def extract(
    image: UploadFile = File(...),
    password_img: int = Form(1),
    password_wm: int = Form(1),
    wm_width: int = Form(...),
    wm_height: int = Form(...),
):
    if wm_width <= 0 or wm_height <= 0:
        raise HTTPException(status_code=400, detail="wm_width and wm_height must be positive")

    with TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        image_path = upload_path(tmp, image.filename, "embedded.png", "source")
        output_path = tmp / "extracted-watermark.png"

        await save_upload(image, image_path)

        try:
            bwm = WaterMark(password_wm=password_wm, password_img=password_img)
            bwm.extract(
                filename=str(image_path),
                wm_shape=(wm_height, wm_width),
                out_wm_name=str(output_path),
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        return Response(
            content=output_path.read_bytes(),
            media_type="image/png",
            headers={"Content-Disposition": f'attachment; filename="{output_path.name}"'},
        )


async def save_upload(upload: UploadFile, path: Path) -> None:
    content = await upload.read()
    if not content:
        raise HTTPException(status_code=400, detail=f"{upload.filename or 'file'} is empty")
    path.write_bytes(content)


def safe_name(filename: Optional[str], fallback: str) -> str:
    if not filename:
        return fallback
    # Browsers may submit Windows-style paths even when the server runs on POSIX.
    name = Path(filename.replace("\\", "/")).name
    return fallback if name in {"", ".", ".."} else name


def upload_path(directory: Path, filename: Optional[str], fallback: str, role: str) -> Path:
    """Keep uploads separate even when clients send identical filenames."""
    return directory / f"{role}-{safe_name(filename, fallback)}"


@app.get("/")
def serve_index():
    return serve_frontend()


@app.get("/{full_path:path}")
def serve_frontend(full_path: str = ""):
    index_file = FRONTEND_DIST / "index.html"
    if not index_file.exists():
        raise HTTPException(
            status_code=404,
            detail="Frontend build not found. Run `npm run build` in the frontend directory first.",
        )
    return FileResponse(index_file)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000)
