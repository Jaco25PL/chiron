"""Shrinks a VRM for the web by downscaling its embedded textures, keeping every VRM extension.

    python web/scripts/slim_vrm.py in.vrm out.vrm [--max 1024] [--normal 512]

Generic glTF optimizers drop the VRMC_* extensions (expressions, MToon, spring bones), so this edits
the GLB directly: each image is resized and re-encoded, the binary buffer is rebuilt with the new
image bytes, and the JSON is left as is apart from offsets and lengths. Normal maps (names ending
in _nml) get a smaller cap, and the embedded thumbnail is cut to 256 px. Needs Pillow.
"""

import argparse
import io
import json
import struct

from PIL import Image


def pad4(b: bytes, fill: bytes = b"\0") -> bytes:
    return b + fill * (-len(b) % 4)


def shrink(data: bytes, mime: str, cap: int) -> bytes:
    img = Image.open(io.BytesIO(data))
    if max(img.size) <= cap:
        return data
    img.thumbnail((cap, cap), Image.LANCZOS)
    out = io.BytesIO()
    if mime == "image/jpeg":
        img.convert("RGB").save(out, "JPEG", quality=88, optimize=True)
    else:
        img.save(out, "PNG", optimize=True)
    return out.getvalue()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--max", type=int, default=1024, help="largest side of color textures")
    ap.add_argument("--normal", type=int, default=512, help="largest side of normal maps")
    args = ap.parse_args()

    raw = open(args.src, "rb").read()
    magic, version, _ = struct.unpack("<4sII", raw[:12])
    assert magic == b"glTF" and version == 2, "not a GLB v2 file"
    json_len = struct.unpack("<I", raw[12:16])[0]
    gltf = json.loads(raw[20:20 + json_len])
    bin_start = 20 + json_len + 8
    blob = raw[bin_start:bin_start + struct.unpack("<I", raw[20 + json_len:24 + json_len])[0]]

    views = gltf["bufferViews"]
    chunks = [blob[v.get("byteOffset", 0):v.get("byteOffset", 0) + v["byteLength"]] for v in views]
    thumb = gltf.get("extensions", {}).get("VRMC_vrm", {}).get("meta", {}).get("thumbnailImage")
    before = sum(len(chunks[im["bufferView"]]) for im in gltf["images"])
    for i, im in enumerate(gltf["images"]):
        name = im.get("name", "")
        cap = 256 if i == thumb else args.normal if name.endswith("_nml") else args.max
        chunks[im["bufferView"]] = shrink(chunks[im["bufferView"]], im["mimeType"], cap)
    after = sum(len(chunks[im["bufferView"]]) for im in gltf["images"])

    # rebuild the buffer: same views, same order, 4-byte aligned (accessors need it)
    new_blob = b""
    for v, c in zip(views, chunks):
        new_blob = pad4(new_blob)
        v["byteOffset"] = len(new_blob)
        v["byteLength"] = len(c)
        new_blob += c
    new_blob = pad4(new_blob)
    gltf["buffers"][0]["byteLength"] = len(new_blob)

    js = pad4(json.dumps(gltf, separators=(",", ":")).encode(), b" ")
    body = struct.pack("<I4s", len(js), b"JSON") + js + struct.pack("<I4s", len(new_blob), b"BIN\0") + new_blob
    with open(args.dst, "wb") as f:
        f.write(struct.pack("<4sII", b"glTF", 2, 12 + len(body)) + body)
    print(f"{len(raw) / 1e6:.1f} MB -> {(12 + len(body)) / 1e6:.1f} MB (textures {before / 1e6:.1f} -> {after / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
