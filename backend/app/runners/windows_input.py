"""Send Unicode to the focused control without clipboard/file storage."""

import ctypes
from ctypes import wintypes


def type_text(text: str):
    if not hasattr(ctypes, "windll"):
        raise RuntimeError("Windows required")
    pointer = wintypes.WPARAM

    class Keyboard(ctypes.Structure):
        _fields_ = [
            ("wVk", wintypes.WORD),
            ("wScan", wintypes.WORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", pointer),
        ]

    class Mouse(ctypes.Structure):
        _fields_ = [
            ("dx", wintypes.LONG),
            ("dy", wintypes.LONG),
            ("mouseData", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", pointer),
        ]

    class Data(ctypes.Union):
        _fields_ = [("ki", Keyboard), ("mi", Mouse)]

    class Input(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("data", Data)]

    raw = text.encode("utf-16-le")
    for offset in range(0, len(raw), 2):
        code = int.from_bytes(raw[offset : offset + 2], "little")
        for flags in (0x0004, 0x0004 | 0x0002):
            event = Input(
                type=1,
                data=Data(ki=Keyboard(wVk=0, wScan=code, dwFlags=flags, time=0, dwExtraInfo=0)),
            )
            if ctypes.windll.user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(Input)) != 1:
                raise RuntimeError("Input rejected")
