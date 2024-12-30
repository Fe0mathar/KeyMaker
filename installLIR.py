#!/usr/bin/env python3
"""
installLIR.py - Installs the "LadyInRed" (FaceFusion) integration in KeyMaker.

Usage:
  1) Ensure you're inside the same Python environment as KeyMaker.
  2) In the KeyMaker console, type: installLIR
  3) This script will:
     - Check for ffmpeg
     - Install Python libs needed for FaceFusion (insightface, filetype, etc.)
     - Call facefusion\install.py with --onnxruntime=cuda or default
     - Attempt to do a 'download' step or skip if not recognized
"""

import os
import sys
import subprocess
import shutil

def check_ffmpeg():
    """Check if 'ffmpeg' is on PATH by trying ffmpeg -version."""
    try:
        out = subprocess.check_output(["ffmpeg", "-version"], stderr=subprocess.STDOUT)
        print("[installLIR] Detected ffmpeg on system PATH. Good.")
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print("[installLIR] WARNING: ffmpeg not found on PATH.")
        print("   FaceFusion might fail on certain video operations.")
        print("   Please install or add ffmpeg to PATH for best results.")

def install_facefusion_python_libs():
    """
    Installs the core Python libraries needed by FaceFusion:
      - insightface, filetype, scipy, etc.
    """
    print("[installLIR] Installing extra Python libraries with pip (insightface, filetype, etc.)...")

    # Customize your pinned versions or let pip handle it.
    # For example, you might add more packages if needed:
    libs = [
        "insightface",
        "filetype",
        "scipy",
        # Add others as needed, e.g. "numpy==2.2.0"
    ]

    pip_cmd = [
        sys.executable, "-m", "pip", "install", "--upgrade"
    ] + libs

    try:
        subprocess.run(pip_cmd, check=True)
        print("[installLIR] Extra Python libs installed successfully.")
    except subprocess.CalledProcessError as e:
        print("[installLIR] ERROR: Failed installing extra libs:", e)
        print("   You can manually install them with pip if necessary.")
        return False

    return True

def run_facefusion_install(onnx_provider="cuda"):
    """
    Calls facefusion\install.py with the chosen onnxruntime provider.
    By default, we try 'cuda', else we fallback to 'default'.
    Also pass --skip-conda to avoid conda logic.
    """
    facefusion_dir = os.path.join(os.getcwd(), "facefusion")
    installer_path = os.path.join(facefusion_dir, "install.py")

    if not os.path.exists(installer_path):
        print(f"[installLIR] ERROR: facefusion\\install.py not found at: {installer_path}")
        print("   Make sure you've cloned facefusion into F:\\KeyMaker\\facefusion or the correct path.")
        return False

    print(f"[installLIR] Running {installer_path} with --onnxruntime={onnx_provider} --skip-conda ...")

    # e.g. python install.py --onnxruntime=cuda --skip-conda
    cmd = [
        sys.executable,
        installer_path,
        f"--onnxruntime={onnx_provider}",
        "--skip-conda",
    ]

    try:
        subprocess.run(cmd, check=True, cwd=facefusion_dir)
        print("[installLIR] FaceFusion install.py completed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"[installLIR] ERROR: facefusion install.py step failed: {e}")
        return False

    # Attempt optional 'facefusion.py download --download-scope full'
    facefusion_py = os.path.join(facefusion_dir, "facefusion.py")
    if not os.path.exists(facefusion_py):
        print("[installLIR] WARNING: facefusion.py not found, skipping download step.")
        return True  # Not critical

    print("[installLIR] Downloading all FaceFusion models with scope=full (via huggingface & github fallback).")
    # Some FaceFusion versions do not have a 'download' subcommand. We'll ignore the error if so.
    download_cmd = [
        sys.executable,
        facefusion_py,
        "download",  # might not exist in every FaceFusion version
        "--download-scope", "full"
    ]

    try:
        subprocess.run(download_cmd, check=True, cwd=facefusion_dir)
        print("[installLIR] FaceFusion models downloaded with scope=full.")
    except subprocess.CalledProcessError as e:
        print("[installLIR] WARNING: facefusion download step failed:", e)
        print("           You can still let FaceFusion auto-download models on demand.")

    return True

def pick_onnx_provider():
    """
    A simple function that tries to see if user wants CUDA or fallback to 'default'.
    - In production you might check for nvidia-smi or something similar
    """
    # Minimal approach: always attempt 'cuda' unless user forced CPU
    # If you want to detect GPU presence more robustly, you'd add logic here.
    return "cuda"

if __name__ == "__main__":
    print("[installLIR] Starting LadyInRed (FaceFusion) installation...")

    # Step 1) Check ffmpeg
    check_ffmpeg()

    # Step 2) Install additional Python libs
    if not install_facefusion_python_libs():
        print("[installLIR] Stopping because extra libs installation failed.")
        sys.exit(1)

    # Step 3) Attempt to call facefusion\install.py with onnxruntime=cuda
    onnx_provider = pick_onnx_provider()
    success = run_facefusion_install(onnx_provider=onnx_provider)
    if not success:
        print("[installLIR] Something failed during facefusion install steps.")
        sys.exit(1)

    print("[installLIR] Done! FaceFusion (LadyInRed) is ready. Type 'lir' in KeyMaker to run facefusion.py.")
