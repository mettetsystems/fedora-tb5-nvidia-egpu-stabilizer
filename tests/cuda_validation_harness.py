#!/usr/bin/env python3
# Manual-only diagnostic. NEVER run from RPM %build/%install/%check, akmods,
# dracut, systemd, install-local.sh, or uninstall-local.sh.
#
# RECONSTRUCTED / GENERALIZED harness. This is NOT the byte-for-byte script
# used for the recorded validation. That historical one-shot test is
# tests/cuda_pinned_bidir.py (cuDeviceGetByPCIBusId 0000:8d:00.0, one MiB
# argument, two pinned buffers, one H2D, sync, one D2H, sync, verify).
#
# This file reconstructs the broader investigation ladder from
# docs/INVESTIGATION_LOG.md and the test report. Do not treat PASS here as
# a substitute for cuda_pinned_bidir.py.

from __future__ import annotations

import argparse
import ctypes
import sys
import time

RTX5090_PCI_DEVICE = 0x2B85
CU_DEVICE_ATTRIBUTE_PCI_DEVICE_ID = 34
CU_MEMHOSTALLOC_PORTABLE = 0x01


def _load_cuda():
    try:
        return ctypes.CDLL("libcuda.so.1")
    except OSError as exc:
        raise SystemExit(f"FAIL: cannot load libcuda.so.1: {exc}") from exc


class Cuda:
    def __init__(self) -> None:
        self.lib = _load_cuda()
        self.lib.cuInit.argtypes = [ctypes.c_uint]
        self.lib.cuInit.restype = ctypes.c_int
        self.lib.cuDeviceGetCount.argtypes = [ctypes.POINTER(ctypes.c_int)]
        self.lib.cuDeviceGetCount.restype = ctypes.c_int
        self.lib.cuDeviceGet.argtypes = [ctypes.POINTER(ctypes.c_int), ctypes.c_int]
        self.lib.cuDeviceGet.restype = ctypes.c_int
        self.lib.cuDeviceGetName.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_int]
        self.lib.cuDeviceGetName.restype = ctypes.c_int
        self.lib.cuDeviceGetAttribute.argtypes = [
            ctypes.POINTER(ctypes.c_int),
            ctypes.c_int,
            ctypes.c_int,
        ]
        self.lib.cuDeviceGetAttribute.restype = ctypes.c_int
        self.lib.cuCtxCreate.argtypes = [
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.c_uint,
            ctypes.c_int,
        ]
        self.lib.cuCtxCreate.restype = ctypes.c_int
        self.lib.cuCtxDestroy.argtypes = [ctypes.c_void_p]
        self.lib.cuCtxDestroy.restype = ctypes.c_int
        self.lib.cuMemAlloc.argtypes = [ctypes.POINTER(ctypes.c_ulonglong), ctypes.c_size_t]
        self.lib.cuMemAlloc.restype = ctypes.c_int
        self.lib.cuMemFree.argtypes = [ctypes.c_ulonglong]
        self.lib.cuMemFree.restype = ctypes.c_int
        self.lib.cuMemAllocHost.argtypes = [ctypes.POINTER(ctypes.c_void_p), ctypes.c_size_t]
        self.lib.cuMemAllocHost.restype = ctypes.c_int
        self.lib.cuMemFreeHost.argtypes = [ctypes.c_void_p]
        self.lib.cuMemFreeHost.restype = ctypes.c_int
        self.lib.cuMemHostAlloc.argtypes = [
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.c_size_t,
            ctypes.c_uint,
        ]
        self.lib.cuMemHostAlloc.restype = ctypes.c_int
        self.lib.cuMemsetD8.argtypes = [ctypes.c_ulonglong, ctypes.c_ubyte, ctypes.c_size_t]
        self.lib.cuMemsetD8.restype = ctypes.c_int
        self.lib.cuMemcpyHtoD.argtypes = [ctypes.c_ulonglong, ctypes.c_void_p, ctypes.c_size_t]
        self.lib.cuMemcpyHtoD.restype = ctypes.c_int
        self.lib.cuMemcpyDtoH.argtypes = [ctypes.c_void_p, ctypes.c_ulonglong, ctypes.c_size_t]
        self.lib.cuMemcpyDtoH.restype = ctypes.c_int

    def check(self, err: int, what: str) -> None:
        if err != 0:
            raise SystemExit(f"FAIL: {what}: CUDA error {err}")


