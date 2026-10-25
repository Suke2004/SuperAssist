Option Explicit
Dim shell, files, folder, logPath, command, quote, exitCode
Set shell = CreateObject("WScript.Shell")
Set files = CreateObject("Scripting.FileSystemObject")
folder = files.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = folder
logPath = files.BuildPath(folder, "output\desktop-launch.log")
quote = Chr(34)

On Error Resume Next
If Not files.FolderExists(files.BuildPath(folder, "output")) Then
    files.CreateFolder files.BuildPath(folder, "output")
End If
If Err.Number <> 0 Then
    shell.Popup "Cannot create the desktop startup log: " & Err.Description, 0, "VeyraCue startup", 16
    WScript.Quit 1
End If

command = quote & shell.ExpandEnvironmentStrings("%ComSpec%") & quote & " /d /s /c " & quote & quote & files.BuildPath(folder, "run.bat") & quote & " --silent > " & quote & logPath & quote & " 2>&1" & quote
exitCode = shell.Run(command, 0, True)
If Err.Number <> 0 Then
    shell.Popup "Cannot start the desktop assistant: " & Err.Description, 0, "VeyraCue startup", 16
    WScript.Quit 1
End If
If exitCode <> 0 Then
    shell.Popup "The desktop assistant could not start. See " & logPath, 0, "VeyraCue startup", 16
End If
WScript.Quit exitCode
