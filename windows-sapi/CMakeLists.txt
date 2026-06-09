# Build the EYEWAZ SAPI5 voice DLL (Windows, MSVC).
#
#   cmake -S . -B build -A x64
#   cmake --build build --config Release
#   regsvr32 build\Release\EyewazTts.dll        (elevated)
#
# Requires the Windows SDK (sapi.h, sapiddk.h are part of it). Build x64 to use
# the voice in 64-bit screen readers; build Win32 as well for 32-bit hosts.
cmake_minimum_required(VERSION 3.20)
project(EyewazTts LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_library(EyewazTts SHARED
    src/EyewazTtsEngine.cpp
    src/dll.cpp
    src/EyewazTts.def
)

target_compile_definitions(EyewazTts PRIVATE UNICODE _UNICODE WIN32_LEAN_AND_MEAN)
target_link_libraries(EyewazTts PRIVATE winhttp ole32 oleaut32 advapi32)

# sapi.lib ships with the Windows SDK; usually found automatically. If not, point
# CMake at it: target_link_libraries(EyewazTts PRIVATE "$ENV{WindowsSdkDir}/Lib/.../sapi.lib")
