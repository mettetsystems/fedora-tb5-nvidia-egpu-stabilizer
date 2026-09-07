#!/usr/bin/env python3
# Manual-only diagnostic. NEVER run from RPM %build/%install/%check, akmods,
# dracut, systemd, install-local.sh, or uninstall-local.sh.
#
# Validated investigation test for one pinned bidirectional copy.
# Selects RTX 5090 at PCI BDF 0000:8d:00.0 via cuDeviceGetByPCIBusId().
# Usage: python3 cuda_pinned_bidir.py <MiB>
#
# This is the historical one-shot test (one size argument, two pinned host
# buffers, one VRAM buffer, H2D, sync, D2H, sync, verify, print GB/s).
# Do not generalize it. The reconstructed multi-stage ladder lives in
# tests/cuda_validation_harness.py and is not this script.

import ctypes
import sys
import time

GPU_BDF = "0000:8d:00.0"


def check(err, what):
    if err != 0:
        raise SystemExit(f"FAIL: {what}: CUDA error {err}")


def main(argv):
    if len(argv) != 1:
        raise SystemExit("usage: cuda_pinned_bidir.py <MiB>")
    mib = int(argv[0])
    if mib <= 0:
        raise SystemExit("FAIL: MiB must be > 0")
    nbytes = mib * 1024 * 1024

    lib = ctypes.CDLL("libcuda.so.1")
    lib.cuInit.argtypes = [ctypes.c_uint]
    lib.cuInit.restype = ctypes.c_int
    lib.cuDeviceGetByPCIBusId.argtypes = [ctypes.POINTER(ctypes.c_int), ctypes.c_char_p]
    lib.cuDeviceGetByPCIBusId.restype = ctypes.c_int
    lib.cuCtxCreate.argtypes = [ctypes.POINTER(ctypes.c_void_p), ctypes.c_uint, ctypes.c_int]
    lib.cuCtxCreate.restype = ctypes.c_int
    lib.cuCtxDestroy.argtypes = [ctypes.c_void_p]
    lib.cuCtxDestroy.restype = ctypes.c_int
    lib.cuCtxSynchronize.argtypes = []
    lib.cuCtxSynchronize.restype = ctypes.c_int
    lib.cuMemAlloc.argtypes = [ctypes.POINTER(ctypes.c_ulonglong), ctypes.c_size_t]
    lib.cuMemAlloc.restype = ctypes.c_int
    lib.cuMemFree.argtypes = [ctypes.c_ulonglong]
    lib.cuMemFree.restype = ctypes.c_int
    lib.cuMemAllocHost.argtypes = [ctypes.POINTER(ctypes.c_void_p), ctypes.c_size_t]
    lib.cuMemAllocHost.restype = ctypes.c_int
    lib.cuMemFreeHost.argtypes = [ctypes.c_void_p]
    lib.cuMemFreeHost.restype = ctypes.c_int
    lib.cuMemcpyHtoD.argtypes = [ctypes.c_ulonglong, ctypes.c_void_p, ctypes.c_size_t]
    lib.cuMemcpyHtoD.restype = ctypes.c_int
    lib.cuMemcpyDtoH.argtypes = [ctypes.c_void_p, ctypes.c_ulonglong, ctypes.c_size_t]
    lib.cuMemcpyDtoH.restype = ctypes.c_int

    check(lib.cuInit(0), "cuInit")
    dev = ctypes.c_int()
    check(lib.cuDeviceGetByPCIBusId(ctypes.byref(dev), GPU_BDF.encode()), "cuDeviceGetByPCIBusId")
    ctx = ctypes.c_void_p()
    check(lib.cuCtxCreate(ctypes.byref(ctx), 0, dev.value), "cuCtxCreate")

    h_src = ctypes.c_void_p()
    h_dst = ctypes.c_void_p()
    dptr = ctypes.c_ulonglong()
    check(lib.cuMemAllocHost(ctypes.byref(h_src), nbytes), "cuMemAllocHost src")
    check(lib.cuMemAllocHost(ctypes.byref(h_dst), nbytes), "cuMemAllocHost dst")
    check(lib.cuMemAlloc(ctypes.byref(dptr), nbytes), "cuMemAlloc")

    src = (ctypes.c_ubyte * nbytes).from_address(h_src.value)
    dst = (ctypes.c_ubyte * nbytes).from_address(h_dst.value)
    pattern = bytes((i * 17) & 0xFF for i in range(4096))
    mv = memoryview(src).cast("B")
    offset = 0
    while offset < nbytes:
        take = min(len(pattern), nbytes - offset)
        mv[offset:offset + take] = pattern[:take]
        offset += take

    t0 = time.perf_counter()
    check(lib.cuMemcpyHtoD(dptr.value, h_src, nbytes), "H2D")
    check(lib.cuCtxSynchronize(), "sync after H2D")
    h2d = time.perf_counter() - t0

    t0 = time.perf_counter()
    check(lib.cuMemcpyDtoH(h_dst, dptr.value, nbytes), "D2H")
    check(lib.cuCtxSynchronize(), "sync after D2H")
    d2h = time.perf_counter() - t0

    if memoryview(dst).cast("B") != memoryview(src).cast("B"):
        raise SystemExit("FAIL: data mismatch")

    def gb_s(seconds):
        return 0.0 if seconds <= 0 else nbytes / seconds / 1e9

    print(
        f"PASS: {mib} MiB pinned bidir {GPU_BDF}  "
        f"H2D {gb_s(h2d):.2f} GB/s  D2H {gb_s(d2h):.2f} GB/s"
    )

    check(lib.cuMemFree(dptr.value), "cuMemFree")
    check(lib.cuMemFreeHost(h_src), "cuMemFreeHost src")
    check(lib.cuMemFreeHost(h_dst), "cuMemFreeHost dst")
    check(lib.cuCtxDestroy(ctx), "cuCtxDestroy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
