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

# darknet is built from source via CMake.  We use hank-ai/darknet (Stephane
# Charette's own fork) rather than AlexeyAB/darknet because DarkHelp was written
# against that fork: it does an unconditional '#include <darknet.hpp>' and calls
# 'Darknet::create_yolo_heatmaps()', both of which only exist in this repo.
#
# CUDA is auto-detected (CheckLanguage), cuDNN + OpenCV come from apt, so there
# is no vcpkg / OpenCV-from-source -- the build stays fast.  A newer cmake is
# required (>=3.24) than what Ubuntu 22.04 ships by default.
WORKDIR /opt/darknet
RUN curl -fsSL https://github.com/kitware/cmake/releases/download/v3.27.9/cmake-3.27.9-linux-x86_64.tar.gz | tar -xz --strip-components=1 -C /usr/local \
    && git clone https://github.com/hank-ai/darknet.git . \
    && CUDASTUB_DIR=$(find /usr/local/cuda -name 'libcuda.so' -path '*/stubs/*' -print -quit) \
    && ln -sf "$CUDASTUB_DIR/libcuda.so" "$(dirname "$CUDASTUB_DIR")/libcuda.so.1" \
    && ldconfig \
    && cmake -B build -DCMAKE_BUILD_TYPE=Release \
        -DDARKNET_CUDA_ARCHITECTURES="75" \
        -DCMAKE_SHARED_LINKER_FLAGS="-Wl,-rpath-link=$(dirname "$CUDASTUB_DIR")" \
        -DCMAKE_EXE_LINKER_FLAGS="-Wl,-rpath-link=$(dirname "$CUDASTUB_DIR")" \
    && cmake --build build -j "$(nproc)" \
    && cmake --install build \
    && ldconfig

WORKDIR /opt/darkhelp
RUN git clone --depth 1 https://github.com/stephanecharette/DarkHelp.git . \
    && CUDASTUB_DIR=$(find /usr/local/cuda -name 'libcuda.so' -path '*/stubs/*' -print -quit) \
    && ldconfig \
    && cmake -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH=/usr/local \
        -DCMAKE_SHARED_LINKER_FLAGS="-Wl,-rpath-link=$(dirname "$CUDASTUB_DIR")" \
        -DCMAKE_EXE_LINKER_FLAGS="-Wl,-rpath-link=$(dirname "$CUDASTUB_DIR")" \
    && cmake --build build -j "$(nproc)" \
    && cp "$(find . -name 'libdarkhelp.so' -maxdepth 2 | head -n1)" /usr/local/lib/libdarkhelp.so \
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
