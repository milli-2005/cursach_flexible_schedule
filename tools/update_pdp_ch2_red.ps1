param(
    [string]$SourcePath,
    [string]$DestPath,
    [string]$DataPath = ''
)

$ErrorActionPreference = 'Stop'

$wdColorRed = 255
$wdAlignLeft = 0
$wdAlignJustify = 3

function Format-Range {
    param(
        $Range,
        [string]$FontName,
        [int]$Size,
        [int]$Color,
        [double]$Indent,
        [int]$Align,
        [bool]$Bold
    )

    $Range.Font.Name = $FontName
    $Range.Font.Size = $Size
    $Range.Font.Color = $Color
    if ($Bold) {
        $Range.Font.Bold = -1
    } else {
        $Range.Font.Bold = 0
    }
    $Range.ParagraphFormat.Alignment = $Align
    $Range.ParagraphFormat.FirstLineIndent = $Indent
    $Range.ParagraphFormat.SpaceAfter = 0
    $Range.ParagraphFormat.SpaceBefore = 0
}

function Insert-AtParagraphStart {
    param(
        $Doc,
        [int]$ParagraphIndex,
        [string]$Text,
        [string]$FontName,
        [int]$Size,
        [double]$Indent,
        [int]$Align,
        [bool]$Bold
    )

    $start = $Doc.Paragraphs.Item($ParagraphIndex).Range.Start
    $range = $Doc.Range($start, $start)
    $range.Text = $Text + "`r"
    Format-Range -Range $range -FontName $FontName -Size $Size -Color $wdColorRed -Indent $Indent -Align $Align -Bold $Bold
}

if ([string]::IsNullOrWhiteSpace($DataPath)) {
    $DataPath = Join-Path $PSScriptRoot 'pdp_ch2_red_data.json'
}

$data = Get-Content -LiteralPath $DataPath -Raw -Encoding UTF8 | ConvertFrom-Json

Copy-Item -LiteralPath $SourcePath -Destination $DestPath -Force

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0

try {
    $doc = $word.Documents.Open($DestPath)

    $doc.Paragraphs.Item(232).Range.Text = $data.listing13 + "`r"
    Format-Range -Range $doc.Paragraphs.Item(232).Range -FontName 'Times New Roman' -Size 14 -Color $wdColorRed -Indent 35.45 -Align $wdAlignLeft -Bold $false

    $doc.Paragraphs.Item(230).Range.Text = $data.pgParagraph + "`r"
    Format-Range -Range $doc.Paragraphs.Item(230).Range -FontName 'Times New Roman' -Size 14 -Color $wdColorRed -Indent 35.45 -Align $wdAlignJustify -Bold $false

    $doc.Paragraphs.Item(199).Range.Text = $data.listing12 + "`r"
    Format-Range -Range $doc.Paragraphs.Item(199).Range -FontName 'Times New Roman' -Size 14 -Color $wdColorRed -Indent 35.45 -Align $wdAlignLeft -Bold $false

    $doc.Paragraphs.Item(187).Range.Text = $data.listing11 + "`r"
    Format-Range -Range $doc.Paragraphs.Item(187).Range -FontName 'Times New Roman' -Size 14 -Color $wdColorRed -Indent 35.45 -Align $wdAlignLeft -Bold $false

    $doc.Paragraphs.Item(167).Range.Text = $data.listing10 + "`r"
    Format-Range -Range $doc.Paragraphs.Item(167).Range -FontName 'Times New Roman' -Size 14 -Color $wdColorRed -Indent 35.45 -Align $wdAlignLeft -Bold $false

    $doc.Paragraphs.Item(157).Range.Text = $data.listing9 + "`r"
    Format-Range -Range $doc.Paragraphs.Item(157).Range -FontName 'Times New Roman' -Size 14 -Color $wdColorRed -Indent 35.45 -Align $wdAlignLeft -Bold $false

    $doc.Paragraphs.Item(147).Range.Text = $data.listing8 + "`r"
    Format-Range -Range $doc.Paragraphs.Item(147).Range -FontName 'Times New Roman' -Size 14 -Color $wdColorRed -Indent 35.45 -Align $wdAlignLeft -Bold $false

    $doc.Paragraphs.Item(135).Range.Text = $data.listing7 + "`r"
    Format-Range -Range $doc.Paragraphs.Item(135).Range -FontName 'Times New Roman' -Size 14 -Color $wdColorRed -Indent 35.45 -Align $wdAlignLeft -Bold $false

    Insert-AtParagraphStart -Doc $doc -ParagraphIndex 216 -Text $data.versionParagraph -FontName 'Times New Roman' -Size 14 -Indent 35.45 -Align $wdAlignJustify -Bold $false

    $doc.Paragraphs.Item(126).Range.Text = $data.heading22 + "`r"
    Format-Range -Range $doc.Paragraphs.Item(126).Range -FontName 'Times New Roman' -Size 14 -Color $wdColorRed -Indent 35.45 -Align $wdAlignJustify -Bold $true

    $doc.Paragraphs.Item(91).Range.Text = $data.overview91 + "`r"
    Format-Range -Range $doc.Paragraphs.Item(91).Range -FontName 'Times New Roman' -Size 14 -Color $wdColorRed -Indent 35.45 -Align $wdAlignJustify -Bold $false

    Insert-AtParagraphStart -Doc $doc -ParagraphIndex 90 -Text $data.overview89add -FontName 'Times New Roman' -Size 14 -Indent 35.45 -Align $wdAlignJustify -Bold $false

    foreach ($entry in $data.newParagraphs) {
        Insert-AtParagraphStart -Doc $doc -ParagraphIndex 135 -Text $entry.text -FontName $entry.font -Size ([int]$entry.size) -Indent ([double]$entry.indent) -Align ([int]$entry.align) -Bold ([bool]$entry.bold)
    }

    $doc.Save()
    $doc.Close()
}
finally {
    if ($word -ne $null) {
        $word.Quit()
    }
}

Write-Output $DestPath
