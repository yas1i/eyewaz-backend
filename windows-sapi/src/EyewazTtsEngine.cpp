#include "EyewazTtsEngine.h"
#include "guids.h"
#include <winhttp.h>
#include <new>

#pragma comment(lib, "winhttp.lib")
#pragma comment(lib, "sapi.lib")

CEyewazTtsEngine::CEyewazTtsEngine()
    : m_cRef(1), m_endpoint(L"http://127.0.0.1:59125/tts") {}
CEyewazTtsEngine::~CEyewazTtsEngine() {}

// ---------- IUnknown ----------
STDMETHODIMP CEyewazTtsEngine::QueryInterface(REFIID riid, void** ppv) {
    if (!ppv) return E_POINTER;
    if (riid == IID_IUnknown || riid == IID_ISpTTSEngine)
        *ppv = static_cast<ISpTTSEngine*>(this);
    else if (riid == IID_ISpObjectWithToken)
        *ppv = static_cast<ISpObjectWithToken*>(this);
    else { *ppv = nullptr; return E_NOINTERFACE; }
    AddRef();
    return S_OK;
}
STDMETHODIMP_(ULONG) CEyewazTtsEngine::AddRef() { return InterlockedIncrement(&m_cRef); }
STDMETHODIMP_(ULONG) CEyewazTtsEngine::Release() {
    LONG c = InterlockedDecrement(&m_cRef);
    if (c == 0) delete this;
    return c;
}

// ---------- ISpObjectWithToken ----------
STDMETHODIMP CEyewazTtsEngine::SetObjectToken(ISpObjectToken* pToken) {
    m_cpToken = pToken;
    LoadEndpointFromToken();
    return S_OK;
}
STDMETHODIMP CEyewazTtsEngine::GetObjectToken(ISpObjectToken** ppToken) {
    if (!ppToken) return E_POINTER;
    *ppToken = m_cpToken;
    if (*ppToken) (*ppToken)->AddRef();
    return S_OK;
}

void CEyewazTtsEngine::LoadEndpointFromToken() {
    // Optional: let the installed token override the endpoint / key via its
    // attributes ("Endpoint", "ApiKey"). Falls back to the localhost default.
    if (!m_cpToken) return;
    CComPtr<ISpDataKey> attrs;
    if (SUCCEEDED(m_cpToken->OpenKey(L"Attributes", &attrs)) && attrs) {
        LPWSTR v = nullptr;
        if (SUCCEEDED(attrs->GetStringValue(L"Endpoint", &v)) && v) { m_endpoint = v; CoTaskMemFree(v); }
        v = nullptr;
        if (SUCCEEDED(attrs->GetStringValue(L"ApiKey", &v)) && v) { m_apiKey = v; CoTaskMemFree(v); }
    }
}

// ---------- ISpTTSEngine::GetOutputFormat ----------
// Tell SAPI the format we natively produce; SAPI resamples to the device.
STDMETHODIMP CEyewazTtsEngine::GetOutputFormat(const GUID*, const WAVEFORMATEX*,
                                               GUID* pOutputFormatId,
                                               WAVEFORMATEX** ppCoMemWFEX) {
    if (!pOutputFormatId || !ppCoMemWFEX) return E_POINTER;
    *pOutputFormatId = SPDFID_WaveFormatEx;
    WAVEFORMATEX* wfex = (WAVEFORMATEX*)CoTaskMemAlloc(sizeof(WAVEFORMATEX));
    if (!wfex) return E_OUTOFMEMORY;
    wfex->wFormatTag      = WAVE_FORMAT_PCM;
    wfex->nChannels       = kChannels;
    wfex->nSamplesPerSec  = kSampleRate;
    wfex->wBitsPerSample  = kBitsPerSample;
    wfex->nBlockAlign     = (kChannels * kBitsPerSample) / 8;
    wfex->nAvgBytesPerSec = kSampleRate * wfex->nBlockAlign;
    wfex->cbSize          = 0;
    *ppCoMemWFEX = wfex;
    return S_OK;
}

// ---------- ISpTTSEngine::Speak ----------
// Walk the fragment list, synthesize each run, write PCM to the site, and bail
// out promptly if SAPI signals an abort (e.g. the user interrupts speech).
STDMETHODIMP CEyewazTtsEngine::Speak(DWORD, REFGUID, const WAVEFORMATEX*,
                                     const SPVTEXTFRAG* pFrag,
                                     ISpTTSEngineSite* pSite) {
    if (!pSite) return E_POINTER;

    LONG rate = 0;
    pSite->GetRate(&rate);          // SAPI rate: -10..+10  -> map to speed
    USHORT volume = 100;
    pSite->GetVolume(&volume);      // 0..100

    for (; pFrag != nullptr; pFrag = pFrag->pNext) {
        if (pSite->GetActions() & SPVES_ABORT) break;
        if (!pFrag->pTextStart || pFrag->ulTextLen == 0) continue;

        std::wstring text(pFrag->pTextStart, pFrag->ulTextLen);

        std::vector<BYTE> pcm;
        if (!Synthesize(text, rate, pcm) || pcm.empty()) continue;

        // Apply volume (16-bit samples) before handing to SAPI.
        if (volume < 100) {
            short* s = reinterpret_cast<short*>(pcm.data());
            size_t n = pcm.size() / sizeof(short);
            for (size_t i = 0; i < n; ++i) s[i] = (short)(s[i] * volume / 100);
        }

        // Write in blocks so an abort is honoured mid-utterance.
        const ULONG kBlock = kSampleRate / 4 * (kBitsPerSample / 8); // ~0.25s
        for (size_t off = 0; off < pcm.size(); off += kBlock) {
            if (pSite->GetActions() & SPVES_ABORT) return S_OK;
            ULONG chunk = (ULONG)min((size_t)kBlock, pcm.size() - off);
            ULONG written = 0;
            pSite->Write(pcm.data() + off, chunk, &written);
        }
        // TODO: report SPEI_WORD_BOUNDARY events here for caret tracking by
        //       mapping character offsets -> sample offsets (pSite->AddEvents).
    }
    return S_OK;
}

