param(
    [Parameter(Mandatory = $true)][string]$InputPath,
    [Parameter(Mandatory = $true)][string]$OutputPath
)

$ErrorActionPreference = 'Stop'
$word = $null
$document = $null
try {
    $inputResolved = (Resolve-Path -LiteralPath $InputPath).Path
    $outputFull = [System.IO.Path]::GetFullPath($OutputPath)
    $outputParent = [System.IO.Path]::GetDirectoryName($outputFull)
    [System.IO.Directory]::CreateDirectory($outputParent) | Out-Null
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $document = $word.Documents.Open($inputResolved, $false, $true)
    $document.ExportAsFixedFormat($outputFull, 17)
    Write-Output ("Microsoft Word " + $word.Version)
}
finally {
    if ($null -ne $document) {
        $document.Close($false)
        [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($document)
    }
    if ($null -ne $word) {
        $word.Quit()
        [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($word)
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
