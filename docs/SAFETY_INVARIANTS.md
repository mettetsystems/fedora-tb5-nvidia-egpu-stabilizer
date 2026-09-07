# Safety Invariants

1. Never force Gen4.
2. Never retrain after NVIDIA binds.
3. Exactly one normal pre-NVIDIA retrain.
4. Fail closed on unexpected GPU/parent/state.
5. Do not disable Secure Boot.
6. Do not disable kernel lockdown.
7. Do not globally disable the IOMMU.
8. Do not overwrite NVIDIA modules.
9. Do not take display ownership from the Intel iGPU.
10. Do not run CUDA or pinned-memory stress automatically during install/boot.
11. Do not use NVIDIA's `.run` installer.
12. Do not restore old injector configuration.
13. Do not modify GRUB automatically.
14. Post-NVIDIA reassert may change TLS/HASD only; it must never retrain.
15. Idle Gen1 is not a failure by itself.
16. Treat sticky `RxErr+` as historical unless counters/timestamps prove a new error.
