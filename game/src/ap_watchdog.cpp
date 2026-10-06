// See ap_watchdog.h.

#ifdef HL2AP_TEST_BUILD

#include "ap_watchdog.h"

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <tlhelp32.h>

#include <atomic>
#include <cstdio>
#include <string>
#include <vector>

namespace {

const DWORD kStallSeconds = 15;
const DWORD kPollMs = 500;
// Stack bytes scanned for return addresses, from ESP up.
const DWORD kStackScanBytes = 64 * 1024;
const int kMaxStackHits = 80;

std::atomic<long> g_server_frames{0};
std::atomic<const char*> g_stage{"not started"};
std::atomic<bool> g_started{false};

CRITICAL_SECTION g_dir_lock;
std::string g_dir;
HANDLE g_main_thread = nullptr;

typedef long(__cdecl* ClientFramesFn)();

long ClientFrames() {
    static ClientFramesFn fn = nullptr;
    if (fn == nullptr) {
        HMODULE client = GetModuleHandleA("client.dll");
        if (client != nullptr) {
            fn = reinterpret_cast<ClientFramesFn>(GetProcAddress(client, "HL2AP_ClientFrames"));
        }
    }
    return fn != nullptr ? fn() : -1;
}

std::string Dir() {
    EnterCriticalSection(&g_dir_lock);
    std::string dir = g_dir;
    LeaveCriticalSection(&g_dir_lock);
    return dir;
}

std::string Stamp() {
    SYSTEMTIME t;
    GetLocalTime(&t);
    char buf[32];
    snprintf(buf, sizeof(buf), "%04d-%02d-%02d %02d:%02d:%02d", t.wYear, t.wMonth, t.wDay,
             t.wHour, t.wMinute, t.wSecond);
    return buf;
}

void Append(const std::string& text) {
    std::string path = Dir() + "/watchdog.txt";
    HANDLE file = CreateFileA(path.c_str(), FILE_APPEND_DATA, FILE_SHARE_READ, nullptr,
                              OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) {
        return;
    }
    DWORD written = 0;
    WriteFile(file, text.data(), static_cast<DWORD>(text.size()), &written, nullptr);
    CloseHandle(file);
}

struct Module {
    DWORD base;
    DWORD end;
    std::string name;
};

std::vector<Module> Modules() {
    std::vector<Module> out;
    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE, GetCurrentProcessId());
    if (snap == INVALID_HANDLE_VALUE) {
        return out;
    }
    MODULEENTRY32 entry;
    entry.dwSize = sizeof(entry);
    for (BOOL ok = Module32First(snap, &entry); ok; ok = Module32Next(snap, &entry)) {
        DWORD base = reinterpret_cast<DWORD>(entry.modBaseAddr);
        out.push_back({base, base + entry.modBaseSize, entry.szModule});
    }
    CloseHandle(snap);
    return out;
}

const Module* Owner(const std::vector<Module>& modules, DWORD address) {
    for (const Module& m : modules) {
        if (address >= m.base && address < m.end) {
            return &m;
        }
    }
    return nullptr;
}

std::string Where(const std::vector<Module>& modules, DWORD address) {
    char buf[160];
    const Module* m = Owner(modules, address);
    if (m != nullptr) {
        snprintf(buf, sizeof(buf), "%s+0x%lx", m->name.c_str(),
                 static_cast<unsigned long>(address - m->base));
    } else {
        snprintf(buf, sizeof(buf), "0x%08lx", static_cast<unsigned long>(address));
    }
    return buf;
}

