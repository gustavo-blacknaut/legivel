import ctypes
import sys
from ctypes import wintypes
from dataclasses import dataclass

SOFTWARE_ADAPTER_FLAG = 2
NOT_FOUND = 0x887A0002
ENUM_ADAPTERS1 = 12
GET_DESC1 = 10
QUERY_INTERFACE = 0
RELEASE = 2
QUERY_VIDEO_MEMORY_INFO = 14
LOCAL_SEGMENT_GROUP = 0
VENDORS = {0x1002: "AMD", 0x10DE: "NVIDIA", 0x8086: "Intel", 0x1414: "Microsoft"}


class Guid(ctypes.Structure):
    _fields_ = [("data1", wintypes.DWORD), ("data2", wintypes.WORD), ("data3", wintypes.WORD), ("data4", ctypes.c_ubyte * 8)]

    @classmethod
    def parse(cls, text: str) -> "Guid":
        parts = text.split("-")
        tail = bytes.fromhex(parts[3] + parts[4])
        return cls(int(parts[0], 16), int(parts[1], 16), int(parts[2], 16), (ctypes.c_ubyte * 8)(*tail))


class Luid(ctypes.Structure):
    _fields_ = [("low", wintypes.DWORD), ("high", wintypes.LONG)]


class AdapterDescription(ctypes.Structure):
    _fields_ = [
        ("description", ctypes.c_wchar * 128),
        ("vendor_id", wintypes.UINT),
        ("device_id", wintypes.UINT),
        ("subsystem_id", wintypes.UINT),
        ("revision", wintypes.UINT),
        ("dedicated_video_memory", ctypes.c_size_t),
        ("dedicated_system_memory", ctypes.c_size_t),
        ("shared_system_memory", ctypes.c_size_t),
        ("luid", Luid),
        ("flags", wintypes.UINT),
    ]


class VideoMemoryInfo(ctypes.Structure):
    _fields_ = [
        ("budget", ctypes.c_uint64),
        ("current_usage", ctypes.c_uint64),
        ("available_for_reservation", ctypes.c_uint64),
        ("current_reservation", ctypes.c_uint64),
    ]


FACTORY1_IID = "770aae78-f26f-4dba-a829-253c83d1b387"
ADAPTER3_IID = "645967a4-1392-4310-a798-8053ce3e93fd"


@dataclass(frozen=True)
class GpuAdapter:
    index: int
    name: str
    vendor: str
    dedicated_memory_mb: int
    software: bool


def argument_type(argument) -> type:
    return type(argument) if hasattr(type(argument), "from_param") else ctypes.c_void_p


def call(interface: ctypes.c_void_p, slot: int, restype, *arguments):
    vtable = ctypes.cast(interface, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
    prototype = ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *[argument_type(argument) for argument in arguments])
    return prototype(vtable[slot])(interface, *arguments)


def release(interface: ctypes.c_void_p) -> None:
    if interface:
        call(interface, RELEASE, wintypes.ULONG)


def create_factory() -> ctypes.c_void_p | None:
    if sys.platform != "win32":
        return None
    factory = ctypes.c_void_p()
    guid = Guid.parse(FACTORY1_IID)
    result = ctypes.windll.dxgi.CreateDXGIFactory1(ctypes.byref(guid), ctypes.byref(factory))
    return factory if result == 0 else None


def list_adapters() -> list[GpuAdapter]:
    factory = create_factory()
    if factory is None:
        return []
    adapters = []
    try:
        index = 0
        while True:
            adapter = ctypes.c_void_p()
            result = call(factory, ENUM_ADAPTERS1, ctypes.c_long, wintypes.UINT(index), ctypes.byref(adapter))
            if result & 0xFFFFFFFF == NOT_FOUND or result != 0:
                break
            description = AdapterDescription()
            call(adapter, GET_DESC1, ctypes.c_long, ctypes.byref(description))
            adapters.append(
                GpuAdapter(
                    index=index,
                    name=description.description.strip(),
                    vendor=VENDORS.get(description.vendor_id, hex(description.vendor_id)),
                    dedicated_memory_mb=description.dedicated_video_memory // (1024 * 1024),
                    software=bool(description.flags & SOFTWARE_ADAPTER_FLAG),
                )
            )
            release(adapter)
            index += 1
    finally:
        release(factory)
    return adapters


def preferred_adapter(adapters: list[GpuAdapter]) -> GpuAdapter | None:
    hardware = [adapter for adapter in adapters if not adapter.software]
    return max(hardware, key=lambda adapter: adapter.dedicated_memory_mb, default=None)


def video_memory_in_use_mb(adapter_index: int) -> float | None:
    factory = create_factory()
    if factory is None:
        return None
    adapter = ctypes.c_void_p()
    adapter3 = ctypes.c_void_p()
    try:
        if call(factory, ENUM_ADAPTERS1, ctypes.c_long, wintypes.UINT(adapter_index), ctypes.byref(adapter)) != 0:
            return None
        guid = Guid.parse(ADAPTER3_IID)
        if call(adapter, QUERY_INTERFACE, ctypes.c_long, ctypes.byref(guid), ctypes.byref(adapter3)) != 0:
            return None
        info = VideoMemoryInfo()
        if (
            call(
                adapter3,
                QUERY_VIDEO_MEMORY_INFO,
                ctypes.c_long,
                wintypes.UINT(0),
                ctypes.c_int(LOCAL_SEGMENT_GROUP),
                ctypes.byref(info),
            )
            != 0
        ):
            return None
        return info.current_usage / (1024 * 1024)
    finally:
        release(adapter3)
        release(adapter)
        release(factory)
