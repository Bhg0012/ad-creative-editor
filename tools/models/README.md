# Models

- `face_detection_yunet_2023mar.onnx`: YuNet face detector from the OpenCV Zoo
  (https://github.com/opencv/opencv_zoo, Apache-2.0). Used by `tools/render.py` to center
  the 9:16 / 4:5 reframe on the speaker's face (`focus: auto`). 232 KB, runs on CPU in OpenCV 4.5.4+.
