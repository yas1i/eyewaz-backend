' EYEWAZ Urdu Voice - hidden launcher for the local speech server.
' Started by the "EYEWAZ Urdu Voice Server" logon task. Runs the frozen server
' with NO visible window (the 0 in .Run). Self-locating: everything is resolved
' relative to this script's own folder, so the install location can be anywhere.
Option Explicit
Dim fso, sh, appDir, cmd
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh  = CreateObject("WScript.Shell")
appDir = fso.GetParentFolderName(WScript.ScriptFullName)

' If it is already listening, do nothing (avoids a second copy on re-logon).
On Error Resume Next
Dim exec, out
Set exec = sh.Exec("cmd /c netstat -ano -p tcp | findstr :59125 | findstr LISTENING")
out = exec.StdOut.ReadAll()
If InStr(out, "59125") > 0 Then WScript.Quit 0
On Error Goto 0

cmd = """" & appDir & "\eyewaz-voice-server.exe""" & _
      " --piper-exe """ & appDir & "\piper\piper.exe""" & _
      " --voices-dir """ & appDir & "\voices""" & _
      " --port 59125"
sh.Run cmd, 0, False   ' 0 = hidden window, False = do not wait
