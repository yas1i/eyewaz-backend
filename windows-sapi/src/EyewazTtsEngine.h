// EYEWAZ SAPI5 text-to-speech engine.
//
// Implements the two interfaces SAPI requires of a voice:
//   ISpTTSEngine        — Speak() / GetOutputFormat()
//   ISpObjectWithToken  — receive our registry voice token (settings)
//
// Synthesis is delegated over HTTP to the local EYEWAZ Piper server
// (../tts-local, default http://127.0.0.1:59125/tts) so the heavy lifting is the
// same trained voice used everywhere else. Keeping the audio engine out of C++
// means this DLL stays thin; the only native work is WAV decode + handing PCM
// back to SAPI and honouring rate/volume/abort.
#pragma once

#include <sapi.h>
#include <sapiddk.h>
#include <atlbase.h>
#include <string>
#include <vector>

class ATL_NO_VTABLE CEyewazTtsEngine
    : public ISpTTSEngine
    , public ISpObjectWithToken
{
public:
    CEyewazTtsEngine();
    virtual ~CEyewazTtsEngine();

    // IUnknown
    STDMETHOD(QueryInterface)(REFIID riid, void** ppv);
    STDMETHOD_(ULONG, AddRef)();
    STDMETHOD_(ULONG, Release)();

    // ISpTTSEngine
    STDMETHOD(Speak)(DWORD dwSpeakFlags, REFGUID rguidFormatId,
                     const WAVEFORMATEX* pWaveFormatEx,
                     const SPVTEXTFRAG* pTextFragList,
                     ISpTTSEngineSite* pOutputSite);
    STDMETHOD(GetOutputFormat)(const GUID* pTargetFmtId,
                               const WAVEFORMATEX* pTargetWaveFormatEx,
                               GUID* pOutputFormatId,
                               WAVEFORMATEX** ppCoMemOutputWaveFormatEx);

    // ISpObjectWithToken
    STDMETHOD(SetObjectToken)(ISpObjectToken* pToken);
    STDMETHOD(GetObjectToken)(ISpObjectToken** ppToken);

private:
    // POST `text` to the local Piper server and return decoded 16-bit PCM.
    bool Synthesize(const std::wstring& text, int rate, std::vector<BYTE>& pcmOut);
    // Pull endpoint (and optional API key) from the voice token, with defaults.
    void LoadEndpointFromToken();

    LONG                       m_cRef;
    CComPtr<ISpObjectToken>    m_cpToken;
    std::wstring               m_endpoint;   // e.g. http://127.0.0.1:59125/tts
    std::wstring               m_apiKey;     // usually empty for localhost

    // Native output format we produce (Piper medium = 22.05 kHz mono 16-bit).
    static const DWORD kSampleRate = 22050;
    static const WORD  kChannels   = 1;
    static const WORD  kBitsPerSample = 16;
};
