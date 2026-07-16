$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$ffmpeg = 'C:\Users\animeshs\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg.Shared_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.2-full_build-shared\bin\ffmpeg.exe'
$wav = Join-Path $root 'voiceover.wav'
$mp4 = Join-Path $root 'inteRx_demo.mp4'
$text = @'
Welcome to inteRx, a research and education prototype for exploring potential drug interaction harm.

In this demonstration, we start with a simple question: what happens when a user enters a combination such as warfarin and aspirin?

Codex inspected the original Marimo app and found a hardcoded interaction table with fixed pairwise probabilities. We replaced that demo database with a normalized evidence-file interface. Each row can represent evidence from DrugBank, an FDA label, a PubMed study, or a pharmacovigilance dataset. The file stores the drug pair, harm description, source, evidence identifier, positive and negative observations, weight, and source link.

The model now uses Bayesian aggregation. A Beta prior is updated by weighted evidence to produce a posterior probability for each drug pair, together with a ninety-five percent credible interval. Pairwise posterior samples are then combined with a noisy-OR calculation, so uncertainty flows into the overall result instead of treating fixed point estimates as fact.

Codex helped inspect the existing code, implement the data and Bayesian changes, validate the Python syntax, and prepare this demonstration. GPT-5.6 Luna Light was used as the reasoning assistant for the requested design and narration.

The important limitation is that this is not clinical advice. The application does not invent probabilities. It expects a reviewed, normalized export from authorized data sources, including licensed DrugBank access where required.
'@
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.Rate = 0
$synth.Volume = 100
$synth.SetOutputToWaveFile($wav)
$synth.Speak($text)
$synth.Dispose()

$font = 'C\:/Windows/Fonts/arial.ttf'
$vf = "drawtext=fontfile='$font':text='inteRx':fontcolor=white:fontsize=72:x=90:y=70,drawtext=fontfile='$font':text='Bayesian drug-interaction explorer':fontcolor=0x9bdcff:fontsize=38:x=95:y=165,drawtext=fontfile='$font':text='Evidence  ->  Bayesian posterior  ->  uncertainty-aware result':fontcolor=white:fontsize=34:x=95:y=430,drawtext=fontfile='$font':text='Research and education prototype - not clinical advice':fontcolor=0xffd27d:fontsize=28:x=95:y=930"
& $ffmpeg -y -f lavfi -i "color=c=0x101827:s=1920x1080:r=30" -i $wav -vf $vf -c:v libx264 -pix_fmt yuv420p -c:a aac -b:a 192k -shortest -movflags +faststart $mp4
Write-Output $mp4
