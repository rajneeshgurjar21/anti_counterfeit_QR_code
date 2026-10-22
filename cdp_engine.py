"""
Anti-Counterfeit QR Code Engine with Copy Detection Pattern (CDP)
================================================================
Generates secure 2D barcodes embedding high-entropy micro-dot patterns 
with fiducial registration marks inside standard QR codes.
"""

import hashlib
import numpy as np
from PIL import Image, ImageDraw
import qrcode
from qrcode.constants import ERROR_CORRECT_H

def generate_cdp_pattern(seed_str: str, grid_size: int = 120, dot_size: int = 2, density: float = 0.5) -> Image.Image:
    """
    Generate a deterministic pseudo-random micro-dot Copy Detection Pattern (CDP).
    
    Args:
        seed_str: Unique product/serial key used as cryptographic PRNG seed.
        grid_size: Number of micro-cells in width and height (e.g. 120x120).
        dot_size: Pixel size of each micro-cell (e.g. 2px per cell for 240x240 px image).
        density: Target density of black dots (typically 0.45 - 0.50 for maximum entropy).
        
    Returns:
        PIL Image of the raw high-frequency micro-dot texture.
    """
    # Deterministic seed using SHA-256 (32-bit for legacy RandomState or SeedSequence)
    hash_digest = hashlib.sha256(seed_str.encode('utf-8')).digest()
    seed_int = int.from_bytes(hash_digest[:4], byteorder='big')
    rng = np.random.default_rng(seed_int)
    
    # Generate binary pseudo-random matrix with given density
    # Maximum Shannon entropy is achieved near 50% density
    noise_matrix = rng.random((grid_size, grid_size)) < density
    
    # Scale up each micro-dot by dot_size to make it printable at desired DPI
    raw_array = np.kron(noise_matrix.astype(np.uint8) * 255, np.ones((dot_size, dot_size), dtype=np.uint8))
    
    # Invert so black dots are 0 and white background is 255
    raw_array = 255 - raw_array
    
    return Image.fromarray(raw_array, mode='L')


def generate_cdp_module_with_fiducials(
    seed_str: str, 
    pattern_grid_size: int = 100, 
    dot_size: int = 2, 
    margin_cells: int = 14
) -> Image.Image:
    """
    Generate the complete CDP module:
    - High-density micro-dot pattern in the center.
    - Quiet zone / margin.
    - Fiducial registration marks (small squares) along the perimeter for sub-pixel camera alignment.
    - Orientation mark at bottom-right corner.
    
    Matches the exact layout shown in the reference image.
    """
    # 1. Generate inner micro-dot pattern
    core_pattern = generate_cdp_pattern(seed_str, grid_size=pattern_grid_size, dot_size=dot_size)
    core_w, core_h = core_pattern.size
    
    # Margin in pixels
    margin_px = margin_cells * dot_size
    total_w = core_w + 2 * margin_px
    total_h = core_h + 2 * margin_px
    
    # Create white canvas
    cdp_img = Image.new('L', (total_w, total_h), color=255)
    draw = ImageDraw.Draw(cdp_img)
    
    # Paste core micro-dot pattern into center
    cdp_img.paste(core_pattern, (margin_px, margin_px))
    
    # Draw fiducial registration markers (small black squares)
    # The reference image has 4 corner markers + 2 markers per side (total 12 markers around border)
    fid_size = int(dot_size * 5)  # size of fiducial square
    fid_offset = int(margin_px / 2)  # distance from outer edge
    
    # Side positions along each edge: 0.15, 0.50, 0.85
    positions = [
        fid_offset, 
        total_w // 2 - fid_size // 2, 
        total_w - fid_offset - fid_size
    ]
    
    # Top and Bottom rows
    for x in positions:
        # Top edge
        draw.rectangle([x, fid_offset, x + fid_size, fid_offset + fid_size], fill=0)
        # Bottom edge
        draw.rectangle([x, total_h - fid_offset - fid_size, x + fid_size, total_h - fid_offset], fill=0)
        
    # Left and Right columns (intermediate markers)
    mid_y = total_h // 2 - fid_size // 2
    # Left edge
    draw.rectangle([fid_offset, mid_y, fid_offset + fid_size, mid_y + fid_size], fill=0)
    # Right edge
    draw.rectangle([total_w - fid_offset - fid_size, mid_y, total_w - fid_offset, mid_y + fid_size], fill=0)
    
    # Add asymmetric orientation marker at bottom-right corner:
    # A small nested square or distinctive mark to prevent 90/180/270 rotation ambiguity
    ori_x = total_w - fid_offset - fid_size
    ori_y = total_h - fid_offset - fid_size
    # Clear inner center of this marker to make it a hollow square (as seen in reference image bottom right!)
    inner_pad = max(1, dot_size)
    draw.rectangle([ori_x + inner_pad, ori_y + inner_pad, ori_x + fid_size - inner_pad, ori_y + fid_size - inner_pad], fill=255)
    
    return cdp_img


