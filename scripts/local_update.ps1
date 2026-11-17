# 이 PC에서 수시 경쟁률 공개값을 수집해 푸시한다 (Windows 작업 스케줄러가 30분마다 실행).
# 진학어플라이 경쟁률 페이지가 GitHub Actions 서버를 403 으로 막아, 경민대 등은 여기서 갱신한다.
# 작업 폴더와 섞이지 않게 수집 전용 worktree(F:\git\km-intruder-updater)에서 origin/master 를 받아 돌린다.
#
# 설치: git worktree add --detach F:\git\km-intruder-updater origin/master
#       schtasks /Create /TN "km-intruder 경쟁률 수집" /SC MINUTE /MO 30 /TR "powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File F:\git\km-intruder-updater\scripts\local_update.ps1"
# 로그: F:\git\km-intruder-updater.log (최근 2000줄 유지)
$ErrorActionPreference = 'Continue'
$repo = Split-Path -Parent $PSScriptRoot
$log = Join-Path (Split-Path -Parent $repo) 'km-intruder-updater.log'
$env:PYTHONIOENCODING = 'utf-8'
$data = @('admissions-2026/depts/*/ratios*.json', 'admissions-2026/school/susi*.json')

function Log($m) { "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $m" | Out-File -FilePath $log -Append -Encoding utf8 }

Set-Location $repo
Log '== 시작'
# Actions 커밋과 엇갈려 push 가 거절되면 최신을 다시 받아 처음부터 (최대 3번)
for ($try = 1; $try -le 3; $try++) {
    git fetch -q origin 2>&1 | ForEach-Object { Log "fetch: $_" }
    git reset -q --hard origin/master   # 수집 전용 폴더라 로컬 변경은 없다
    $out = & python scripts/update_admissions_ratios.py 2>&1
    $out | Where-Object { "$_" -match '실패|총 지원' } | ForEach-Object { Log "  $_" }
    git diff --quiet -- $data
    if ($LASTEXITCODE -eq 0) { Log '변경 없음'; break }
    git add -- $data
    git commit -q -m 'Update admissions ratios (local)'
    git push -q origin HEAD:master 2>&1 | ForEach-Object { Log "push: $_" }
    if ($LASTEXITCODE -eq 0) { Log "푸시 완료 $(git rev-parse --short HEAD)"; break }
    Log "푸시 실패 ($try/3) - 다시 시도"
}
$lines = Get-Content $log -Encoding utf8
if ($lines.Count -gt 2000) { $lines | Select-Object -Last 2000 | Set-Content $log -Encoding utf8 }
