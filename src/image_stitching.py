import cv2
import numpy as np
import os


def load_images(input_dir):
    images = []
    filenames = sorted(os.listdir(input_dir))

    for filename in filenames:
        if filename.lower().endswith((".jpg", ".jpeg", ".png")):
            path = os.path.join(input_dir, filename)
            img = cv2.imread(path)
            if img is not None:
                images.append(img)
                print(f"Loaded: {filename}")

    return images


def detect_and_match(img1, img2):
    gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)

    orb = cv2.ORB_create(8000)

    kp1, des1 = orb.detectAndCompute(gray1, None)
    kp2, des2 = orb.detectAndCompute(gray2, None)

    if des1 is None or des2 is None:
        return kp1, kp2, []

    bf = cv2.BFMatcher(cv2.NORM_HAMMING)
    matches = bf.knnMatch(des1, des2, k=2)

    good_matches = []
    for pair in matches:
        if len(pair) == 2:
            m, n = pair
            if m.distance < 0.7 * n.distance:
                good_matches.append(m)

    return kp1, kp2, good_matches


def compute_homography(img1, img2):
    """img1을 img2 기준으로 변환하는 Homography 계산"""
    kp1, kp2, matches = detect_and_match(img1, img2)

    print(f"  Good matches: {len(matches)}")

    if len(matches) < 10:
        print("  Not enough good matches")
        return None

    src_pts = np.float32([kp1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)

    H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 3.0)

    if H is None:
        print("  Homography computation failed")
        return None

    inliers = mask.ravel().sum()
    print(f"  Inliers: {inliers}/{len(matches)}")

    if inliers < 8:
        print("  Not enough inliers")
        return None

    return H


def crop_black_area(img):
    """검은 영역 크롭 - 노이즈 픽셀 필터링 포함"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # 작은 노이즈 제거를 위해 약간의 blur 적용
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    _, thresh = cv2.threshold(blurred, 5, 255, cv2.THRESH_BINARY)

    # morphology로 작은 구멍/노이즈 제거
    kernel = np.ones((10, 10), np.uint8)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        return img

    # 가장 큰 contour만 사용 (노이즈 픽셀 무시)
    largest = max(contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(largest)

    return img[y:y+h, x:x+w]


def linear_blend(panorama, warped, mask_pano, mask_warp):
    """
    오버랩 영역에서 선형 블렌딩 적용
    - mask_pano: 파노라마의 유효 픽셀 마스크
    - mask_warp: 새로 warping된 이미지의 유효 픽셀 마스크
    """
    result = panorama.copy()

    # 오버랩 영역
    overlap = (mask_pano > 0) & (mask_warp > 0)
    # warped만 있는 영역
    only_warp = (mask_pano == 0) & (mask_warp > 0)

    # warped만 있는 부분은 그냥 복사
    result[only_warp] = warped[only_warp]

    if not np.any(overlap):
        return result

    # 오버랩 영역에서 distance transform으로 가중치 계산
    dist_pano = cv2.distanceTransform(mask_pano, cv2.DIST_L2, 5)
    dist_warp = cv2.distanceTransform(mask_warp, cv2.DIST_L2, 5)

    # 정규화
    total = dist_pano + dist_warp
    total[total == 0] = 1  # 0 나누기 방지

    alpha_pano = dist_pano / total
    alpha_warp = dist_warp / total

    # 오버랩 영역에 블렌딩 적용
    for c in range(3):
        result[:, :, c][overlap] = (
            alpha_pano[overlap] * panorama[:, :, c][overlap] +
            alpha_warp[overlap] * warped[:, :, c][overlap]
        ).astype(np.uint8)

    return result


def get_valid_mask(img):
    """이미지에서 유효한 픽셀(검은색이 아닌) 마스크 반환"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(gray, 1, 255, cv2.THRESH_BINARY)
    return mask


def warp_image_to_canvas(img, H, canvas_size, translation):
    """이미지를 translation 포함한 Homography로 캔버스에 warping"""
    T = np.array([
        [1, 0, translation[0]],
        [0, 1, translation[1]],
        [0, 0, 1]
    ], dtype=np.float64)
    return cv2.warpPerspective(img, T @ H, canvas_size)


def place_on_canvas(img, canvas_size, offset_x, offset_y):
    """이미지를 캔버스에 배치 (Homography 없이 단순 이동)"""
    canvas = np.zeros((canvas_size[1], canvas_size[0], 3), dtype=np.uint8)
    h, w = img.shape[:2]

    x1, y1 = offset_x, offset_y
    x2, y2 = x1 + w, y1 + h

    # 캔버스 범위 내로 클리핑
    cx1 = max(x1, 0)
    cy1 = max(y1, 0)
    cx2 = min(x2, canvas_size[0])
    cy2 = min(y2, canvas_size[1])

    ix1 = cx1 - x1
    iy1 = cy1 - y1
    ix2 = ix1 + (cx2 - cx1)
    iy2 = iy1 + (cy2 - cy1)

    canvas[cy1:cy2, cx1:cx2] = img[iy1:iy2, ix1:ix2]
    return canvas