def create_anti_counterfeit_qr(
    payload: str, 
    serial_no: str, 
    output_path: str = None,
    box_size: int = 12,
    border: int = 4,
    cdp_ratio: float = 0.32
) -> tuple[Image.Image, Image.Image]:
    """
    Creates a full Anti-Counterfeit QR Code:
    1. Encodes payload into a high-error-correction (Level H) QR code.
    2. Clears the center region (within the 30% error correction allowance).
    3. Generates the Copy Detection Pattern (CDP) keyed to `serial_no`.
    4. Pastes the CDP seamlessly into the QR center.
    
    Args:
        payload: URL or text encoded in the standard QR code (e.g. verification URL).
        serial_no: Unique product ID / cryptographic seed for the CDP.
        output_path: Optional file path to save the final QR code image.
        box_size: Size of each QR module in pixels.
        border: Quiet zone width in modules.
        cdp_ratio: Fractional width of the QR code occupied by the central CDP (typically 0.28 - 0.34).
        
    Returns:
        (composite_qr_image, standalone_cdp_image)
    """
    # 1. Generate base QR code with High error correction (Level H: 30% recovery)
    qr = qrcode.QRCode(
        version=None,  # Auto-fit version
        error_correction=ERROR_CORRECT_H,
        box_size=box_size,
        border=border,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    
    # Render base QR image
    qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    qr_w, qr_h = qr_img.size
    
    # 2. Determine center cutout size
    # With Level H, we can safely overwrite up to 25-30% of the area in the center
    # without damaging the 3 finder patterns or exceeding reed-solomon capacity.
    center_w = int(qr_w * cdp_ratio)
    # Make it even
    if center_w % 2 != 0:
        center_w += 1
    center_h = center_w
    
    center_x = (qr_w - center_w) // 2
    center_y = (qr_h - center_h) // 2
    
    # 3. Generate CDP module with matching pixel dimensions
    # Calculate grid size & dot size to fit perfectly into center_w
    dot_size = max(1, box_size // 5)  # Fine micro-dot resolution
    margin_cells = 10
    pattern_grid_size = (center_w - 2 * margin_cells * dot_size) // dot_size
    
    cdp_img = generate_cdp_module_with_fiducials(
        seed_str=serial_no,
        pattern_grid_size=pattern_grid_size,
        dot_size=dot_size,
        margin_cells=margin_cells
    )
    # Resize slightly if needed for exact fit
    cdp_img_resized = cdp_img.resize((center_w, center_h), Image.Resampling.NEAREST).convert('RGB')
    
    # 4. Clear center of QR code (white cutout)
    draw = ImageDraw.Draw(qr_img)
    draw.rectangle([center_x, center_y, center_x + center_w, center_y + center_h], fill="white")
    
    # 5. Composite CDP into QR center
    qr_img.paste(cdp_img_resized, (center_x, center_y))
    
    if output_path:
        qr_img.save(output_path, "PNG", dpi=(600, 600))
        
    return qr_img, cdp_img_resized
