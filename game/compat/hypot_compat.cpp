// `_hypot`, so the static UCRT's hypot.obj is never pulled into the client.
//
// Valve's VS2013 particles.lib carries an inline `hypot` from that compiler's
// math.h as a COMDAT, which calls `_hypot`. The UCRT defines both in one
// object, so resolving `_hypot` from it brings a second, non-COMDAT `hypot`,
// and lld-link refuses the pair (MSVC's linker let it pass). Defining `_hypot`
// here satisfies the reference first.

#include <cmath>

extern "C" double __cdecl _hypot(double x, double y)
{
	x = std::fabs(x);
	y = std::fabs(y);
	if (std::isinf(x) || std::isinf(y))
		return INFINITY;
	if (std::isnan(x) || std::isnan(y))
		return NAN;
	const double big = x > y ? x : y;
	const double small = x > y ? y : x;
	if (big == 0.0)
		return 0.0;
	// Scaled so that neither square overflows.
	const double ratio = small / big;
	return big * std::sqrt(1.0 + ratio * ratio);
}