// The main thread's EIP and every stack word that points into a module. Stack
// scanning over-reports (stale values), but needs no frame pointers or symbols.
std::string MainThreadReport() {
    std::string out;
    if (g_main_thread == nullptr || SuspendThread(g_main_thread) == static_cast<DWORD>(-1)) {
        return "main thread: could not suspend\n";
    }
    CONTEXT ctx;
    ZeroMemory(&ctx, sizeof(ctx));
    ctx.ContextFlags = CONTEXT_CONTROL | CONTEXT_INTEGER;
    std::vector<Module> modules = Modules();
    if (GetThreadContext(g_main_thread, &ctx)) {
        out += "main thread eip: " + Where(modules, ctx.Eip) + "\n";
        out += "main thread ebp chain:\n";
        DWORD frame = ctx.Ebp;
        for (int i = 0; i < 32 && frame != 0; ++i) {
            DWORD pair[2];
            SIZE_T got = 0;
            if (!ReadProcessMemory(GetCurrentProcess(), reinterpret_cast<void*>(frame), pair,
                                   sizeof(pair), &got) || got != sizeof(pair)) {
                break;
            }
            out += "  " + Where(modules, pair[1]) + "\n";
            if (pair[0] <= frame) {
                break;
            }
            frame = pair[0];
        }
        out += "main thread stack scan (module words from esp):\n";
        std::vector<DWORD> stack(kStackScanBytes / sizeof(DWORD));
        SIZE_T got = 0;
        // Partial reads fail outright at the stack top, so shrink until one fits.
        for (SIZE_T bytes = kStackScanBytes; bytes >= 4096; bytes /= 2) {
            if (ReadProcessMemory(GetCurrentProcess(), reinterpret_cast<void*>(ctx.Esp),
                                  stack.data(), bytes, &got)) {
                break;
            }
            got = 0;
        }
        int hits = 0;
        for (SIZE_T i = 0; i < got / sizeof(DWORD) && hits < kMaxStackHits; ++i) {
            const Module* m = Owner(modules, stack[i]);
            if (m != nullptr) {
                char off[24];
                snprintf(off, sizeof(off), "  esp+0x%04lx ", static_cast<unsigned long>(i * 4));
                out += off + Where(modules, stack[i]) + "\n";
                ++hits;
            }
        }
    } else {
        out += "main thread: GetThreadContext failed\n";
    }
    ResumeThread(g_main_thread);
    return out;
}

typedef BOOL(WINAPI* MiniDumpFn)(HANDLE, DWORD, HANDLE, int, void*, void*, void*);

bool WriteDump() {
    HMODULE dbghelp = LoadLibraryA("dbghelp.dll");
    if (dbghelp == nullptr) {
        return false;
    }
    MiniDumpFn dump = reinterpret_cast<MiniDumpFn>(GetProcAddress(dbghelp, "MiniDumpWriteDump"));
    if (dump == nullptr) {
        return false;
    }
    std::string path = Dir() + "/watchdog.dmp";
    HANDLE file = CreateFileA(path.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS,
                              FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) {
        return false;
    }
    // MiniDumpNormal | MiniDumpWithThreadInfo: every thread's stack, small file.
    BOOL ok = dump(GetCurrentProcess(), GetCurrentProcessId(), file, 0x1000, nullptr, nullptr,
                   nullptr);
    CloseHandle(file);
    return ok != FALSE;
}

DWORD WINAPI Watch(void*) {
    long last_server = -1;
    long last_client = -1;
    DWORD last_change = GetTickCount();
    bool reported = false;
    for (;;) {
        Sleep(kPollMs);
        long server = g_server_frames.load();
        long client = ClientFrames();
        DWORD now = GetTickCount();
        if (server != last_server || client != last_client) {
            if (reported) {
                char buf[96];
                snprintf(buf, sizeof(buf), "%s resumed after %lu s (so a stall, not a freeze)\n\n",
                         Stamp().c_str(), static_cast<unsigned long>((now - last_change) / 1000));
                Append(buf);
                reported = false;
            }
            last_server = server;
            last_client = client;
            last_change = now;
            continue;
        }
        if (reported || now - last_change < kStallSeconds * 1000) {
            continue;
        }
        reported = true;
        char head[256];
        snprintf(head, sizeof(head),
                 "%s FROZEN: no server or client frame for %lu s\n"
                 "last hl2ap stage: %s\nserver frames: %ld, client frames: %ld%s\n",
                 Stamp().c_str(), static_cast<unsigned long>(kStallSeconds), g_stage.load(),
                 server, client, client < 0 ? " (client counter missing)" : "");
        std::string report = head + MainThreadReport();
        report += WriteDump() ? "minidump: watchdog.dmp\n" : "minidump: failed\n";
        Append(report + "\n");
    }
}

}  // namespace

void WatchdogStart(const char* store_dir) {
    if (!g_started.exchange(true)) {
        InitializeCriticalSection(&g_dir_lock);
        g_dir = store_dir;
        DuplicateHandle(GetCurrentProcess(), GetCurrentThread(), GetCurrentProcess(),
                        &g_main_thread, 0, FALSE, DUPLICATE_SAME_ACCESS);
        Append(Stamp() + " watchdog armed\n");
        HANDLE thread = CreateThread(nullptr, 0, Watch, nullptr, 0, nullptr);
        if (thread != nullptr) {
            CloseHandle(thread);
        }
        return;
    }
    EnterCriticalSection(&g_dir_lock);
    g_dir = store_dir;
    LeaveCriticalSection(&g_dir_lock);
}

void WatchdogBeat() { g_server_frames.fetch_add(1); }

void WatchdogStage(const char* stage) { g_stage.store(stage); }

#endif  // HL2AP_TEST_BUILD
