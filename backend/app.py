from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from blind_watermark import WaterMark


app = FastAPI(title="Blind Watermark API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    output_format = output_format.lower()
    if output_format not in {"png", "jpg", "jpeg"}:
        raise HTTPException(status_code=400, detail="output_format must be png or jpg")

    suffix = ".jpg" if output_format in {"jpg", "jpeg"} else ".png"
    with TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        image_path = tmp / safe_name(image.filename, "image.png")
        watermark_path = tmp / safe_name(watermark.filename, "watermark.png")
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
        image_path = tmp / safe_name(image.filename, "embedded.png")
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
    name = Path(filename).name
    return name or fallback
