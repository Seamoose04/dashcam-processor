# Self-hosted GitHub Actions runner image for the dashcam-processor workhorse.
# Provides every dependency Workhorse links against at build time:
#   - OpenCV4 (video decode / image ops)
#   - tesseract + leptonica (OCR of license plates)
#   - darknet  -> libdarknet.so      (YOLO inference backend)
#   - darkhelp -> libdarkhelp.so     (C++ wrapper around the Darknet C API)
#   - CUDA Toolkit + cuDNN + nvml    (GPU status via NVML, GPU YOLO if enabled)
#
# Build:  docker build -t dashcam-runner .
# Run:    docker run --gpus all -e RUNNER_TOKEN=<...> -d ghcr.io/.../dashcam-runner:latest
FROM nvidia/cuda:12.6.3-cudnn-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    CUDA_VERSION=12.6.3

# System + build deps. OpenCV4 and tesseract are the only apt packages;
# darknet + darkhelp are built from source (DarkHelp dropped vcpkg support).
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl tar unzip git cmake pkg-config g++ \
        build-essential yasm libgtk2.0-dev libmagic-dev \
        libopencv-dev opencv-data \
        libtesseract-dev tesseract-ocr \
        libtclap-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/darknet
RUN git clone --depth 1 https://github.com/AlexeyAB/darknet.git . \
    && sed -i 's/^GPU=0/GPU=1/; s^CUDNN=0^CUDNN=1^; s^OPENCV=0^OPENCV=1^; s^OPENMP=0^OPENMP=1^' Makefile \
    && make -j 4 \
    && cp lib/libdarknet.so /usr/local/lib/libdarknet.so \
    && ldconfig

WORKDIR /opt/darkhelp
RUN git clone --depth 1 https://github.com/stephanecharette/DarkHelp.git . \
    && cmake -B build -DCMAKE_BUILD_TYPE=Release \
    && cmake --build build -j 4 \
    && cp libdarkhelp.so /usr/local/lib/libdarkhelp.so \
    && ldconfig

# GitHub Actions runner binary (baked in so the image is self-contained).
RUN mkdir -p /opt/actions-runner \
    && curl -sL https://github.com/actions/runner/releases/download/v2.336.0/actions-runner-linux-x64-2.336.0.tar.gz \
         | tar -xz -C /opt/actions-runner

# CUDA toolkit ships with nvml headers + the nvml library.
ENV PATH="/opt/nvidia/cuda/bin:${PATH}"

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
