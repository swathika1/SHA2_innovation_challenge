$appJs = "\\wsl.localhost\Ubuntu\home\swathika\IC26\docker\SHA2_innovation_challenge\mobile_frontend\app.js"
$index = "\\wsl.localhost\Ubuntu\home\swathika\IC26\docker\SHA2_innovation_challenge\mobile_frontend\index.html"

(Get-Content $appJs) |
ForEach-Object {
    if ($_ -match "const profileAsset = ") {
        "        const profileAsset = 'assets/elderly-profile-80.svg?v=20260406';"
    } else {
        $_
    }
} | Set-Content $appJs

(Get-Content $index) |
ForEach-Object {
    if ($_ -match 'class="profile-img-large"' -and $_ -match 'alt="Profile"') {
        '                    <img src="assets/elderly-profile-80.svg?v=20260406" alt="Profile" class="profile-img-large" style="border-radius: 14px; box-shadow: 0 8px 20px rgba(0,0,0,0.2); width: 100px; height: 100px; object-fit: cover; border: 3px solid rgba(255,255,255,0.3);">'
    } elseif ($_ -match 'class="profile-img"' -and $_ -match 'alt="Profile"') {
        '                <img src="assets/elderly-profile-80.svg?v=20260406" alt="Profile" class="profile-img">'
    } else {
        $_
    }
} | Set-Content $index

Write-Output "Profile image revert applied."
