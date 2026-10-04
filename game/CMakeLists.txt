# Builds the hl2ap server dll: the Source SDK 2013 singleplayer branch's
# server_hl2 project (plain HL2, as retail hl2/bin/server.dll) plus the
# sources in src/. The episodes (Phase 9) will need server_episodic and our own
# per-campaign content switching; Valve's hl2_complete code is not public.
#
# The SDK is not vendored. Check out ValveSoftware/source-sdk-2013 branch
# `singleplayer` beside this repository and point SDK_DIR at it. The `master`
# branch is the 64-bit multiplayer SDK and retail HL2 will not load it.
#
#   cmake -S game -B build/game -G Ninja \
#         -DCMAKE_TOOLCHAIN_FILE=game/toolchain-clangcl-x86.cmake \
#         -DSDK_DIR=../source-sdk-2013
#   cmake --build build/game

cmake_minimum_required(VERSION 3.20)
project(hl2ap CXX C)

set(SDK_DIR "" CACHE PATH "Path to a checkout of ValveSoftware/source-sdk-2013 (singleplayer)")
get_filename_component(SDK_DIR "${SDK_DIR}" ABSOLUTE BASE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/..")
set(SRC "${SDK_DIR}/src")
if(NOT EXISTS "${SRC}/game/server/server_hl2.vpc")
    message(FATAL_ERROR "Set SDK_DIR to a source-sdk-2013 checkout on branch singleplayer")
endif()
if(NOT MSVC)
    message(FATAL_ERROR "Build with clang-cl (game/toolchain-clangcl-x86.cmake) or MSVC")
endif()
if(CMAKE_SIZEOF_VOID_P EQUAL 8)
    message(FATAL_ERROR "Retail HL2 is 32-bit; build x86")
endif()

find_package(Python3 REQUIRED COMPONENTS Interpreter)

# Valve's file list for a VPC project, read from the .vpc scripts so it never
# drifts from the SDK.
function(vpc_sources out vpc)
    execute_process(
        COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/../tools/vpc_sources.py" "${SRC}/${vpc}"
        OUTPUT_VARIABLE files OUTPUT_STRIP_TRAILING_WHITESPACE
        COMMAND_ERROR_IS_FATAL ANY)
    string(REPLACE "\n" ";" files "${files}")
    set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${SRC}/${vpc}")
    set(${out} ${files} PARENT_SCOPE)
endfunction()

# Valve's release settings (vpc_scripts/source_dll_win32_release.vpc): /O2,
# /fp:fast, RTTI on, C++ exceptions off, everything compiled as C++.
set(VALVE_COMPILE_OPTIONS
    /O2 /Ob2 /Oi /Ot /GF /Gy /GR /fp:fast /Zc:forScope /TP /Z7
    # Valve's code under a 2026 front end: keep the build log readable.
    /W0 -Wno-everything
    # VS2013-era code relies on MSVC's permissive template lookup.
    -fms-compatibility -fdelayed-template-parsing)
set(VALVE_DEFINES
    VPC RAD_TELEMETRY_DISABLED
    COMPILER_MSVC COMPILER_MSVC32 _DLL_EXT=.dll FRAME_POINTER_OMISSION_DISABLED
    WIN32 _WIN32 NDEBUG _WINDOWS _CRT_SECURE_NO_DEPRECATE _CRT_NONSTDC_NO_DEPRECATE
    _ALLOW_RUNTIME_LIBRARY_MISMATCH _ALLOW_ITERATOR_DEBUG_LEVEL_MISMATCH
    _ALLOW_MSC_VER_MISMATCH)
set(VALVE_INCLUDES
    # Shims for headers the modern UCRT dropped.
    "${CMAKE_CURRENT_SOURCE_DIR}/compat"
    "${SRC}/common" "${SRC}/public" "${SRC}/public/tier0" "${SRC}/public/tier1")

# tier1 and mathlib from source rather than Valve's VS2013 .libs. Object
# libraries, linked straight into the dll (no librarian needed).
vpc_sources(TIER1_SOURCES tier1/tier1.vpc)
add_library(tier1 OBJECT ${TIER1_SOURCES})
target_compile_options(tier1 PRIVATE ${VALVE_COMPILE_OPTIONS})
target_compile_definitions(tier1 PRIVATE ${VALVE_DEFINES} _LIB TIER1_STATIC_LIB LIBNAME=tier1)
target_include_directories(tier1 PRIVATE ${VALVE_INCLUDES})

vpc_sources(MATHLIB_SOURCES mathlib/mathlib.vpc)
# 3DNow inline asm that clang cannot assemble; no current CPU has 3DNow, and
# sdk-compat.patch keeps mathlib from selecting it.
list(FILTER MATHLIB_SOURCES EXCLUDE REGEX "/3dnow\\.cpp$")
add_library(mathlib OBJECT ${MATHLIB_SOURCES})
target_compile_options(mathlib PRIVATE ${VALVE_COMPILE_OPTIONS})
target_compile_definitions(mathlib PRIVATE ${VALVE_DEFINES} _LIB MATHLIB_LIB LIBNAME=mathlib)
target_include_directories(mathlib PRIVATE ${VALVE_INCLUDES} "${SRC}/public/mathlib")

# The server.
vpc_sources(SERVER_SOURCES game/server/server_hl2.vpc)
file(GLOB AP_SOURCES CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/src/*.cpp")

add_library(server SHARED ${SERVER_SOURCES} ${AP_SOURCES}
    $<TARGET_OBJECTS:tier1> $<TARGET_OBJECTS:mathlib>)
set_target_properties(server PROPERTIES OUTPUT_NAME "server" PREFIX "")
target_compile_options(server PRIVATE ${VALVE_COMPILE_OPTIONS})
target_compile_definitions(server PRIVATE ${VALVE_DEFINES}
    _USRDLL DLLNAME=server
    GAME_DLL VECTOR VERSION_SAFE_STEAM_API_INTERFACES PROTECTED_THINGS_ENABLE
    sprintf=use_Q_snprintf_instead_of_sprintf strncpy=use_Q_strncpy_instead
    _snprintf=use_Q_snprintf_instead fopen=dont_use_fopen
    HL2_DLL USES_SAVERESTORE)
target_include_directories(server PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/src"
    ${VALVE_INCLUDES}
    "${SRC}/game/server" "${SRC}/game/shared" "${SRC}/utils/common"
    "${SRC}/game/shared/econ" "${SRC}/game/server/NextBot"
    "${SRC}/game/shared/hl2" "${SRC}/game/server/hl2")

option(HL2AP_TEST_BUILD "Build the scenario harness in. Never for release." OFF)
if(HL2AP_TEST_BUILD)
    target_compile_definitions(server PRIVATE HL2AP_TEST_BUILD)
endif()

# Valve's prebuilt libs. tier0, vstdlib and steam_api are import libs; the
# rest are VS2013 static libs whose sources are not in the SDK.
set(VALVE_LIBS "${SRC}/lib/public")
target_link_libraries(server PRIVATE
    "${VALVE_LIBS}/tier0.lib" "${VALVE_LIBS}/vstdlib.lib" "${VALVE_LIBS}/steam_api.lib"
    "${VALVE_LIBS}/choreoobjects.lib" "${VALVE_LIBS}/dmxloader.lib"
    "${VALVE_LIBS}/particles.lib" "${VALVE_LIBS}/tier2.lib" "${VALVE_LIBS}/tier3.lib"
    # VS2013 objects call the pre-UCRT stdio entry points.
    legacy_stdio_definitions
    winmm shell32 user32 advapi32 gdi32 comdlg32 ole32 ws2_32 rpcrt4)
target_link_options(server PRIVATE
    /DEBUG /OPT:REF /OPT:ICF /NODEFAULTLIB:libc /NODEFAULTLIB:libcd /NODEFAULTLIB:libcmtd)