def gb_s(nbytes: int, seconds: float) -> float:
    if seconds <= 0:
        return 0.0
    return nbytes / seconds / 1e9


def select_rtx5090(cu: Cuda) -> tuple[int, str]:
    count = ctypes.c_int()
    cu.check(cu.lib.cuDeviceGetCount(ctypes.byref(count)), "cuDeviceGetCount")
    for index in range(count.value):
        dev = ctypes.c_int()
        cu.check(cu.lib.cuDeviceGet(ctypes.byref(dev), index), "cuDeviceGet")
        device = ctypes.c_int()
        cu.check(
            cu.lib.cuDeviceGetAttribute(
                ctypes.byref(device), CU_DEVICE_ATTRIBUTE_PCI_DEVICE_ID, dev.value
            ),
            "pci device",
        )
        namebuf = ctypes.create_string_buffer(256)
        cu.check(cu.lib.cuDeviceGetName(namebuf, 256, dev.value), "cuDeviceGetName")
        name = namebuf.value.decode("utf-8", "replace")
        if device.value == RTX5090_PCI_DEVICE or "5090" in name:
            return dev.value, name
    raise SystemExit("FAIL: RTX 5090 10de:2b85 not found")


def _pattern_block(seed: int) -> bytes:
    return bytes((i + seed) & 0xFF for i in range(4096))


def fill_pattern(buf, seed: int) -> None:
    mv = memoryview(buf).cast("B")
    block = _pattern_block(seed)
    offset = 0
    n = len(mv)
    while offset < n:
        take = min(len(block), n - offset)
        mv[offset : offset + take] = block[:take]
        offset += take


def verify_pattern(buf, seed: int, what: str) -> None:
    mv = memoryview(buf).cast("B")
    block = _pattern_block(seed)
    offset = 0
    n = len(mv)
    while offset < n:
        take = min(len(block), n - offset)
        if mv[offset : offset + take] != block[:take]:
            raise SystemExit(f"FAIL: {what}: mismatch at {offset}")
        offset += take


def pageable_copy(cu: Cuda, dptr: int, nbytes: int, seed: int, tag: str) -> None:
    src = (ctypes.c_ubyte * nbytes)()
    dst = (ctypes.c_ubyte * nbytes)()
    fill_pattern(src, seed)
    t0 = time.perf_counter()
    cu.check(cu.lib.cuMemcpyHtoD(dptr, src, nbytes), f"{tag} pageable H2D")
    h2d = time.perf_counter() - t0
    t0 = time.perf_counter()
    cu.check(cu.lib.cuMemcpyDtoH(dst, dptr, nbytes), f"{tag} pageable D2H")
    d2h = time.perf_counter() - t0
    verify_pattern(dst, seed, f"{tag} pageable")
    print(
        f"PASS: {tag} pageable {nbytes} B  H2D {gb_s(nbytes, h2d):.2f} GB/s  "
        f"D2H {gb_s(nbytes, d2h):.2f} GB/s"
    )


def pinned_alloc_touch(cu: Cuda, nbytes: int) -> None:
    ptr = ctypes.c_void_p()
    cu.check(
        cu.lib.cuMemHostAlloc(ctypes.byref(ptr), nbytes, CU_MEMHOSTALLOC_PORTABLE),
        "pinned alloc",
    )
    buf = (ctypes.c_ubyte * nbytes).from_address(ptr.value)
    fill_pattern(buf, 7)
    verify_pattern(buf, 7, "pinned CPU touch")
    cu.check(cu.lib.cuMemFreeHost(ptr), "pinned free")
    print(f"PASS: {nbytes} B pinned allocation + CPU touch")


