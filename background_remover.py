#!/usr/bin/env python
"""
Small background remover with a Tkinter UI and CLI.

It works out of the box with Pillow for solid/chroma/checker backgrounds.
If rembg is installed, Auto/AI mode uses it for stronger image matting.
"""

from __future__ import annotations

import argparse
import io
import math
import mimetypes
import os
import uuid
from collections import Counter, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib import error, request

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


@dataclass
class RemoveOptions:
    mode: str = "auto"
    key_color: tuple[int, int, int] | None = None
    tolerance: int = 38
    soft_edges: bool = True
    enhance: bool = True
    upscale: float = 1.0
    fill: tuple[int, int, int] | None = None
    api_key: str | None = None
    api_size: str = "auto"


def clamp(value: int, low: int = 0, high: int = 255) -> int:
    return max(low, min(high, value))


def parse_color(value: str | None) -> tuple[int, int, int] | None:
    if not value:
        return None
    value = value.strip()
    if value.lower() in {"none", "transparent"}:
        return None
    if value.startswith("#"):
        value = value[1:]
    if len(value) != 6:
        raise ValueError("Use a cor no formato #RRGGBB, por exemplo #00ff00.")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def color_to_hex(color: tuple[int, int, int] | None) -> str:
    if color is None:
        return ""
    return "#{:02x}{:02x}{:02x}".format(*color)


def has_rembg() -> bool:
    try:
        import rembg  # noqa: F401
    except Exception:
        return False
    return True


def remove_with_rembg(image: Image.Image) -> Image.Image:
    from rembg import remove

    source = io.BytesIO()
    image.save(source, format="PNG")
    output = remove(source.getvalue())
    return Image.open(io.BytesIO(output)).convert("RGBA")


def get_removebg_api_key(options: RemoveOptions) -> str | None:
    key = options.api_key or os.getenv("REMOVE_BG_API_KEY")
    if key:
        key = key.strip()
    return key or None


def encode_multipart(
    fields: dict[str, str],
    files: dict[str, tuple[str, bytes, str]],
) -> tuple[bytes, str]:
    boundary = f"----BackgroundRemover{uuid.uuid4().hex}"
    chunks: list[bytes] = []

    for name, value in fields.items():
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        chunks.append(str(value).encode("utf-8"))
        chunks.append(b"\r\n")

    for name, (filename, content, mime_type) in files.items():
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(
            (
                f'Content-Disposition: form-data; name="{name}"; '
                f'filename="{filename}"\r\n'
            ).encode("utf-8")
        )
        chunks.append(f"Content-Type: {mime_type}\r\n\r\n".encode("utf-8"))
        chunks.append(content)
        chunks.append(b"\r\n")

    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(chunks), boundary


def remove_with_removebg_api(input_path: str | Path, options: RemoveOptions) -> Image.Image:
    """Use remove.bg's hosted API and return a transparent RGBA image."""

    api_key = get_removebg_api_key(options)
    if not api_key:
        raise ValueError(
            "Para usar o modo API, informe uma chave do remove.bg no campo da tela "
            "ou configure a variavel REMOVE_BG_API_KEY."
        )

    input_path = Path(input_path)
    mime_type = mimetypes.guess_type(input_path.name)[0] or "application/octet-stream"
    fields = {
        "size": options.api_size or "auto",
        "format": "png",
    }
    files = {
        "image_file": (input_path.name, input_path.read_bytes(), mime_type),
    }
    body, boundary = encode_multipart(fields, files)
    api_request = request.Request(
        "https://api.remove.bg/v1.0/removebg",
        data=body,
        headers={
            "X-Api-Key": api_key,
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )

    try:
        with request.urlopen(api_request, timeout=120) as response:
            data = response.read()
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"remove.bg respondeu {exc.code}: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Nao foi possivel acessar a API remove.bg: {exc.reason}") from exc

    return Image.open(io.BytesIO(data)).convert("RGBA")


def iter_border_pixels(image: Image.Image, step: int = 1) -> Iterable[tuple[int, int, int]]:
    rgb = image.convert("RGB")
    width, height = rgb.size
    px = rgb.load()
    for x in range(0, width, step):
        yield px[x, 0]
        yield px[x, height - 1]
    for y in range(0, height, step):
        yield px[0, y]
        yield px[width - 1, y]


