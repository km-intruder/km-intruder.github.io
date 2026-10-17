# 게시판 자동 작성 루틴을 이 PC에서 실행한다 (Windows 작업 스케줄러가 호출).
# 사용: powershell -NoProfile -ExecutionPolicy Bypass -File run-routine.ps1 -Name daily-news
#       (Name: daily-news | weekly-trends)
# 작업 폴더(D:\git\...)를 건드리지 않도록 전용 복제본(%LOCALAPPDATA%\km-routines\repo)에서 실행한다.
param([Parameter(Mandatory = $true)][ValidateSet('daily-news', 'weekly-trends')][string]$Name)

$ErrorActionPreference = 'Continue'
$root = Join-Path $env:LOCALAPPDATA 'km-routines'
$repo = Join-Path $root 'repo'
$logs = Join-Path $root 'logs'
New-Item -ItemType Directory -Force $logs | Out-Null
$log = Join-Path $logs ("{0}-{1}.log" -f $Name, (Get-Date -Format 'yyyy-MM-dd_HHmm'))
function Log($m) { "[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $m | Out-File -FilePath $log -Append -Encoding utf8 }

Log "start $Name"
if (-not (Test-Path (Join-Path $repo '.git'))) {
  Log 'clone repository'
  git clone -q git@github-km-intruder:km-intruder/km-intruder.github.io.git $repo 2>&1 | Out-File -FilePath $log -Append -Encoding utf8
}
Set-Location $repo
# 이전 실행이 남긴 변경을 버리고 원격 최신으로 맞춘다 (전용 복제본이라 안전)
git fetch -q origin 2>&1 | Out-File -FilePath $log -Append -Encoding utf8
git reset -q --hard origin/master 2>&1 | Out-File -FilePath $log -Append -Encoding utf8
git clean -qfd 2>&1 | Out-File -FilePath $log -Append -Encoding utf8

$prompt = "Read scripts/routines/$Name.md and carry out every step exactly as written. Do not ask questions; finish the task and report the result in Korean."
$tools = 'Bash,Read,Write,Edit,Glob,Grep,WebSearch,WebFetch'
& claude -p $prompt --model claude-sonnet-5-5 --allowedTools $tools 2>&1 | Out-File -FilePath $log -Append -Encoding utf8
Log ("claude exit code {0}" -f $LASTEXITCODE)

# 로그는 최근 60개만 남긴다
Get-ChildItem $logs -Filter '*.log' | Sort-Object LastWriteTime -Descending | Select-Object -Skip 60 | Remove-Item -Force -ErrorAction SilentlyContinue
Log 'done'