def pinned_one_way(cu: Cuda, dptr: int, nbytes: int, direction: str, seed: int) -> None:
    ptr = ctypes.c_void_p()
    cu.check(
        cu.lib.cuMemHostAlloc(ctypes.byref(ptr), nbytes, CU_MEMHOSTALLOC_PORTABLE),
        f"pinned alloc {direction}",
    )
    host = (ctypes.c_ubyte * nbytes).from_address(ptr.value)
    if direction == "H2D":
        fill_pattern(host, seed)
        cu.check(cu.lib.cuMemcpyHtoD(dptr, ptr, nbytes), "pinned H2D")
        back = (ctypes.c_ubyte * nbytes)()
        cu.check(cu.lib.cuMemcpyDtoH(back, dptr, nbytes), "pageable D2H verify")
        verify_pattern(back, seed, "pinned H2D")
    elif direction == "D2H":
        tmp = (ctypes.c_ubyte * nbytes)()
        fill_pattern(tmp, seed)
        cu.check(cu.lib.cuMemcpyHtoD(dptr, tmp, nbytes), "seed device")
        cu.check(cu.lib.cuMemcpyDtoH(ptr, dptr, nbytes), "pinned D2H")
        verify_pattern(host, seed, "pinned D2H")
    else:
        raise SystemExit(f"FAIL: unknown direction {direction}")
    cu.check(cu.lib.cuMemFreeHost(ptr), "pinned free")
    print(f"PASS: {nbytes} B pinned {direction}")


def pinned_bidir(cu: Cuda, dptr: int, nbytes: int, seed: int, tag: str) -> tuple[float, float]:
    h_src = ctypes.c_void_p()
    h_dst = ctypes.c_void_p()
    cu.check(
        cu.lib.cuMemHostAlloc(ctypes.byref(h_src), nbytes, CU_MEMHOSTALLOC_PORTABLE),
        f"{tag} pinned src",
    )
    cu.check(
        cu.lib.cuMemHostAlloc(ctypes.byref(h_dst), nbytes, CU_MEMHOSTALLOC_PORTABLE),
        f"{tag} pinned dst",
    )
    src = (ctypes.c_ubyte * nbytes).from_address(h_src.value)
    dst = (ctypes.c_ubyte * nbytes).from_address(h_dst.value)
    fill_pattern(src, seed)
    t0 = time.perf_counter()
    cu.check(cu.lib.cuMemcpyHtoD(dptr, h_src, nbytes), f"{tag} pinned H2D")
    h2d = time.perf_counter() - t0
    t0 = time.perf_counter()
    cu.check(cu.lib.cuMemcpyDtoH(h_dst, dptr, nbytes), f"{tag} pinned D2H")
    d2h = time.perf_counter() - t0
    verify_pattern(dst, seed, f"{tag} pinned bidir")
    cu.check(cu.lib.cuMemFreeHost(h_src), f"{tag} free src")
    cu.check(cu.lib.cuMemFreeHost(h_dst), f"{tag} free dst")
    print(
        f"PASS: {tag} pinned bidir {nbytes} B  H2D {gb_s(nbytes, h2d):.2f} GB/s  "
        f"D2H {gb_s(nbytes, d2h):.2f} GB/s"
    )
    return h2d, d2h


def with_device(cu: Cuda):
    cu.check(cu.lib.cuInit(0), "cuInit")
    print("PASS: cuInit")
    dev, name = select_rtx5090(cu)
    print(f"PASS: select RTX 5090 ({name})")
    ctx = ctypes.c_void_p()
    cu.check(cu.lib.cuCtxCreate(ctypes.byref(ctx), 0, dev), "cuCtxCreate")
    print("PASS: create CUDA context")
    return ctx


