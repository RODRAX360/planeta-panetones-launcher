Unicode true
!include "MUI2.nsh"

!ifndef APP_VERSION
  !error "Pass /DAPP_VERSION=<version> to makensis"
!endif

Name "Planeta Panetones"
OutFile "..\dist\PlanetaPanetones-Setup-${APP_VERSION}.exe"
InstallDir "$LOCALAPPDATA\Programs\PlanetaPanetones"
RequestExecutionLevel user
!ifdef OFFLINE_FAST
  SetCompressor zlib
!else
  SetCompressor /SOLID lzma
!endif
ShowInstDetails nevershow
ShowUninstDetails nevershow
!define MUI_ABORTWARNING
!define MUI_ICON "..\assets\launcher.ico"
!define MUI_UNICON "..\assets\launcher.ico"
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "Spanish"

Section "Instalar"
  SetOutPath "$INSTDIR"
  ClearErrors
  File /r "..\dist\PlanetaPanetones\*"
  IfErrors installation_failed
  WriteUninstaller "$INSTDIR\Desinstalar.exe"
  CreateDirectory "$SMPROGRAMS\Planeta Panetones"
  CreateShortCut "$SMPROGRAMS\Planeta Panetones\Planeta Panetones.lnk" "$INSTDIR\PlanetaPanetones.exe"
  CreateShortCut "$DESKTOP\Planeta Panetones.lnk" "$INSTDIR\PlanetaPanetones.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\PlanetaPanetones" "DisplayName" "Planeta Panetones"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\PlanetaPanetones" "DisplayVersion" "${APP_VERSION}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\PlanetaPanetones" "UninstallString" '"$INSTDIR\Desinstalar.exe"'
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\PlanetaPanetones" "DisplayIcon" "$INSTDIR\PlanetaPanetones.exe"
  Goto installation_done
installation_failed:
  Abort "No se pudieron copiar todos los archivos del launcher. Cierra Planeta Panetones e inténtalo de nuevo."
installation_done:
SectionEnd

Section "Uninstall"
  Delete "$DESKTOP\Planeta Panetones.lnk"
  RMDir /r "$SMPROGRAMS\Planeta Panetones"
  RMDir /r "$INSTDIR"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\PlanetaPanetones"
SectionEnd
