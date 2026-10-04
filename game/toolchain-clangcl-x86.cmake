# Cross-build the 32-bit Source dlls on Linux with clang-cl + lld-link + xwin.
#
# Valve builds the SDK with MSVC on Windows. clang-cl matches MSVC's ABI, name
# decoration and export table, which is what the engine depends on.
#
# Point XWIN_ROOT at a splatted Windows SDK + CRT if it is not in ~/.xwin.
#
#   cmake -S game -B build/game -G Ninja \
#         -DCMAKE_TOOLCHAIN_FILE=game/toolchain-clangcl-x86.cmake \
#         -DSDK_DIR=../source-sdk-2013
#   cmake --build build/game

set(CMAKE_SYSTEM_NAME Windows)
set(CMAKE_SYSTEM_PROCESSOR x86)

if(NOT DEFINED XWIN_ROOT)
    set(XWIN_ROOT "$ENV{HOME}/.xwin" CACHE PATH "Splatted Windows SDK and CRT")
endif()
if(NOT EXISTS "${XWIN_ROOT}/crt/include")
    message(FATAL_ERROR "no splatted SDK at ${XWIN_ROOT}; run xwin, or set XWIN_ROOT")
endif()

set(CMAKE_C_COMPILER clang-cl)
set(CMAKE_CXX_COMPILER clang-cl)
set(CMAKE_LINKER lld-link)
set(CMAKE_C_COMPILER_TARGET i686-pc-windows-msvc)
set(CMAKE_CXX_COMPILER_TARGET i686-pc-windows-msvc)

# Retail HL2 is a 32-bit process. `-m32` as well as the triple, because CMake's
# compiler probe reads the pointer size from a compile.
set(_xwin_flags
    "-m32 --target=i686-pc-windows-msvc \
/imsvc ${XWIN_ROOT}/crt/include \
/imsvc ${XWIN_ROOT}/sdk/include/ucrt \
/imsvc ${XWIN_ROOT}/sdk/include/um \
/imsvc ${XWIN_ROOT}/sdk/include/shared")
set(CMAKE_C_FLAGS_INIT "${_xwin_flags}")
set(CMAKE_CXX_FLAGS_INIT "${_xwin_flags}")

# No manifest: CMake would drive that through `rc` and `mt`, which an xwin
# splat does not have, and a game dll needs none.
set(_xwin_libs
    "/MACHINE:X86 /MANIFEST:NO \
/libpath:${XWIN_ROOT}/crt/lib/x86 \
/libpath:${XWIN_ROOT}/sdk/lib/ucrt/x86 \
/libpath:${XWIN_ROOT}/sdk/lib/um/x86")
set(CMAKE_EXE_LINKER_FLAGS_INIT "${_xwin_libs}")
set(CMAKE_SHARED_LINKER_FLAGS_INIT "${_xwin_libs}")
set(CMAKE_MODULE_LINKER_FLAGS_INIT "${_xwin_libs}")

# The static release CRT everywhere, CMake's own probe included: it links Debug
# by default, and xwin carries no debug CRT.
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded")

set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM BEFORE)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY BEFORE)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE BEFORE)
