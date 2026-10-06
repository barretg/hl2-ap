// Client frame counter for the server's freeze watchdog (see
// game/src/ap_watchdog.h). Test builds only.

#include "cbase.h"
#include "igamesystem.h"

#include "tier0/memdbgon.h"

#ifdef HL2AP_TEST_BUILD

namespace {

volatile long g_client_frames = 0;

class CHeartbeatSystem : public CAutoGameSystemPerFrame {
public:
    CHeartbeatSystem() : CAutoGameSystemPerFrame("CHeartbeatSystem") {}

    void Update(float) override { g_client_frames = g_client_frames + 1; }
};

CHeartbeatSystem g_heartbeat;

}  // namespace

extern "C" __declspec(dllexport) long HL2AP_ClientFrames() { return g_client_frames; }

#endif  // HL2AP_TEST_BUILD
