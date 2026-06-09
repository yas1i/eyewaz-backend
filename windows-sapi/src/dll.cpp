// COM in-proc server plumbing: class factory + (un)registration.
// DllRegisterServer also creates the SAPI voice token so the voice appears in
// JAWS / Narrator / "Speech" settings immediately after `regsvr32`.
#include "EyewazTtsEngine.h"
#include "guids.h"
#include <string>

static HMODULE g_hModule = nullptr;
static LONG    g_cLocks  = 0;

// ---------- Class factory ----------
class CFactory : public IClassFactory {
    LONG m_cRef = 1;
public:
    STDMETHODIMP QueryInterface(REFIID riid, void** ppv) {
        if (riid == IID_IUnknown || riid == IID_IClassFactory) { *ppv = this; AddRef(); return S_OK; }
        *ppv = nullptr; return E_NOINTERFACE;
    }
    STDMETHODIMP_(ULONG) AddRef() { return InterlockedIncrement(&m_cRef); }
    STDMETHODIMP_(ULONG) Release() { LONG c = InterlockedDecrement(&m_cRef); if (!c) delete this; return c; }
    STDMETHODIMP CreateInstance(IUnknown* pOuter, REFIID riid, void** ppv) {
        if (pOuter) return CLASS_E_NOAGGREGATION;
        CEyewazTtsEngine* p = new (std::nothrow) CEyewazTtsEngine();
        if (!p) return E_OUTOFMEMORY;
        HRESULT hr = p->QueryInterface(riid, ppv);
        p->Release();
        return hr;
    }
    STDMETHODIMP LockServer(BOOL f) { f ? InterlockedIncrement(&g_cLocks) : InterlockedDecrement(&g_cLocks); return S_OK; }
};

// ---------- DLL exports ----------
STDAPI DllGetClassObject(REFCLSID rclsid, REFIID riid, void** ppv) {
    if (rclsid != CLSID_EyewazTtsEngine) return CLASS_E_CLASSNOTAVAILABLE;
    CFactory* f = new (std::nothrow) CFactory();
    if (!f) return E_OUTOFMEMORY;
    HRESULT hr = f->QueryInterface(riid, ppv);
    f->Release();
    return hr;
}

STDAPI DllCanUnloadNow() { return g_cLocks == 0 ? S_OK : S_FALSE; }

// Helper: write a string value under an HKLM/HKCR key path.
static LONG SetStr(HKEY root, const wchar_t* sub, const wchar_t* name, const wchar_t* val) {
    HKEY k;
    LONG r = RegCreateKeyExW(root, sub, 0, nullptr, 0, KEY_WRITE, nullptr, &k, nullptr);
    if (r != ERROR_SUCCESS) return r;
    r = RegSetValueExW(k, name, 0, REG_SZ, (const BYTE*)val,
                       (DWORD)((wcslen(val) + 1) * sizeof(wchar_t)));
    RegCloseKey(k);
    return r;
}

STDAPI DllRegisterServer() {
    wchar_t path[MAX_PATH];
    GetModuleFileNameW(g_hModule, path, MAX_PATH);

    // Stringify our CLSID.
    wchar_t clsid[64]; StringFromGUID2(CLSID_EyewazTtsEngine, clsid, 64);

    // 1) COM server registration.
    std::wstring base = std::wstring(L"CLSID\\") + clsid;
    SetStr(HKEY_CLASSES_ROOT, base.c_str(), nullptr, EYEWAZ_VOICE_NAME);
    std::wstring inproc = base + L"\\InprocServer32";
    SetStr(HKEY_CLASSES_ROOT, inproc.c_str(), nullptr, path);
    SetStr(HKEY_CLASSES_ROOT, inproc.c_str(), L"ThreadingModel", L"Both");

    // 2) SAPI voice token — this is what makes JAWS/Narrator list the voice.
    const wchar_t* tok = L"SOFTWARE\\Microsoft\\Speech\\Voices\\Tokens\\EYEWAZ-Urdu";
    SetStr(HKEY_LOCAL_MACHINE, tok, nullptr, EYEWAZ_VOICE_NAME);
    SetStr(HKEY_LOCAL_MACHINE, tok, L"CLSID", clsid);
    std::wstring attr = std::wstring(tok) + L"\\Attributes";
    SetStr(HKEY_LOCAL_MACHINE, attr.c_str(), L"Name",     EYEWAZ_VOICE_NAME);
    SetStr(HKEY_LOCAL_MACHINE, attr.c_str(), L"Vendor",   L"WAJD AI");
    SetStr(HKEY_LOCAL_MACHINE, attr.c_str(), L"Language", L"420");   // Urdu (Pakistan)
    SetStr(HKEY_LOCAL_MACHINE, attr.c_str(), L"Gender",   L"Female");
    SetStr(HKEY_LOCAL_MACHINE, attr.c_str(), L"Age",      L"Adult");
    // Optional overrides read by the engine (else it uses the localhost default):
    SetStr(HKEY_LOCAL_MACHINE, attr.c_str(), L"Endpoint", L"http://127.0.0.1:59125/tts");
    return S_OK;
}

STDAPI DllUnregisterServer() {
    wchar_t clsid[64]; StringFromGUID2(CLSID_EyewazTtsEngine, clsid, 64);
    std::wstring base = std::wstring(L"CLSID\\") + clsid;
    RegDeleteTreeW(HKEY_CLASSES_ROOT, base.c_str());
    RegDeleteTreeW(HKEY_LOCAL_MACHINE,
        L"SOFTWARE\\Microsoft\\Speech\\Voices\\Tokens\\EYEWAZ-Urdu");
    return S_OK;
}

BOOL WINAPI DllMain(HINSTANCE h, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) { g_hModule = h; DisableThreadLibraryCalls(h); }
    return TRUE;
}