def estimate_background_color(image: Image.Image) -> tuple[int, int, int]:
    width, height = image.size
    step = max(1, min(width, height) // 600)
    buckets: Counter[tuple[int, int, int]] = Counter()
    originals: dict[tuple[int, int, int], list[tuple[int, int, int]]] = {}

    for pixel in iter_border_pixels(image, step=step):
        bucket = tuple((channel // 16) * 16 for channel in pixel)
        buckets[bucket] += 1
        originals.setdefault(bucket, []).append(pixel)

    if not buckets:
        return (255, 255, 255)

    bucket, _ = buckets.most_common(1)[0]
    pixels = originals[bucket]
    return tuple(sum(p[i] for p in pixels) // len(pixels) for i in range(3))


def color_distance(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    return math.sqrt(
        (a[0] - b[0]) * (a[0] - b[0])
        + (a[1] - b[1]) * (a[1] - b[1])
        + (a[2] - b[2]) * (a[2] - b[2])
    )


def is_neutral_checker_pixel(pixel: tuple[int, int, int]) -> bool:
    r, g, b = pixel
    average = (r + g + b) // 3
    return average >= 212 and max(pixel) - min(pixel) <= 34


def build_background_mask(
    image: Image.Image,
    key_color: tuple[int, int, int] | None,
    tolerance: int,
    checker_mode: bool = False,
) -> Image.Image:
    """Return an L mask where white means background.

    Only edge-connected pixels are removed. This preserves bright or same-color
    details inside the subject better than a global color delete.
    """

    rgb = image.convert("RGB")
    width, height = rgb.size
    px = rgb.load()
    candidate = bytearray(width * height)

    if checker_mode:
        for y in range(height):
            row = y * width
            for x in range(width):
                if is_neutral_checker_pixel(px[x, y]):
                    candidate[row + x] = 1
    else:
        if key_color is None:
            key_color = estimate_background_color(rgb)
        loose_tolerance = max(8, tolerance)
        for y in range(height):
            row = y * width
            for x in range(width):
                if color_distance(px[x, y], key_color) <= loose_tolerance:
                    candidate[row + x] = 1

    background = bytearray(width * height)
    queue: deque[int] = deque()

    def push(index: int) -> None:
        if candidate[index] and not background[index]:
            background[index] = 255
            queue.append(index)

    for x in range(width):
        push(x)
        push((height - 1) * width + x)
    for y in range(height):
        push(y * width)
        push(y * width + width - 1)

    while queue:
        index = queue.popleft()
        x = index % width
        y = index // width
        if x > 0:
            push(index - 1)
        if x + 1 < width:
            push(index + 1)
        if y > 0:
            push(index - width)
        if y + 1 < height:
            push(index + width)

    return Image.frombytes("L", (width, height), bytes(background))


def soften_alpha(alpha: Image.Image, background_mask: Image.Image) -> Image.Image:
    alpha = alpha.filter(ImageFilter.GaussianBlur(0.55))
    bg = background_mask.load()
    out = alpha.load()
    width, height = alpha.size
    for y in range(height):
        for x in range(width):
            if bg[x, y]:
                out[x, y] = 0
    return alpha


def remove_local(image: Image.Image, options: RemoveOptions) -> Image.Image:
    mode = options.mode.lower()
    checker_mode = mode in {"checker", "xadrez"}
    key_color = options.key_color
    if mode in {"border", "local", "solid", "auto"} and key_color is None:
        key_color = estimate_background_color(image)

    background_mask = build_background_mask(
        image,
        key_color=key_color,
        tolerance=options.tolerance,
        checker_mode=checker_mode,
    )

    # Expand one pixel to catch antialiased fringe, then invert to alpha.
    edge_mask = background_mask.filter(ImageFilter.MaxFilter(3))
    alpha = Image.eval(edge_mask, lambda value: 0 if value else 255)
    if options.soft_edges:
        alpha = soften_alpha(alpha, background_mask)

    result = image.convert("RGBA")
    result.putalpha(alpha)
    return result


def enhance_image(image: Image.Image) -> Image.Image:
    alpha = image.getchannel("A") if image.mode == "RGBA" else None
    rgb = image.convert("RGB")
    rgb = ImageOps.autocontrast(rgb, cutoff=0.4)
    rgb = ImageEnhance.Color(rgb).enhance(1.04)
    rgb = rgb.filter(ImageFilter.UnsharpMask(radius=1.1, percent=95, threshold=3))
    result = rgb.convert("RGBA")
    if alpha is not None:
        result.putalpha(alpha)
    return result


def composite_fill(image: Image.Image, fill: tuple[int, int, int] | None) -> Image.Image:
    if fill is None:
        return image
    background = Image.new("RGBA", image.size, fill + (255,))
    background.alpha_composite(image.convert("RGBA"))
    return background.convert("RGB")


def save_output_image(image: Image.Image, output_path: str | Path, options: RemoveOptions) -> Path:
    output_path = Path(output_path)
    result = image.convert("RGBA")

    if options.upscale and options.upscale != 1:
        width, height = result.size
        result = result.resize(
            (int(width * options.upscale), int(height * options.upscale)),
            Image.Resampling.LANCZOS,
        )

    result = composite_fill(result, options.fill)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    save_kwargs = {"optimize": True}
    if output_path.suffix.lower() in {".jpg", ".jpeg"} and result.mode == "RGBA":
        result = composite_fill(result, (255, 255, 255))
    result.save(output_path, **save_kwargs)
    return output_path


def process_image(input_path: str | Path, output_path: str | Path, options: RemoveOptions) -> Path:
    input_path = Path(input_path)
    output_path = Path(output_path)

    mode = options.mode.lower()
    use_api = mode in {"api", "removebg-api"} or (mode == "auto" and get_removebg_api_key(options))
    if use_api:
        result = remove_with_removebg_api(input_path, options)
    else:
        image = Image.open(input_path)
        image = ImageOps.exif_transpose(image)
        if mode in {"ai", "rembg"} or (mode == "auto" and has_rembg()):
            result = remove_with_rembg(image)
        elif mode in {"auto", "border", "local", "solid", "checker", "xadrez"}:
            # If the image already has alpha, keep it and only polish/save.
            if image.mode == "RGBA" and image.getchannel("A").getextrema()[0] < 255:
                result = image.convert("RGBA")
            else:
                result = remove_local(image, options)
        else:
            raise ValueError(f"Modo desconhecido: {options.mode}")

    if options.enhance:
        result = enhance_image(result)

    return save_output_image(result, output_path, options)


def default_output_path(input_path: str | Path, out_dir: str | Path | None = None) -> Path:
    source = Path(input_path)
    directory = Path(out_dir) if out_dir else source.parent
    return directory / f"{source.stem}-sem-fundo.png"


def process_batch(input_dir: str | Path, out_dir: str | Path, options: RemoveOptions) -> list[Path]:
    input_dir = Path(input_dir)
    out_dir = Path(out_dir)
    outputs: list[Path] = []
    for file_path in sorted(input_dir.iterdir()):
        if file_path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        output_path = default_output_path(file_path, out_dir)
        outputs.append(process_image(file_path, output_path, options))
    return outputs


def make_checkerboard(size: tuple[int, int], tile: int = 16) -> Image.Image:
    width, height = size
    image = Image.new("RGB", size, "white")
    pixels = image.load()
    for y in range(height):
        for x in range(width):
            if ((x // tile) + (y // tile)) % 2:
                pixels[x, y] = (224, 224, 224)
            else:
                pixels[x, y] = (248, 248, 248)
    return image


def launch_gui() -> None:
    import threading
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    from PIL import ImageTk

    class ManualEditor(tk.Toplevel):
        def __init__(self, master, image: Image.Image, on_apply) -> None:
            super().__init__(master)
            self.title("Editor manual")
            self.geometry("1060x760")
            self.minsize(760, 520)
            self.on_apply = on_apply
            self.base_image = image.convert("RGBA").copy()
            self.image = self.base_image.copy()
            self.undo_stack: list[Image.Image] = []
            self.preview_photo = None
            self.scale = 1.0
            self.offset_x = 0
            self.offset_y = 0
            self.stroke_active = False

            self.tool_var = tk.StringVar(value="erase")
            self.brush_var = tk.IntVar(value=36)
            self.status_var = tk.StringVar(value="Apagar: clique e arraste sobre o que sobrou do fundo.")

            self.rowconfigure(1, weight=1)
            self.columnconfigure(0, weight=1)
            self.build_toolbar()
            self.build_canvas()
            self.bind("<Control-z>", lambda _event: self.undo())
            self.bind("<Escape>", lambda _event: self.destroy())
            self.after(120, self.redraw)

        def build_toolbar(self) -> None:
            toolbar = ttk.Frame(self, padding=(10, 8))
            toolbar.grid(row=0, column=0, sticky="ew")
            toolbar.columnconfigure(8, weight=1)

            ttk.Radiobutton(toolbar, text="Apagar", variable=self.tool_var, value="erase").grid(
                row=0, column=0, padx=(0, 8)
            )
            ttk.Radiobutton(toolbar, text="Restaurar", variable=self.tool_var, value="restore").grid(
                row=0, column=1, padx=(0, 14)
            )
            ttk.Label(toolbar, text="Pincel").grid(row=0, column=2, padx=(0, 6))
            ttk.Scale(toolbar, from_=4, to=180, orient="horizontal", variable=self.brush_var).grid(
                row=0, column=3, sticky="ew", padx=(0, 6)
            )
            ttk.Label(toolbar, textvariable=self.brush_var, width=4).grid(row=0, column=4, padx=(0, 14))
            ttk.Button(toolbar, text="Desfazer", command=self.undo).grid(row=0, column=5, padx=(0, 6))
            ttk.Button(toolbar, text="Resetar", command=self.reset).grid(row=0, column=6, padx=(0, 14))
            ttk.Button(toolbar, text="Aplicar", command=self.apply).grid(row=0, column=7, padx=(0, 6))
            ttk.Button(toolbar, text="Fechar", command=self.destroy).grid(row=0, column=8, sticky="e")

            ttk.Label(self, textvariable=self.status_var, padding=(10, 0, 10, 8)).grid(
                row=2, column=0, sticky="ew"
            )

        def build_canvas(self) -> None:
            frame = ttk.Frame(self, padding=(10, 0, 10, 8))
            frame.grid(row=1, column=0, sticky="nsew")
            frame.rowconfigure(0, weight=1)
            frame.columnconfigure(0, weight=1)
            self.canvas = tk.Canvas(frame, bg="#303030", highlightthickness=0)
            self.canvas.grid(row=0, column=0, sticky="nsew")
            self.canvas.bind("<Configure>", lambda _event: self.redraw())
            self.canvas.bind("<ButtonPress-1>", self.start_stroke)
            self.canvas.bind("<B1-Motion>", self.paint)
            self.canvas.bind("<ButtonRelease-1>", self.end_stroke)
            self.canvas.bind("<Motion>", self.update_brush_cursor)

        def push_undo(self) -> None:
            self.undo_stack.append(self.image.copy())
            if len(self.undo_stack) > 20:
                self.undo_stack.pop(0)

        def canvas_to_image(self, event) -> tuple[int, int] | None:
            x = int((event.x - self.offset_x) / self.scale)
            y = int((event.y - self.offset_y) / self.scale)
            if x < 0 or y < 0 or x >= self.image.width or y >= self.image.height:
                return None
            return x, y

        def start_stroke(self, event) -> None:
            if self.canvas_to_image(event) is None:
                return
            self.stroke_active = True
            self.push_undo()
            self.paint(event)

        def end_stroke(self, _event) -> None:
            self.stroke_active = False

        def paint(self, event) -> None:
            position = self.canvas_to_image(event)
            if position is None:
                return
            x, y = position
            radius = max(1, self.brush_var.get() // 2)
            box = (
                max(0, x - radius),
                max(0, y - radius),
                min(self.image.width, x + radius),
                min(self.image.height, y + radius),
            )
            if box[0] >= box[2] or box[1] >= box[3]:
                return

            if self.tool_var.get() == "restore":
                mask = Image.new("L", (box[2] - box[0], box[3] - box[1]), 0)
                draw = ImageDraw.Draw(mask)
                draw.ellipse((0, 0, mask.width - 1, mask.height - 1), fill=255)
                source = self.base_image.crop(box)
                self.image.paste(source, (box[0], box[1]), mask)
            else:
                draw = ImageDraw.Draw(self.image)
                draw.ellipse(box, fill=(0, 0, 0, 0))

            self.redraw()
            self.update_brush_cursor(event)

        def update_brush_cursor(self, event) -> None:
            self.canvas.delete("brush")
            position = self.canvas_to_image(event)
            if position is None:
                return
            radius = max(2, (self.brush_var.get() * self.scale) / 2)
            self.canvas.create_oval(
                event.x - radius,
                event.y - radius,
                event.x + radius,
                event.y + radius,
                outline="#00aaff" if self.tool_var.get() == "restore" else "#ff5050",
                width=2,
                tags="brush",
            )

        def redraw(self) -> None:
            if not hasattr(self, "canvas"):
                return
            canvas_w = max(320, self.canvas.winfo_width())
            canvas_h = max(320, self.canvas.winfo_height())
            available_w = max(50, canvas_w - 24)
            available_h = max(50, canvas_h - 24)
            self.scale = min(available_w / self.image.width, available_h / self.image.height, 1.0)
            display_size = (
                max(1, int(self.image.width * self.scale)),
                max(1, int(self.image.height * self.scale)),
            )
            self.offset_x = (canvas_w - display_size[0]) // 2
            self.offset_y = (canvas_h - display_size[1]) // 2

            display = self.image.resize(display_size, Image.Resampling.LANCZOS)
            checker = make_checkerboard(display_size, tile=max(8, int(16 * self.scale)))
            checker = checker.convert("RGBA")
            checker.alpha_composite(display)
            self.preview_photo = ImageTk.PhotoImage(checker)
            self.canvas.delete("all")
            self.canvas.create_image(self.offset_x, self.offset_y, image=self.preview_photo, anchor="nw")
            self.canvas.create_rectangle(
                self.offset_x,
                self.offset_y,
                self.offset_x + display_size[0],
                self.offset_y + display_size[1],
                outline="#666666",
            )

        def undo(self) -> None:
            if not self.undo_stack:
                return
            self.image = self.undo_stack.pop()
            self.redraw()
            self.status_var.set("Ultima pincelada desfeita.")

        def reset(self) -> None:
            self.push_undo()
            self.image = self.base_image.copy()
            self.redraw()
            self.status_var.set("Edicao manual resetada.")

        def apply(self) -> None:
            self.on_apply(self.image.copy())
            self.destroy()

    class App(tk.Tk):
        def __init__(self) -> None:
            super().__init__()
            self.title("Removedor de Fundo")
            self.geometry("980x700")
            self.minsize(860, 620)

            self.input_var = tk.StringVar()
            self.output_var = tk.StringVar()
            self.mode_var = tk.StringVar(value="auto")
            self.api_key_var = tk.StringVar(value=os.getenv("REMOVE_BG_API_KEY", ""))
            self.api_size_var = tk.StringVar(value="auto")
            self.color_var = tk.StringVar(value="")
            self.tolerance_var = tk.IntVar(value=38)
            self.soft_var = tk.BooleanVar(value=True)
            self.enhance_var = tk.BooleanVar(value=True)
            self.upscale_var = tk.StringVar(value="1")
            self.fill_var = tk.StringVar(value="transparent")
            self.status_var = tk.StringVar(value=self.ai_status_text())
            self.preview_photo = None
            self.current_result: Image.Image | None = None
            self.current_input_path: str | None = None

            self.columnconfigure(0, weight=0)
            self.columnconfigure(1, weight=1)
            self.rowconfigure(0, weight=1)
            self.build_controls()
            self.build_preview()

        def ai_status_text(self) -> str:
            if os.getenv("REMOVE_BG_API_KEY"):
                return "Pronto. Modo Auto usa API remove.bg."
            if has_rembg():
                return "Pronto. Modo Auto usa AI local/rembg."
            return "Pronto. Para recorte mais preciso, use modo API com chave remove.bg."

        def build_controls(self) -> None:
            panel = ttk.Frame(self, padding=14)
            panel.grid(row=0, column=0, sticky="nsw")
            panel.columnconfigure(0, weight=1)

            ttk.Label(panel, text="Imagem").grid(row=0, column=0, sticky="w")
            ttk.Entry(panel, textvariable=self.input_var, width=38).grid(row=1, column=0, sticky="ew", pady=(2, 4))
            ttk.Button(panel, text="Escolher", command=self.pick_input).grid(row=2, column=0, sticky="ew", pady=(0, 10))

            ttk.Label(panel, text="Salvar como").grid(row=3, column=0, sticky="w")
            ttk.Entry(panel, textvariable=self.output_var, width=38).grid(row=4, column=0, sticky="ew", pady=(2, 4))
            ttk.Button(panel, text="Destino", command=self.pick_output).grid(row=5, column=0, sticky="ew", pady=(0, 10))

            ttk.Label(panel, text="Modo").grid(row=6, column=0, sticky="w")
            mode = ttk.Combobox(
                panel,
                textvariable=self.mode_var,
                values=("auto", "api", "ai", "border", "checker"),
                state="readonly",
            )
            mode.grid(row=7, column=0, sticky="ew", pady=(2, 10))

            ttk.Label(panel, text="Chave remove.bg API (opcional)").grid(row=8, column=0, sticky="w")
            ttk.Entry(panel, textvariable=self.api_key_var, show="*").grid(row=9, column=0, sticky="ew", pady=(2, 4))

            ttk.Label(panel, text="Tamanho API").grid(row=10, column=0, sticky="w")
            ttk.Combobox(
                panel,
                textvariable=self.api_size_var,
                values=("auto", "preview", "full", "50MP"),
                state="readonly",
            ).grid(row=11, column=0, sticky="ew", pady=(2, 8))

            ttk.Label(panel, text="Cor manual (#RRGGBB, opcional)").grid(row=12, column=0, sticky="w")
            ttk.Entry(panel, textvariable=self.color_var).grid(row=13, column=0, sticky="ew", pady=(2, 8))

            ttk.Label(panel, text="Tolerancia").grid(row=14, column=0, sticky="w")
            ttk.Scale(
                panel,
                from_=5,
                to=120,
                orient="horizontal",
                variable=self.tolerance_var,
            ).grid(row=15, column=0, sticky="ew", pady=(0, 4))
            ttk.Label(panel, textvariable=self.tolerance_var).grid(row=16, column=0, sticky="w", pady=(0, 8))

            ttk.Checkbutton(panel, text="Bordas suaves", variable=self.soft_var).grid(row=17, column=0, sticky="w")
            ttk.Checkbutton(panel, text="Melhorar nitidez/cor", variable=self.enhance_var).grid(row=18, column=0, sticky="w")

            ttk.Label(panel, text="Aumentar tamanho").grid(row=19, column=0, sticky="w", pady=(10, 0))
            ttk.Combobox(
                panel,
                textvariable=self.upscale_var,
                values=("1", "1.5", "2"),
                state="readonly",
            ).grid(row=20, column=0, sticky="ew", pady=(2, 8))

            ttk.Label(panel, text="Fundo final").grid(row=21, column=0, sticky="w")
            ttk.Combobox(
                panel,
                textvariable=self.fill_var,
                values=("transparent", "white", "black"),
                state="readonly",
            ).grid(row=22, column=0, sticky="ew", pady=(2, 12))

            ttk.Button(panel, text="Previsualizar", command=self.preview).grid(row=23, column=0, sticky="ew", pady=(0, 6))
            ttk.Button(panel, text="Editar manualmente", command=self.open_manual_editor).grid(
                row=24, column=0, sticky="ew", pady=(0, 6)
            )
            ttk.Button(panel, text="Salvar PNG", command=self.save_one).grid(row=25, column=0, sticky="ew", pady=(0, 6))
            ttk.Button(panel, text="Processar pasta", command=self.batch).grid(row=26, column=0, sticky="ew", pady=(0, 12))
            ttk.Label(panel, textvariable=self.status_var, wraplength=270).grid(row=27, column=0, sticky="ew")

        def build_preview(self) -> None:
            frame = ttk.Frame(self, padding=(0, 14, 14, 14))
            frame.grid(row=0, column=1, sticky="nsew")
            frame.rowconfigure(0, weight=1)
            frame.columnconfigure(0, weight=1)
            self.canvas = tk.Canvas(frame, bg="#f4f4f4", highlightthickness=0)
            self.canvas.grid(row=0, column=0, sticky="nsew")
            self.canvas.create_text(
                360,
                260,
                text="Escolha uma imagem para ver a previsualizacao",
                fill="#555555",
                font=("Segoe UI", 14),
            )

        def options(self) -> RemoveOptions:
            fill_lookup = {
                "transparent": None,
                "white": (255, 255, 255),
                "black": (0, 0, 0),
            }
            return RemoveOptions(
                mode=self.mode_var.get(),
                key_color=parse_color(self.color_var.get()),
                tolerance=self.tolerance_var.get(),
                soft_edges=self.soft_var.get(),
                enhance=self.enhance_var.get(),
                upscale=float(self.upscale_var.get()),
                fill=fill_lookup[self.fill_var.get()],
                api_key=self.api_key_var.get(),
                api_size=self.api_size_var.get(),
            )

        def pick_input(self) -> None:
            path = filedialog.askopenfilename(
                title="Escolha a imagem",
                filetypes=(("Imagens", "*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff"), ("Todos", "*.*")),
            )
            if not path:
                return
            self.input_var.set(path)
            self.output_var.set(str(default_output_path(path)))
            self.preview()

        def pick_output(self) -> None:
            initial = self.output_var.get() or "imagem-sem-fundo.png"
            path = filedialog.asksaveasfilename(
                title="Salvar PNG",
                initialfile=Path(initial).name,
                defaultextension=".png",
                filetypes=(("PNG transparente", "*.png"), ("WebP", "*.webp"), ("JPEG", "*.jpg")),
            )
            if path:
                self.output_var.set(path)

        def preview(self) -> None:
            input_path = self.input_var.get()
            if not input_path:
                return
            try:
                image = Image.open(input_path)
                image = ImageOps.exif_transpose(image)
                opts = self.options()
                opts.upscale = 1
                result = self.process_for_preview(input_path, image, opts)
                self.current_result = result.copy()
                self.current_input_path = input_path
                self.show_preview(self.preview_display_image(result))
                self.status_var.set("Previsualizacao atualizada.")
            except Exception as exc:
                messagebox.showerror("Erro", str(exc))
                self.status_var.set("Nao foi possivel previsualizar.")

        def process_for_preview(self, input_path: str, image: Image.Image, opts: RemoveOptions) -> Image.Image:
            mode = opts.mode.lower()
            use_api = mode in {"api", "removebg-api"} or (mode == "auto" and get_removebg_api_key(opts))
            if use_api:
                result = remove_with_removebg_api(input_path, opts)
            elif mode in {"ai", "rembg"} or (mode == "auto" and has_rembg()):
                result = remove_with_rembg(image)
            elif image.mode == "RGBA" and image.getchannel("A").getextrema()[0] < 255:
                result = image.convert("RGBA")
            else:
                result = remove_local(image, opts)
            if opts.enhance:
                result = enhance_image(result)
            return result.convert("RGBA")

        def preview_display_image(self, image: Image.Image) -> Image.Image:
            return composite_fill(image.convert("RGBA"), self.options().fill).convert("RGBA")

        def show_preview(self, image: Image.Image) -> None:
            self.canvas.delete("all")
            canvas_w = max(320, self.canvas.winfo_width())
            canvas_h = max(320, self.canvas.winfo_height())
            display = image.copy()
            display.thumbnail((canvas_w - 30, canvas_h - 30), Image.Resampling.LANCZOS)
            checker = make_checkerboard(display.size)
            checker = checker.convert("RGBA")
            checker.alpha_composite(display)
            self.preview_photo = ImageTk.PhotoImage(checker)
            self.canvas.create_image(canvas_w // 2, canvas_h // 2, image=self.preview_photo)

        def open_manual_editor(self) -> None:
            input_path = self.input_var.get()
            if not input_path:
                messagebox.showinfo("Imagem", "Escolha uma imagem primeiro.")
                return
            if self.current_result is None or self.current_input_path != input_path:
                self.preview()
            if self.current_result is None:
                return

            def apply_edit(edited: Image.Image) -> None:
                self.current_result = edited.convert("RGBA")
                self.current_input_path = input_path
                self.show_preview(self.preview_display_image(self.current_result))
                self.status_var.set("Edicao manual aplicada. Agora voce pode salvar o PNG.")

            ManualEditor(self, self.current_result, apply_edit)

        def run_threaded(self, label: str, target) -> None:
            self.status_var.set(label)

            def worker() -> None:
                try:
                    message = target()
                except Exception as exc:
                    self.after(0, lambda: messagebox.showerror("Erro", str(exc)))
                    self.after(0, lambda: self.status_var.set("Erro ao processar."))
                else:
                    self.after(0, lambda: self.status_var.set(message))

            threading.Thread(target=worker, daemon=True).start()

        def save_one(self) -> None:
            input_path = self.input_var.get()
            output_path = self.output_var.get()
            if not input_path:
                messagebox.showinfo("Imagem", "Escolha uma imagem primeiro.")
                return
            if not output_path:
                output_path = str(default_output_path(input_path))
                self.output_var.set(output_path)

            def task() -> str:
                opts = self.options()
                if self.current_result is not None and self.current_input_path == input_path:
                    saved = save_output_image(self.current_result, output_path, opts)
                else:
                    saved = process_image(input_path, output_path, opts)
                return f"Salvo em: {saved}"

            self.run_threaded("Processando imagem...", task)

        def batch(self) -> None:
            input_dir = filedialog.askdirectory(title="Pasta com imagens")
            if not input_dir:
                return
            output_dir = filedialog.askdirectory(title="Pasta para salvar")
            if not output_dir:
                return

            def task() -> str:
                outputs = process_batch(input_dir, output_dir, self.options())
                return f"{len(outputs)} imagem(ns) salvas em: {output_dir}"

            self.run_threaded("Processando pasta...", task)

    App().mainloop()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Remove fundo de imagens e salva PNG transparente.")
    parser.add_argument("input", nargs="?", help="Imagem de entrada.")
    parser.add_argument("-o", "--output", help="Arquivo de saida. Padrao: <nome>-sem-fundo.png")
    parser.add_argument("--batch", help="Processa todas as imagens de uma pasta.")
    parser.add_argument("--out-dir", help="Pasta de saida para lote.")
    parser.add_argument("--mode", default="auto", choices=("auto", "api", "removebg-api", "ai", "rembg", "border", "checker"))
    parser.add_argument("--api-key", help="Chave da API remove.bg. Se omitida, usa REMOVE_BG_API_KEY.")
    parser.add_argument("--api-size", default="auto", help="Tamanho pedido a API remove.bg: auto, preview, full ou 50MP.")
    parser.add_argument("--key-color", help="Cor do fundo/chroma em #RRGGBB.")
    parser.add_argument("--tolerance", type=int, default=38)
    parser.add_argument("--hard-edge", action="store_true", help="Desativa borda suave.")
    parser.add_argument("--no-enhance", action="store_true", help="Desativa melhoria de nitidez/cor.")
    parser.add_argument("--upscale", type=float, default=1.0, choices=(1.0, 1.5, 2.0))
    parser.add_argument("--fill", choices=("transparent", "white", "black"), default="transparent")
    parser.add_argument("--gui", action="store_true", help="Abre a interface grafica.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.gui or (not args.input and not args.batch):
        launch_gui()
        return 0

    fill_lookup = {
        "transparent": None,
        "white": (255, 255, 255),
        "black": (0, 0, 0),
    }
    options = RemoveOptions(
        mode=args.mode,
        key_color=parse_color(args.key_color),
        tolerance=args.tolerance,
        soft_edges=not args.hard_edge,
        enhance=not args.no_enhance,
        upscale=args.upscale,
        fill=fill_lookup[args.fill],
        api_key=args.api_key,
        api_size=args.api_size,
    )

    if args.batch:
        out_dir = args.out_dir or str(Path(args.batch) / "sem-fundo")
        outputs = process_batch(args.batch, out_dir, options)
        print(f"{len(outputs)} imagem(ns) salvas em {out_dir}")
        return 0

    if not args.input:
        parser.error("informe uma imagem ou use --gui")

    output = args.output or default_output_path(args.input)
    saved = process_image(args.input, output, options)
    print(f"Salvo em: {saved}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Erro: {exc}")
        raise SystemExit(1)