def run_smoke(cu: Cuda) -> None:
    ctx = with_device(cu)
    dptr = ctypes.c_ulonglong()
    nbytes = 64 * 1024 * 1024
    cu.check(cu.lib.cuMemAlloc(ctypes.byref(dptr), nbytes), "cuMemAlloc 64 MiB")
    pinned_bidir(cu, dptr.value, nbytes, 64, "64 MiB")
    cu.check(cu.lib.cuMemFree(dptr.value), "cuMemFree")
    cu.check(cu.lib.cuCtxDestroy(ctx), "cuCtxDestroy")


def run_repeat(cu: Cuda) -> None:
    nbytes = 64 * 1024 * 1024
    for cycle in range(1, 21):
        ctx = with_device(cu)
        dptr = ctypes.c_ulonglong()
        cu.check(cu.lib.cuMemAlloc(ctypes.byref(dptr), nbytes), f"cycle {cycle} alloc")
        pinned_bidir(cu, dptr.value, nbytes, cycle, f"cycle {cycle}/20 64 MiB")
        cu.check(cu.lib.cuMemFree(dptr.value), f"cycle {cycle} free")
        cu.check(cu.lib.cuCtxDestroy(ctx), f"cycle {cycle} ctx")
    print("PASS: 20 x 64 MiB pinned bidirectional cycles")


def run_full(cu: Cuda) -> None:
    ctx = with_device(cu)
    small = 4096
    dptr = ctypes.c_ulonglong()
    cu.check(cu.lib.cuMemAlloc(ctypes.byref(dptr), small), "4 KiB VRAM")
    cu.check(cu.lib.cuMemsetD8(dptr.value, 0x5A, small), "4 KiB memset")
    pageable_copy(cu, dptr.value, small, 1, "4 KiB")
    cu.check(cu.lib.cuMemFree(dptr.value), "free 4 KiB")

    large = 256 * 1024 * 1024
    cu.check(cu.lib.cuMemAlloc(ctypes.byref(dptr), large), "256 MiB VRAM")
    pageable_copy(cu, dptr.value, large, 2, "256 MiB")
    cu.check(cu.lib.cuMemFree(dptr.value), "free 256 MiB")

    pinned_alloc_touch(cu, small)
    cu.check(cu.lib.cuMemAlloc(ctypes.byref(dptr), small), "4 KiB VRAM pinned")
    pinned_one_way(cu, dptr.value, small, "H2D", 3)
    pinned_one_way(cu, dptr.value, small, "D2H", 4)
    cu.check(cu.lib.cuMemFree(dptr.value), "free 4 KiB pinned")

    for mib, seed in ((1, 10), (64, 11), (128, 12), (256, 13)):
        nbytes = mib * 1024 * 1024
        cu.check(cu.lib.cuMemAlloc(ctypes.byref(dptr), nbytes), f"{mib} MiB VRAM")
        pinned_bidir(cu, dptr.value, nbytes, seed, f"{mib} MiB")
        cu.check(cu.lib.cuMemFree(dptr.value), f"free {mib} MiB")

    cu.check(cu.lib.cuCtxDestroy(ctx), "cuCtxDestroy before repeat")
    run_repeat(cu)
    print("PASS: full validated CUDA ladder")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Manual-only validated CUDA ladder. Refuses to run without a mode."
    )
    parser.add_argument(
        "mode",
        nargs="?",
        choices=("smoke", "repeat", "full"),
        help="smoke=once 64 MiB pinned bidir; repeat=20x64 MiB; full=investigation ladder",
    )
    args = parser.parse_args(argv)
    if args.mode is None:
        parser.print_help()
        print("\nRefusing to run: choose smoke, repeat, or full.", file=sys.stderr)
        return 2
    print("MANUAL CUDA TEST — not part of boot, RPM, or akmods")
    cu = Cuda()
    if args.mode == "smoke":
        run_smoke(cu)
    elif args.mode == "repeat":
        run_repeat(cu)
    else:
        run_full(cu)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
