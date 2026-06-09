// EYEWAZ SAPI5 voice — COM identity.
// Generate your OWN CLSID with `uuidgen` and paste it here before shipping;
// the placeholder below must be unique to your build.
#pragma once
#include <initguid.h>

// {7B11A1E0-1E2D-4C3A-9E10-EAEAEA000001}  <-- REPLACE with your own uuidgen value
DEFINE_GUID(CLSID_EyewazTtsEngine,
    0x7b11a1e0, 0x1e2d, 0x4c3a, 0x9e, 0x10, 0xea, 0xea, 0xea, 0x00, 0x00, 0x01);

// Registry token id shown to screen readers / Windows.
#define EYEWAZ_TOKEN_ID    L"HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Speech\\Voices\\Tokens\\EYEWAZ-Urdu"
#define EYEWAZ_VOICE_NAME  L"EYEWAZ Urdu"
