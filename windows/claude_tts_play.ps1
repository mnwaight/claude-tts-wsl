param([string]$FilePath)
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public class MCIHelper {
    [DllImport("winmm.dll", CharSet=CharSet.Auto)]
    public static extern int mciSendString(string cmd, System.Text.StringBuilder ret, int retSize, IntPtr cb);
}
'@
[MCIHelper]::mciSendString("close claudetts", $null, 0, [IntPtr]::Zero) | Out-Null
[MCIHelper]::mciSendString("open `"$FilePath`" type mpegvideo alias claudetts", $null, 0, [IntPtr]::Zero) | Out-Null
[MCIHelper]::mciSendString("play claudetts wait", $null, 0, [IntPtr]::Zero) | Out-Null
[MCIHelper]::mciSendString("close claudetts", $null, 0, [IntPtr]::Zero) | Out-Null
