Unicode true
!include "LogicLib.nsh"

Name "Planeta Panetones - Rescate de actualizacion"
OutFile "PlanetaPanetones-Rescate.exe"
RequestExecutionLevel user
SilentInstall silent
ShowInstDetails nevershow
AutoCloseWindow true

Section "Actualizar"
  InitPluginsDir
  SetOutPath "$PLUGINSDIR"
  File /oname=install.ps1 "install.ps1"
  nsExec::ExecToStack 'powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$PLUGINSDIR\install.ps1" -OutFile "$PLUGINSDIR\PlanetaPanetones-Setup-full.exe"'
  Pop $0
  Pop $1
  ${If} $0 != "0"
    SetErrorLevel 1
    Quit
  ${EndIf}
  SetErrorLevel 0
SectionEnd
