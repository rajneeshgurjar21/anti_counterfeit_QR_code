import cv2
import numpy as np

def compute_fft_hf_ratio(gray, cutoff_ratio=0.20):
    f = np.fft.fft2(gray.astype(np.float32))
    fshift = np.fft.fftshift(f)
    mag = np.abs(fshift)**2
    h, w = gray.shape
    cy, cx = h // 2, w // 2
    y, x = np.ogrid[:h, :w]
    dist = np.sqrt((x - cx)**2 + (y - cy)**2)
    cutoff = min(h, w) * cutoff_ratio
    low = np.sum(mag[dist <= cutoff])
    high = np.sum(mag[dist > cutoff])
    total = low + high
    return float(high / total) if total > 0 else 0.0

master = cv2.imread("master_anti_counterfeit_qr.png", 0)
h, w = master.shape
cw = int(w * 0.32)
x1, y1 = (w - cw) // 2, (h - cw) // 2
master_crop = master[y1+20:y1+cw-20, x1+20:x1+cw-20]

gen_scan = cv2.imread("sample_genuine_scan.png", 0)
gen_crop = gen_scan[y1+20:y1+cw-20, x1+20:x1+cw-20]

fake_scan = cv2.imread("sample_counterfeit_reprint.png", 0)
fake_crop = fake_scan[y1+20:y1+cw-20, x1+20:x1+cw-20]

samples = {
    "1. Master Digital (Pristine)": master_crop,
    "2. Blurred sigma=0.6": cv2.GaussianBlur(master_crop, (0, 0), 0.6),
    "3. Blurred sigma=0.8": cv2.GaussianBlur(master_crop, (0, 0), 0.8),
    "4. Blurred sigma=1.2": cv2.GaussianBlur(master_crop, (0, 0), 1.2),
    "5. Genuine Mobile Scan": gen_crop,
    "6. Counterfeit Reprint": fake_crop,
}

print(f"{'Sample':<32} | {'Laplacian':<10} | {'FFT HF':<10} | {'Sobel Grad':<10}")
print("-" * 70)
for name, img in samples.items():
    lap = cv2.Laplacian(img, cv2.CV_64F).var()
    hf = compute_fft_hf_ratio(img, cutoff_ratio=0.20)
    sobelx = cv2.Sobel(img, cv2.CV_64F, 1, 0, ksize=3)
    sobely = cv2.Sobel(img, cv2.CV_64F, 0, 1, ksize=3)
    grad = np.mean(np.sqrt(sobelx**2 + sobely**2))
    print(f"{name:<32} | {lap:<10.1f} | {hf:<10.4f} | {grad:<10.1f}")
