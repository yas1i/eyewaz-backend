// EYEWAZ SAPI5 voice — COM identity.
// Generate your OWN CLSID with `uuidgen` and paste it here before shipping;
// the placeholder below must be unique to your build.
#pragma once
#include <initguid.h>

// {705EFB11-63AC-4556-8C54-47DD2373657D}  EYEWAZ Urdu SAPI5 voice (unique per WAJD AI)
DEFINE_GUID(CLSID_EyewazTtsEngine,
    0x705efb11, 0x63ac, 0x4556, 0x8c, 0x54, 0x47, 0xdd, 0x23, 0x73, 0x65, 0x7d);

// Registry token id shown to screen readers / Windows.
#define EYEWAZ_TOKEN_ID    L"HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Speech\\Voices\\Tokens\\EYEWAZ-Urdu"
#define EYEWAZ_VOICE_NAME  L"EYEWAZ Urdu"
