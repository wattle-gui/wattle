# make_shortcuts.py -- WINDOWS: puts "Wattle Editor", "Wattle Command Prompt" and "Wattle Manuals" on the Desktop and in the Start menu.
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PS = r'''
$sh = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath('Desktop')
$start = Join-Path ([Environment]::GetFolderPath('Programs')) 'Wattle'
New-Item -ItemType Directory -Force -Path $start | Out-Null
function Make($name, $target, $cmdline, $dir, $desc) {
    foreach ($folder in @($desktop, $start)) {
        $lnk = $sh.CreateShortcut((Join-Path $folder ($name + '.lnk')))
        $lnk.TargetPath = $target
        $lnk.Arguments = $cmdline
        $lnk.WorkingDirectory = $dir
        $lnk.Description = $desc
        $lnk.Save()
    }
}
Make 'Wattle Editor' '__PYW__' '"__HERE__\Editor\ESP32_Editor.py"' '__HERE__\Editor' 'Design the screens of your Wattle app'
Make 'Wattle Command Prompt' '__HERE__\wattle_prompt.cmd' '' '__HERE__' 'A command window where the wattle command works'
Make 'Wattle Manuals' '__HERE__\manual\books\index.html' '' '__HERE__\manual\books' 'The Wattle manuals'
Write-Output 'shortcuts made'
'''


def main():
    pyw = os.path.join(HERE, "python", "pythonw.exe")
    if not os.path.exists(pyw):
        pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    script = PS.replace("__PYW__", pyw).replace("__HERE__", HERE)
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script], capture_output=True, text=True)
    print((r.stdout + r.stderr).strip() or "done")
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
