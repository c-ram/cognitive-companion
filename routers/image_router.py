import shutil
import textwrap
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from PIL import Image, ImageDraw, ImageFont

from datetime import datetime, timedelta
from database import get_db, ActiveImageState
from sqlalchemy.orm import Session

router = APIRouter(prefix="/image", tags=["image"])

BASE_DIR = Path("assets") / "images"
TEMPLATES_DIR = BASE_DIR / "templates"
ACTIVE_IMAGE = BASE_DIR / "active.png"

# Simple template map
TEMPLATE_MAP = {
    "default": TEMPLATES_DIR / "default.png",
    "alert": TEMPLATES_DIR / "alert.png",
}


def ensure_dirs():
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)


def measure_text(draw_obj, text, font_obj):
    """Return (width, height) for the given text using available Pillow APIs."""
    try:
        bbox = draw_obj.textbbox((0, 0), text, font=font_obj)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    except Exception:
        try:
            return draw_obj.textsize(text, font=font_obj)
        except Exception:
            if font_obj is not None:
                try:
                    return font_obj.getsize(text)
                except Exception:
                    pass
            return (len(text) * 6, 11)

def generate_template_if_missing(path: Path, size=(800, 480), bg=(30, 30, 60), label=""):
    if path.exists():
        return
    img = Image.new("RGBA", size, bg)
    draw = ImageDraw.Draw(img)
    if label is not None and label != "": 
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None
        w, h = measure_text(draw, label, font)
        draw.text(((size[0] - w) / 2, (size[1] - h) / 2), label, fill=(255, 255, 255), font=font)
    img.save(path)

def ensure_templates():
    # ensure_dirs()
    # generate_template_if_missing(TEMPLATE_MAP["default"], size=(800, 480), bg=(255, 0, 0), label="DEFAULT")
    # generate_template_if_missing(TEMPLATE_MAP["alert"], size=(800, 480), bg=(0, 255, 0), label="ALERT")
    return

def find_best_font_size(text: str, font_path: str, max_w: int, max_h: int, start_size: int = 60, min_size: int = 10) -> ImageFont.FreeTypeFont:
    """Finds the maximum font size that fits the text within max_w and max_h."""
    size = start_size
    while size >= min_size:
        try:
            font = ImageFont.truetype(font_path, size)
        except Exception as e:
            print(f"Failed to load font {font_path} at size {size}: {e}")
            return ImageFont.load_default()
        
        # We need a dummy draw object to measure accurately
        img = Image.new("RGB", (1, 1))
        draw = ImageDraw.Draw(img)
        w, h = measure_text(draw, text, font)
        
        if w <= max_w and h <= max_h:
            return font
        size -= 4
    
    # Fallback to minimum size if none fits or load default
    try:
        return ImageFont.truetype(font_path, min_size)
    except:
        return ImageFont.load_default()

def generate_alert_image(text: str, expires_in_minutes: int, bbox: tuple, font_name: str, db: Session):
    """
    Generate an alert image using the default template, fitting the text into bbox (w, h).
    Calculates font size automatically and writes an expiry time to the DB.
    """
    ensure_templates()
    tpl = TEMPLATE_MAP["alert"]
    text = textwrap.fill(text, width=40).replace('\n', '\n\n')
    
    try:
        img = Image.open(tpl).convert("RGBA")
        draw = ImageDraw.Draw(img)
        
        font_path = str(Path("assets", "fonts", font_name))
        max_w, max_h = bbox
        
        font = find_best_font_size(text, font_path, max_w, max_h)
        w, h = measure_text(draw, text, font)
        
        # Center the text in the image roughly
        x = (img.width - w) / 2
        y = (img.height - h) / 2
        
        # Overwrite default template with a semi-transparent background to make text readable
        rect_color = (255, 255, 255, 48)
        overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
        ov_draw = ImageDraw.Draw(overlay)
        padding = 20
        ov_draw.rectangle([x - padding, y - padding, x + w + padding, y + h + padding], fill=rect_color)
        combined = Image.alpha_composite(img, overlay)
        
        cd = ImageDraw.Draw(combined)
        cd.text((x, y), text, fill=(0, 0, 0, 255), font=font)
        
        # Save active image
        combined.convert("RGB").save(ACTIVE_IMAGE, format="PNG")
        
        # Update expiry in DB
        state = db.query(ActiveImageState).first()
        if not state:
            state = ActiveImageState()
            db.add(state)
        state.expires_at = datetime.utcnow() + timedelta(minutes=expires_in_minutes)
        db.commit()
    except Exception as e:
        print(f"Failed to generate alert image: {e}")
        db.rollback()


@router.on_event("startup")
async def startup_create_assets():
    # ensure_templates()
    # ensure active exists
    if not ACTIVE_IMAGE.exists():
        shutil.copyfile(TEMPLATE_MAP["default"], ACTIVE_IMAGE)


@router.get("/active/{image_name}")
async def get_active_image(image_name: str, db: Session = Depends(get_db)):
    if not ACTIVE_IMAGE.exists():
        raise HTTPException(status_code=404, detail="Active image not found")

    state = db.query(ActiveImageState).first()
    if state and state.expires_at and datetime.utcnow() > state.expires_at:
        # Expired: replace active with default
        # ensure_templates()
        shutil.copyfile(TEMPLATE_MAP["default"], ACTIVE_IMAGE)
        state.expires_at = None
        db.commit()

    return FileResponse(str(ACTIVE_IMAGE), media_type="image/png")


@router.post("/reset")
async def reset_active_to_default(request: Request):
    """
    Copy the default template into the active image location.
    """
    # ensure_templates()
    try:
        shutil.copyfile(TEMPLATE_MAP["default"], ACTIVE_IMAGE)
        return JSONResponse({"status": "ok", "active": str(ACTIVE_IMAGE)})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class RenderRequest(BaseModel):
    template_name: str
    text: str


@router.post("/render")
async def render_template(req: RenderRequest):
    """
    Renders `text` onto a copy of the requested template and replaces the active image.
    `template_name` must exist in TEMPLATE_MAP.
    """
    ensure_templates()
    tpl = TEMPLATE_MAP.get(req.template_name)
    if not tpl:
        raise HTTPException(status_code=400, detail=f"Unknown template: {req.template_name}")

    if not tpl.exists():
        raise HTTPException(status_code=500, detail=f"Template missing on disk: {tpl}")

    try:
        img = Image.open(tpl).convert("RGBA")
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None

        # Simple layout: put text near bottom-left with padding and semi-transparent box
        text = req.text or ""
        padding = 12
        w, h = measure_text(draw, text, font)
        box_x0 = padding
        box_y0 = img.height - h - padding * 2
        box_x1 = box_x0 + w + padding * 2
        box_y1 = img.height - padding

        # draw semi-transparent rectangle
        rect_color = (0, 0, 0, 160)
        overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
        ov_draw = ImageDraw.Draw(overlay)
        ov_draw.rectangle([box_x0, box_y0, box_x1, box_y1], fill=rect_color)
        combined = Image.alpha_composite(img, overlay)

        cd = ImageDraw.Draw(combined)
        cd.text((box_x0 + padding, box_y0 + padding / 2), text, fill=(255, 255, 255, 255), font=font)

        # Save to active
        combined.convert("RGB").save(ACTIVE_IMAGE, format="PNG")
        return JSONResponse({"status": "ok", "active": str(ACTIVE_IMAGE)})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