// ---------- HTTP to the local Piper server ----------
// Minimal WinHTTP POST of {"text":...,"speed":...}; returns the WAV's PCM body.
bool CEyewazTtsEngine::Synthesize(const std::wstring& text, int rate,
                                  std::vector<BYTE>& pcmOut) {
    // SAPI rate -10..10 -> Piper speed ~0.5..2.0 (rate 0 == 1.0x).
    double speed = 1.0 + (rate * 0.07);
    if (speed < 0.5) speed = 0.5; if (speed > 2.0) speed = 2.0;

    // Build JSON body (UTF-8). Escape backslash and quote; Urdu passes as UTF-8.
    auto utf8 = [](const std::wstring& w) {
        int n = WideCharToMultiByte(CP_UTF8, 0, w.c_str(), (int)w.size(), nullptr, 0, nullptr, nullptr);
        std::string s(n, 0);
        WideCharToMultiByte(CP_UTF8, 0, w.c_str(), (int)w.size(), &s[0], n, nullptr, nullptr);
        return s;
    };
    std::string body = "{\"text\":\"";
    for (char c : utf8(text)) {
        if (c == '"' || c == '\\') body.push_back('\\');
        if (c == '\n' || c == '\r') { body += "\\n"; continue; }
        body.push_back(c);
    }
    body += "\",\"speed\":" + std::to_string(speed) + "}";

    // Parse endpoint into host/port/path.
    URL_COMPONENTS uc{}; uc.dwStructSize = sizeof(uc);
    wchar_t host[256] = {0}, path[1024] = {0};
    uc.lpszHostName = host; uc.dwHostNameLength = _countof(host);
    uc.lpszUrlPath = path;  uc.dwUrlPathLength  = _countof(path);
    if (!WinHttpCrackUrl(m_endpoint.c_str(), 0, 0, &uc)) return false;

    HINTERNET hS = WinHttpOpen(L"EYEWAZ-SAPI/1.0", WINHTTP_ACCESS_TYPE_NO_PROXY,
                               WINHTTP_NO_PROXY_NAME, WINHTTP_NO_PROXY_BYPASS, 0);
    if (!hS) return false;
    HINTERNET hC = WinHttpConnect(hS, host, uc.nPort, 0);
    HINTERNET hR = hC ? WinHttpOpenRequest(hC, L"POST", path, nullptr,
                        WINHTTP_NO_REFERER, WINHTTP_DEFAULT_ACCEPT_TYPES,
                        (uc.nScheme == INTERNET_SCHEME_HTTPS) ? WINHTTP_FLAG_SECURE : 0) : nullptr;
    bool ok = false;
    if (hR) {
        std::wstring headers = L"Content-Type: application/json\r\n";
        if (!m_apiKey.empty()) headers += L"X-API-Key: " + m_apiKey + L"\r\n";
        if (WinHttpSendRequest(hR, headers.c_str(), (DWORD)-1L,
                               (LPVOID)body.data(), (DWORD)body.size(),
                               (DWORD)body.size(), 0) &&
            WinHttpReceiveResponse(hR, nullptr)) {
            std::vector<BYTE> all;
            DWORD avail = 0;
            while (WinHttpQueryDataAvailable(hR, &avail) && avail) {
                size_t cur = all.size(); all.resize(cur + avail);
                DWORD read = 0;
                WinHttpReadData(hR, all.data() + cur, avail, &read);
                all.resize(cur + read);
            }
            // Strip the WAV header: find the "data" chunk and copy the rest.
            for (size_t i = 12; i + 8 <= all.size(); ) {
                DWORD sz = *(DWORD*)&all[i + 4];
                if (memcmp(&all[i], "data", 4) == 0) {
                    size_t start = i + 8;
                    size_t end = min(all.size(), start + sz);
                    pcmOut.assign(all.begin() + start, all.begin() + end);
                    ok = !pcmOut.empty();
                    break;
                }
                i += 8 + sz + (sz & 1);
            }
        }
        WinHttpCloseHandle(hR);
    }
    if (hC) WinHttpCloseHandle(hC);
    WinHttpCloseHandle(hS);
    return ok;
}