def stitch_images(images):
    """
    N장의 이미지를 스티칭 (3장 이상 지원)
    - 중앙 이미지를 기준으로 좌우 확장
    - 중앙이 없으면 순차적으로 스티칭
    """
    n = len(images)

    if n == 1:
        return images[0]

    # 중앙 이미지를 기준으로 설정
    center_idx = n // 2
    center = images[center_idx]

    print(f"Total images: {n}, Center index: {center_idx}")

    # 각 이미지에 대한 Homography 계산 (center 기준)
    homographies = {}
    homographies[center_idx] = np.eye(3)  # center는 identity

    # 왼쪽 이미지들: 인접 이미지 간 homography 누적
    print("\n--- Computing left homographies ---")
    H_accum = np.eye(3)
    for i in range(center_idx - 1, -1, -1):
        print(f"  Image {i} -> {i+1}")
        H = compute_homography(images[i], images[i + 1])
        if H is None:
            print(f"  Failed to compute homography for image {i}, stopping left side")
            break
        H_accum = H_accum @ H  # 누적
        homographies[i] = H_accum

    # 오른쪽 이미지들: 인접 이미지 간 homography 누적
    print("\n--- Computing right homographies ---")
    H_accum = np.eye(3)
    for i in range(center_idx + 1, n):
        print(f"  Image {i} -> {i-1}")
        H = compute_homography(images[i], images[i - 1])
        if H is None:
            print(f"  Failed to compute homography for image {i}, stopping right side")
            break
        H_accum = H_accum @ H  # 누적
        homographies[i] = H_accum

    if len(homographies) < 2:
        print("Not enough valid homographies")
        return center

    # 캔버스 크기 계산: 모든 이미지 코너를 변환해서 bounding box
    all_corners = []

    for idx, H in homographies.items():
        h, w = images[idx].shape[:2]
        corners = np.float32([
            [0, 0], [0, h], [w, h], [w, 0]
        ]).reshape(-1, 1, 2)
        warped_corners = cv2.perspectiveTransform(corners, H)
        all_corners.append(warped_corners)

    all_corners = np.concatenate(all_corners, axis=0)
    xmin, ymin = np.int32(all_corners.min(axis=0).ravel() - 0.5)
    xmax, ymax = np.int32(all_corners.max(axis=0).ravel() + 0.5)

    translation = [-xmin, -ymin]
    canvas_width = xmax - xmin
    canvas_height = ymax - ymin

    print(f"\nCanvas size: {canvas_width} x {canvas_height}")
    print(f"Translation: {translation}")

    # 캔버스에 이미지들을 순서대로 합성 (블렌딩 포함)
    panorama = np.zeros((canvas_height, canvas_width, 3), dtype=np.uint8)
    pano_mask = np.zeros((canvas_height, canvas_width), dtype=np.uint8)

    # center부터 배치, 그 다음 좌우 순서로
    order = [center_idx]
    for dist in range(1, n):
        if center_idx - dist >= 0 and (center_idx - dist) in homographies:
            order.append(center_idx - dist)
        if center_idx + dist < n and (center_idx + dist) in homographies:
            order.append(center_idx + dist)

    for idx in order:
        H = homographies[idx]
        img = images[idx]

        if idx == center_idx:
            # center는 단순 배치
            warped = place_on_canvas(img, (canvas_width, canvas_height), translation[0], translation[1])
        else:
            warped = warp_image_to_canvas(img, H, (canvas_width, canvas_height), translation)

        warp_mask = get_valid_mask(warped)

        if not np.any(pano_mask):
            # 첫 번째 이미지는 그냥 복사
            panorama = warped.copy()
            pano_mask = warp_mask.copy()
        else:
            # 블렌딩 적용
            panorama = linear_blend(panorama, warped, pano_mask, warp_mask)
            pano_mask = cv2.bitwise_or(pano_mask, warp_mask)

    panorama = crop_black_area(panorama)
    return panorama


def main():
    input_dir = "input"
    output_dir = "results"

    os.makedirs(output_dir, exist_ok=True)

    print("=== Image Stitching ===\n")
    images = load_images(input_dir)

    if len(images) < 3:
        print(f"Please add at least 3 images. Found: {len(images)}")
        return

    print(f"\nTotal {len(images)} images loaded\n")

    panorama = stitch_images(images)

    output_path = os.path.join(output_dir, "panorama.jpg")
    cv2.imwrite(output_path, panorama)
    print(f"\nPanorama saved to {output_path}")
    print(f"Output size: {panorama.shape[1]} x {panorama.shape[0]}")


if __name__ == "__main__":
    main()