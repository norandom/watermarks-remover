<#
Find invisible characters in text files. Pure PowerShell, nothing to install.

REQUIRES: Windows PowerShell 5.1, which ships with Windows 10 and 11. Nothing
to install. Also runs unchanged on PowerShell 7 (pwsh) on Windows, Linux and
macOS. Verified on both.

    irm https://raw.githubusercontent.com/norandom/watermarks-remover/main/scripts/detect.ps1 | iex

To point it somewhere else, set a variable first. A script run through iex
cannot take parameters, so this is the only way:

    $WmPath = 'C:\src\myrepo'; irm <url> | iex
    $WmIncludeHidden = $true;  irm <url> | iex

Before you run anything piped into iex, from this repository or any other:
read it. This one only reads files. It never writes, deletes, or connects
anywhere. You can check that in about a minute, and you should.

WHAT THIS IS NOT

This is not wm-hook. It finds every invisible character and stops there. It
has no explanation layer, so it cannot tell an emoji presentation selector
from a payload, or an Arabic joiner from smuggled bytes.

In the measured corpus that gap was two orders of magnitude: 29 carriers
found, 27 of them entirely legitimate. This script reports the first number.
Treat a hit as "look at this", never as "something is hidden here".
#>

Set-StrictMode -Version Latest

# A #Requires line is inert when this arrives through iex, because iex sees a
# string rather than a script file. So the version gate has to be a real check.
if ($PSVersionTable.PSVersion -lt [version]'5.1') {
    Write-Error ("Needs Windows PowerShell 5.1 or later. This is " +
                 "$($PSVersionTable.PSVersion). 5.1 ships with Windows 10 and 11.")
    return
}

# Get-Variable, not $WmPath directly. Under StrictMode a bare reference to an
# unset variable is a terminating error, and these are optional by design.
function Get-Opt($name, $default) {
    $v = Get-Variable -Name $name -ValueOnly -ErrorAction SilentlyContinue
    if ($null -eq $v -or $v -eq '') { return $default }
    return $v
}

$Target = Get-Opt 'WmPath' '.'
$IncludeHidden = [bool](Get-Opt 'WmIncludeHidden' $false)

if (-not (Test-Path -LiteralPath $Target)) {
    Write-Error "No such path: $Target"
    return
}

$SkipDirs = @('.git', 'node_modules', '.venv', 'venv', '__pycache__',
              'dist', 'build', 'target', 'site', '.mypy_cache',
              '.pytest_cache', '.ruff_cache', '.tox')

$TextExt = @('.md','.markdown','.mdx','.qmd','.rmd','.txt','.rst','.tex',
             '.py','.ps1','.psm1','.psd1','.sh','.bash','.zsh',
             '.js','.mjs','.cjs','.ts','.tsx','.jsx','.css','.html',
             '.json','.yaml','.yml','.toml','.ini','.cfg','.xml',
             '.rs','.go','.c','.h','.cpp','.hpp','.java','.rb','.sql','.po')

# .NET regex matches UTF-16, so anything above U+FFFF has to be written as a
# surrogate pair. U+E0000 is not [\uE0000]; it is high \uDB40 plus low \uDC00.
# Writing \uE0000 silently means "\uE000 followed by 0", which matches
# private-use U+E000 and quietly reports the wrong class.
$Classes = [ordered]@{
    'zero width'         = '[\u200B\u200C\u200D\u2060\uFEFF]'
    'tag block'          = '\uDB40[\uDC00-\uDC7F]'
    'private use'        = '[\uE000-\uF8FF]|[\uDB80-\uDBFF][\uDC00-\uDFFF]'
    'bidi control'       = '[\u200E\u200F\u061C\u202A-\u202E\u2066-\u2069]'
    'variation selector' = '[\uFE00-\uFE0F]|\uDB40[\uDD00-\uDDEF]'
    'space homoglyph'    = '[\u00A0\u1680\u2000-\u200A\u202F\u205F\u3000]'
}

$Compiled = [ordered]@{}
foreach ($name in $Classes.Keys) {
    $Compiled[$name] = [regex]::new($Classes[$name],
        [System.Text.RegularExpressions.RegexOptions]::Compiled)
}

