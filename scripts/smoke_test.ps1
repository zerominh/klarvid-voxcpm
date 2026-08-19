Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$base = "http://127.0.0.1:8000"

Write-Host "GET /health"
curl.exe -s "$base/health"
Write-Host ""

Write-Host "POST /v1/tts"
curl.exe -s -X POST "$base/v1/tts" `
  -H "Content-Type: application/json" `
  -d "{\"text\":\"Xin chào, Klarvid test text to speech.\"}" `
  --output smoke_tts.wav
Write-Host "wrote smoke_tts.wav"

Write-Host "POST /v1/tts/stream"
curl.exe -s -X POST "$base/v1/tts/stream" `
  -H "Content-Type: application/json" `
  -d "{\"text\":\"Đây là bản streaming.\"}" `
  --output smoke_stream.wav
Write-Host "wrote smoke_stream.wav"

$ref = $args[0]
if ($ref) {
    Write-Host "POST /v1/voices $ref"
    $created = curl.exe -s -X POST "$base/v1/voices" `
      -F "name=smoke" `
      -F "prompt_text=Xin chào, đây là mẫu giọng." `
      -F "reference_audio=@$ref"
    Write-Host $created
    $id = ($created | ConvertFrom-Json).id
    if ($id) {
        Write-Host "POST /v1/tts voice_id=$id"
        curl.exe -s -X POST "$base/v1/tts" `
          -H "Content-Type: application/json" `
          -d "{\"text\":\"Đây là giọng đã lưu.\",\"voice_id\":\"$id\"}" `
          --output smoke_voice.wav
        Write-Host "wrote smoke_voice.wav"
    }
    Write-Host "POST /v1/clone $ref"
    curl.exe -s -X POST "$base/v1/clone" `
      -F "text=Đây là giọng nhân bản." `
      -F "reference_audio=@$ref" `
      --output smoke_clone.wav
    Write-Host "wrote smoke_clone.wav"
} else {
    Write-Host "Skip voices/clone (pass a wav path: .\\scripts\\smoke_test.ps1 D:\\path\\speaker.wav)"
}
