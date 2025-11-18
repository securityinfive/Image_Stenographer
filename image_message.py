# Encode: 
#           - straight text 
#         python image_message.py encode -i input.jpg -o output.png -m "secret msg" 
#           - message in a text/msg file
#         python image_message.py encode -i input.jpg -o output.png -t message.txt 
# Decode: 
#           - display the encoded output        
#         python image_message.py decode -i output.png 
#            - output encoded message to a file
#         python image_message.py decode -i output.png > output_msg.txt 


import argparse
import os
import sys
import struct
import numpy as np
import cv2

import sys
sys.stdout.reconfigure(encoding="utf-8") # force encoding to avoid charmap errors

MAGIC = b"STEG"          # 4 bytes to identify our payload
LEN_SIZE = 4             # 4 bytes (uint32) payload length in bytes
HEADER_SIZE = len(MAGIC) + LEN_SIZE  # 8 bytes
BITS_PER_BYTE = 8
def read_image(path: str) -> np.ndarray:
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise SystemExit(f"Failed to read image: {path}")
    if img.dtype != np.uint8:
        img = img.astype(np.uint8)
    return img

def to_uint8_1d(img: np.ndarray) -> np.ndarray:
    # Flatten to 1D uint8 buffer of all channels
    return img.reshape(-1)

def capacity_bits(img: np.ndarray) -> int:
    # We store 1 bit in each byte (channel) => total bytes == total bit capacity
    return img.size  # number of uint8 values == bits of capacity

def pack_payload(message_bytes: bytes) -> bytes:
    if len(message_bytes) > 0xFFFFFFFF:
        raise ValueError("Message too large.")
    return MAGIC + struct.pack(">I", len(message_bytes)) + message_bytes  # big-endian length

def unpack_header(bitstream: np.ndarray) -> tuple[int, int]:
    """
    Read first HEADER_SIZE bytes out of the bitstream and return (offset_bits, payload_len).
    bitstream: np.array of 0/1 bits (dtype uint8), 1D
    """
    header_bits_needed = HEADER_SIZE * BITS_PER_BYTE
    header_bits = bitstream[:header_bits_needed]
    header_bytes = np.packbits(header_bits).tobytes()
    magic = header_bytes[:4]
    if magic != MAGIC:
        raise ValueError("No valid payload magic detected.")
    length = struct.unpack(">I", header_bytes[4:8])[0]
    return header_bits_needed, length

def bytes_to_bits(b: bytes) -> np.ndarray:
    # Convert bytes to a 1D array of bits (0/1) MSB-first
    arr = np.frombuffer(b, dtype=np.uint8)
    return np.unpackbits(arr)

def bits_to_bytes(bits: np.ndarray) -> bytes:
    # Length must be multiple of 8
    if bits.size % 8 != 0:
        # pad with zeros (decode side usually exact, but just in case)
        pad = 8 - (bits.size % 8)
        bits = np.pad(bits, (0, pad), mode="constant")
    arr = np.packbits(bits)
    return arr.tobytes()

def embed_bits_into_lsb(img: np.ndarray, bits: np.ndarray) -> np.ndarray:
    flat = to_uint8_1d(img).copy()
    if bits.size > flat.size:
        raise ValueError(f"Not enough capacity: need {bits.size} bits, have {flat.size}.")
    # Clear LSB then OR in our bits
    flat[:bits.size] = (flat[:bits.size] & 0xFE) | bits
    return flat.reshape(img.shape)

def extract_bits_from_lsb(img: np.ndarray, num_bits: int) -> np.ndarray:
    flat = to_uint8_1d(img)
    return (flat[:num_bits] & 1).astype(np.uint8)

def encode(input_path: str, output_path: str, message: str | None, text_file: str | None):
    img = read_image(input_path)
    if img.ndim == 2:
        # grayscale is fine — single channel; just a note
        pass

    if message is None and text_file is None:
        raise SystemExit("Provide -m/--message or -t/--text-file for encode.")

    if text_file:
        with open(text_file, "r") as f:
            msg_text = f.read()
        msg_bytes = msg_text.encode("utf-8")
    else:
        msg_bytes = message.encode("utf-8")

    payload = pack_payload(msg_bytes)
    bits = bytes_to_bits(payload)

    cap = capacity_bits(img)
    if bits.size > cap:
        raise SystemExit(f"Payload too large for this image. Need {bits.size} bits, have {cap} bits.")

    stego = embed_bits_into_lsb(img, bits)

    # Warn about JPG: re-encoding may destroy bits
    ext = os.path.splitext(output_path)[1].lower()
    if ext in (".jpg", ".jpeg"):
        print("Warning: Saving as JPEG is lossy and may corrupt the hidden message. Prefer PNG or BMP.", file=sys.stderr)

    if not cv2.imwrite(output_path, stego):
        raise SystemExit(f"Failed to write: {output_path}")

    print(f"Embedded {len(msg_bytes)} bytes into {output_path}")
    if ext not in (".png", ".bmp"):
        print("Tip: Use .png or .bmp to preserve hidden data.", file=sys.stderr)

def decode(input_path: str, raw: bool = False):
    img = read_image(input_path)
    # Read enough bits for header
    header_bits_needed = HEADER_SIZE * BITS_PER_BYTE
    if capacity_bits(img) < header_bits_needed:
        raise SystemExit("Image too small to contain header.")
    header_bits = extract_bits_from_lsb(img, header_bits_needed)
    _, length = unpack_header(header_bits)

    total_bits_needed = header_bits_needed + length * BITS_PER_BYTE
    if capacity_bits(img) < total_bits_needed:
        raise SystemExit("Image does not contain full payload (truncated).")

    all_bits = extract_bits_from_lsb(img, total_bits_needed)
    payload_bits = all_bits[header_bits_needed:]
    data = bits_to_bytes(payload_bits)[:length]

    if raw:
        sys.stdout.buffer.write(data)
    else:
        # Try UTF-8, fallback to repr if it fails
        try:
            print(data.decode("utf-8"))
        except UnicodeDecodeError:
            print(f"<binary {len(data)} bytes>")
            sys.stdout.buffer.write(data)

def main():
    p = argparse.ArgumentParser(description="LSB steganography (OpenCV + NumPy) for JPEG/PNG/BMP images.")
    sub = p.add_subparsers(dest="cmd", required=True)

    pe = sub.add_parser("encode", help="Embed a message into an image")
    pe.add_argument("-i", "--input", required=True, help="Input image (JPG/PNG/BMP). Readable by OpenCV.")
    pe.add_argument("-o", "--output", required=True, help="Output image. Prefer PNG or BMP to preserve bits.")
    src = pe.add_mutually_exclusive_group(required=True)
    src.add_argument("-m", "--message", help="Message string to embed (UTF-8).")
    src.add_argument("-t", "--text-file", help="Path to text file. Raw bytes are embedded.")
    
    # no password/crypto here; add your own if needed

    pd = sub.add_parser("decode", help="Extract a message from an image")
    pd.add_argument("-i", "--input", required=True, help="Stego image path")
    pd.add_argument("--raw", action="store_true", help="Write raw bytes to stdout (no UTF-8 decode)")

    args = p.parse_args()

    if args.cmd == "encode":
        encode(args.input, args.output, args.message, args.text_file)
    elif args.cmd == "decode":
        decode(args.input, args.raw)

if __name__ == "__main__":
    main()