$root = (Resolve-Path -LiteralPath $Target).Path
$files = Get-ChildItem -LiteralPath $root -Recurse -File -Force -ErrorAction SilentlyContinue |
    Where-Object {
        $rel = $_.FullName.Substring($root.Length).TrimStart('\', '/')
        $parts = $rel -split '[\\/]'
        if ($TextExt -notcontains $_.Extension.ToLower()) { return $false }
        foreach ($p in $parts) { if ($SkipDirs -contains $p) { return $false } }
        if (-not $IncludeHidden) {
            foreach ($p in $parts) { if ($p.StartsWith('.')) { return $false } }
        }
        return $true
    }

$hits = [ordered]@{}
foreach ($name in $Classes.Keys) { $hits[$name] = [System.Collections.ArrayList]::new() }

$scanned = 0
foreach ($f in $files) {
    try {
        $text = [System.IO.File]::ReadAllText($f.FullName, [System.Text.Encoding]::UTF8)
    } catch { continue }
    # IndexOf([char]0), not IndexOf("`0"). The string overload is culture
    # sensitive by default, and NUL is an ignorable character to the default
    # comparer, so IndexOf("`0") returns 0 for every string ever. That marked
    # all 13 files binary and reported "0 files scanned" on a full directory.
    # The char overload is always ordinal.
    if ($text.IndexOf([char]0) -ge 0) { continue }   # looks binary
    $scanned++

    $lines = $null
    foreach ($name in $Compiled.Keys) {
        if (-not $Compiled[$name].IsMatch($text)) { continue }
        if ($null -eq $lines) { $lines = $text -split "`r?`n" }
        for ($i = 0; $i -lt $lines.Count; $i++) {
            if ($Compiled[$name].IsMatch($lines[$i])) {
                $rel = $f.FullName.Substring($root.Length).TrimStart('\', '/')
                [void]$hits[$name].Add("$rel`:$($i + 1)")
            }
        }
    }
}

$total = 0
foreach ($name in $hits.Keys) { $total += $hits[$name].Count }

Write-Host ""
Write-Host "$scanned file(s) scanned in $root"

foreach ($name in $hits.Keys) {
    $found = $hits[$name]
    if ($found.Count -eq 0) { continue }
    Write-Host ""
    Write-Host "== $name ($($found.Count))" -ForegroundColor Yellow
    # Locations only. Printing the matching line would put an invisible
    # character into your terminal, which is how this problem starts.
    $found | Select-Object -First 40 | ForEach-Object { Write-Host "   $_" }
    if ($found.Count -gt 40) {
        Write-Host "   ... and $($found.Count - 40) more"
    }
}

Write-Host ""
if ($scanned -eq 0) {
    # A scan that never happened must not report a clean bill of health.
    # "No invisible characters found" after reading zero files is the same
    # manufactured confidence the main tool refuses to print.
    Write-Host "No text files were found under $root. Nothing was checked." -ForegroundColor Red
    Write-Host "Set `$WmIncludeHidden = `$true to include dot directories."
    $global:LASTEXITCODE = 2
    return
}
if ($total -eq 0) {
    Write-Host "No invisible characters found." -ForegroundColor Green
    Write-Host "That is not proof a human wrote it. Statistical watermarks change"
    Write-Host "which words a model picks and leave no character trace at all."
} else {
    Write-Host "$total line(s) contain invisible characters." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Most of these are legitimate. Emoji need variation selectors,"
    Write-Host "Arabic and Devanagari need joiners, and a byte-order mark is just"
    Write-Host "an encoding signature. This script cannot tell those apart from"
    Write-Host "hidden data. For a verdict rather than a list:"
    Write-Host ""
    Write-Host "  uvx --from git+https://github.com/norandom/watermarks-remover ``"
    Write-Host "      wm-hook --detect $Target"
}

# Never `exit` here. Run through iex this code is executing in the user's own
# session, and `exit` would close their shell. Set the variable a caller can
# check and let the pipeline end normally.
$global:LASTEXITCODE = if ($total -gt 0) { 1 } else { 0 }
