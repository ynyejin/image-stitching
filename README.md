# Image Stitching 

## 📌 Overview
본 프로젝트는 여러 장의 이미지를 자동으로 정합하여 하나의 파노라마 이미지를 생성하는 것을 목표로 한다.  
OpenCV의 high-level API(cv::Stitcher)를 사용하지 않고, 특징점 기반의 방법을 직접 구현하였다.

---

## 🎯 목표
- 3장 이상의 입력 이미지를 사용하여 하나의 큰 이미지 생성
- 이미지 간 오버랩을 활용하여 자동 정합 수행

---

## ⚙️ Method (프로그램 설명)

본 프로그램은 다음과 같은 파이프라인으로 동작한다.

1. **Feature Detection**
   - ORB를 사용하여 특징점 추출

2. **Feature Matching**
   - BFMatcher를 이용하여 특징점 매칭
   - ratio test를 통해 좋은 매칭만 선택

3. **Homography Estimation**
   - RANSAC을 이용하여 이상치를 제거하고 Homography 계산

4. **Image Warping**
   - `warpPerspective`를 이용하여 기준 이미지에 맞게 변환

5. **Image Stitching**
   - 중앙 이미지를 기준으로 좌우 이미지 확장 방식으로 파노라마 생성

---

## ⭐ Additional Features 

### 1. Image Blending 
겹치는 영역에서 단순 덮어쓰기가 아닌 **distance transform 기반 linear blending**을 적용하여  
이미지 경계가 자연스럽게 이어지도록 구현하였다.

→ 이미지 간 경계가 눈에 띄지 않도록 개선

---

### 2. Automatic Cropping
스티칭 이후 생성되는 검은 영역을 자동으로 제거하는 기능을 구현하였다.

→ 결과 이미지의 외부 검은 여백 제거

※ 단, 내부에 발생하는 검은 영역은 제거되지 않을 수 있음

---

## 📂 Project Structure

```

image-stitching/
├── input/
│   ├── img1.png
│   ├── img2.png
│   └── img3.png
├── results/
│   └── panorama.jpg
├── src/
│   └── image_stitching.py
└── README.md

````

---

## ▶️ How to Run

```bash
python src/image_stitching.py
````

---

## 🖼️ Results

### Input Images

![img1](input/img1.png)
![img2](input/img2.png)
![img3](input/img3.png)

### Output Image

![panorama](results/panorama.jpg)

---

## ⚠️ Limitations (한계)

본 프로젝트는 Homography 기반의 스티칭을 사용하기 때문에 다음과 같은 한계가 존재한다.

* 장면이 하나의 평면이라는 가정을 기반으로 하기 때문에
  깊이 차이가 큰 경우 왜곡이 발생할 수 있음

* 넓은 시야각에서 이미지 변환 시
  이미지 외부뿐만 아니라 내부에도 빈 영역(검은 영역)이 발생할 수 있음

* 현재 구현된 Cropping 기능은
  **외부 검은 영역만 제거 가능하며 내부 빈 영역은 제거하지 못함**

---

## 🔧 Improvements (개선 방향)

다음과 같은 방법을 통해 결과를 개선할 수 있다.

### 1. 입력 이미지 개선

* 카메라 위치를 고정한 상태에서 좌우로 회전하며 촬영
* 회전 각도를 줄여 촬영 (넓은 시야각 제한)
* 인접 이미지 간 충분한 overlap 확보 (30~50%)

→ Parallax를 줄이고 왜곡 및 내부 빈 영역 감소

#### 결과 비교

- 기존 (넓은 회전 각도)
![before](results/panorama.jpg)

- 개선 (회전 각도 감소)
![after](results/after.jpg)

→ 회전 각도를 줄여 촬영했을 때 내부 검은 영역이 감소하고 스티칭 결과가 더 안정적으로 생성되는 것을 확인할 수 있었다.

---

### 2. Cropping 기능 개선

* 현재는 bounding box 기반 외곽 제거만 수행
* 내부 빈 영역까지 제거하기 위해
  **최대 직사각형 영역(maximal rectangle) 추출 알고리즘 적용 가능**

---

### 3. 고급 투영 방식 적용

* Cylindrical Projection
* Spherical Projection

→ 넓은 시야각에서 발생하는 왜곡을 효과적으로 줄일 수 있음

---

## 💡 Discussion

Homography 기반 스티칭은 장면이 하나의 평면이라고 가정하기 때문에
넓은 시야각이나 3D 구조가 포함된 경우 이미지 가장자리에서 왜곡이 발생할 수 있다.

이를 개선하기 위해서는 cylindrical 또는 spherical projection과 같은 방법을 사용할 수 있다.
