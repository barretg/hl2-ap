// Identifies this server.dll in the console, so a run can confirm the engine
// loaded ours and not the retail one.

#include "cbase.h"
#include "igamesystem.h"

// memdbgon must be the last include file in a .cpp file!!!
#include "tier0/memdbgon.h"

#define HL2AP_BUILD_TAG "hl2ap server.dll (" __DATE__ " " __TIME__ ")"

class CAPVersionSystem : public CAutoGameSystem
{
public:
	CAPVersionSystem() : CAutoGameSystem( "CAPVersionSystem" ) {}

	virtual bool Init()
	{
		Msg( "%s loaded\n", HL2AP_BUILD_TAG );
		return true;
	}

	virtual void LevelInitPostEntity()
	{
		Msg( "%s: map %s\n", HL2AP_BUILD_TAG, STRING( gpGlobals->mapname ) );
	}
};

static CAPVersionSystem s_APVersionSystem;

CON_COMMAND( ap_version, "Print the hl2ap server.dll build" )
{
	Msg( "%s\n", HL2AP_BUILD_TAG );
}
