#!/usr/bin/env python
"""
ladyinred.py - Minimal script to launch the FaceFusion server and open a browser,
with a tweak to force or prefer CUDA via onnxruntime as an example.

Usage:
  python ladyinred.py
  or
  python ladyinred.py run

In KeyMaker:
  The 'LIR' console command calls this script.
"""

import os
import sys
import subprocess

import onnxruntime as ort

# This function is optional—just to show you can test onnxruntime
def check_cuda():
    """
    Quick check if onnxruntime can load a dummy session with CUDA providers.
    """
    try:
        # Providers you want in order of priority
        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]

        # We'll do a trivial check. If you have an actual .onnx model, set it here
        # or skip if you only want to test the environment.
        dummy_model = "path/to/a/tiny/model.onnx"

        # Initialize session
        ort_session = ort.InferenceSession(dummy_model, providers=providers)

        # If no error => we presumably can run CUDA
        print("[LadyInRed] CUDA check: onnxruntime created session with providers =>", ort_session.get_providers())
    except Exception as e:
        print("[LadyInRed] Warning: CUDA check raised an exception:", e)


def launch_facefusion():
    """
    Runs "python facefusion.py run --open-browser" from F:\KeyMaker\facefusion,
    using the same Python environment that launched ladyinred.py,
    and requesting CUDA if available.
    """
    # Optionally do a quick environment check:
    check_cuda()

    facefusion_dir = r"F:\KeyMaker\facefusion"    # Path to facefusion
    python_cmd = sys.executable

    # In case FaceFusion has a config to specify providers, you might
    # do something like:
    #
    #   python facefusion.py run --open-browser --execution-providers "CUDAExecutionProvider"
    #
    # But this depends on FaceFusion's CLI design. If there's no such option,
    # we rely on an internal facefusion config or .ini to set providers.

    cmd = f'cd "{facefusion_dir}" && "{python_cmd}" facefusion.py run --open-browser'
    print(f"[LadyInRed] Launching FaceFusion with:\n{cmd}")

    if os.name == 'nt':
        # On Windows, shell=True uses cmd.exe
        subprocess.run(cmd, shell=True)
    else:
        # On Unix/Mac, specify a shell if needed
        subprocess.run(cmd, shell=True, executable='/bin/bash')


def main():
    """
    If you want to parse arguments (e.g. "python ladyinred.py run"),
    you could do so, but for now we just always call launch_facefusion().
    """
    # For a quick CLI parse:
    # e.g. python ladyinred.py run
    # e.g. python ladyinred.py run --open-browser
    # This is very simplistic:
    if len(sys.argv) > 1:
        # if "run" in sys.argv => do the same anyway
        pass

    launch_facefusion()


if __name__ == "__main__":
    main()
