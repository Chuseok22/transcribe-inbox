from __future__ import annotations
import psutil


def available_memory_bytes() -> int:
    return psutil.virtual_memory().available


def swap_out_bytes() -> int:
    return psutil.swap_memory().sout
