# Explicit developer fixture generation. Only these synthetic sentences are written to target/.
[CmdletBinding()]
param([switch]$RecognitionQuality)
$ErrorActionPreference = 'Stop'
$fixtureRoot = Join-Path ([IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))) 'target\voice-bilingual-fixtures'
New-Item -ItemType Directory -Path $fixtureRoot -Force | Out-Null
$synth = New-Object -ComObject SAPI.SpVoice
$category = New-Object -ComObject SAPI.SpObjectTokenCategory
$category.SetId('HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech_OneCore\Voices', $false)
$voiceTokens = @($synth.GetVoices()) + @($category.EnumerateTokens())
$sentences = @(
    @{ language='en'; text='Could you help me find the presentation I saved yesterday?'; keywords=@('presentation','yesterday') },
    @{ language='en'; text='Please do not open that folder. Show me another option.'; keywords=@('not','folder','another') },
    @{ language='en'; text='Hello, can you hear me? I would like to ask a question.'; keywords=@('hear','question') },
    @{ language='tr'; text='Dün kaydettiğim sunum dosyasını bulmama yardımcı olur musun?'; keywords=@('sunum','dosyasını') },
    @{ language='tr'; text='O klasörü açma. Bana başka bir seçenek göster.'; keywords=@('açma','başka','seçenek') },
    @{ language='tr'; text='Merhaba, beni duyabiliyor musun? Sana bir soru sormak istiyorum.'; keywords=@('merhaba','soru','istiyorum') }
)
if ($RecognitionQuality) {
    $fixtureRoot = Join-Path ([IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))) 'target\voice-quality-fixtures'
    New-Item -ItemType Directory -Path $fixtureRoot -Force | Out-Null
    $sentences = @(
        @{ language='tr'; text="Steam'i açar mısın?"; keywords=@('steam','açar') },
        @{ language='tr'; text='Merhaba Jarvis, nasılsın?'; keywords=@('merhaba','jarvis','nasılsın') },
        @{ language='tr'; text="Steam'i açma. Sadece bir soru soracağım."; keywords=@('steam','açma','soru') },
        @{ language='tr'; text='Toplantı için hazırladığım tabloyu bulabilir misin?'; keywords=@('toplantı','tabloyu','bulabilir') },
        @{ language='tr'; text='Hayır, bu değil. Diğer seçeneği gösterir misin?'; keywords=@('hayır','değil','diğer') },
        @{ language='en'; text='Could you open Steam for me?'; keywords=@('open','steam') },
        @{ language='en'; text='Do not open the browser. I only have a question.'; keywords=@('not','browser','question') },
        @{ language='en'; text='Can you find the spreadsheet I saved yesterday?'; keywords=@('spreadsheet','yesterday') }
    )
}
$manifest = @()
for ($index = 0; $index -lt $sentences.Count; $index++) {
    $sentence = $sentences[$index]
    $primary = if ($sentence.language -eq 'tr') { 0x1f } else { 0x09 }
    $token = $voiceTokens | Where-Object {
        $attributes = $_.GetAttribute('Language') -split ';'
        @($attributes | Where-Object { ([Convert]::ToInt32($_,16) -band 0x3ff) -eq $primary }).Count -gt 0
    } | Select-Object -First 1
    if (-not $token) { throw "No installed $($sentence.language) fixture voice" }
    $synth.Voice = $token
    $path = Join-Path $fixtureRoot "$index.wav"
    $stream = New-Object -ComObject SAPI.SpFileStream
    $stream.Format.Type = 18 # SAFT16kHz16BitMono
    try {
        $stream.Open($path, 3, $false)
        $synth.AudioOutputStream = $stream
        $null = $synth.Speak($sentence.text, 16)
    } finally { $stream.Close() }
    $manifest += @{ file="$index.wav"; language=$sentence.language; text=$sentence.text; keywords=$sentence.keywords }
}
[IO.File]::WriteAllText((Join-Path $fixtureRoot 'manifest.json'), (ConvertTo-Json -InputObject $manifest -Depth 4), [Text.UTF8Encoding]::new($false))
Write-Output "Created $($manifest.Count) synthetic bilingual fixtures in $fixtureRoot"
