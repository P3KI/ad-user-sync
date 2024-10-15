
param(
    [string]$TransferGroup = "Transfer",
    [string]$OutputFile = "Users.json"
)

class User {
    [string]$UserName
    [string]$Name
    [boolean]$Enabled
    [string]$GivenName
    [string]$Surname
    $AccountExpirationDate
    [string[]]$Groups

    User([string]$UserName, [string]$Name, [boolean]$Enabled, [string]$GivenName, [string]$Surname, $AccountExpirationDate, [string[]]$Groups) {
        $this.UserName = $UserName
        $this.Name = $Name
        $this.Surname = $Surname
        $this.GivenName = $GivenName
        $this.Enabled = $Enabled
        $this.AccountExpirationDate = $AccountExpirationDate
        $this.Groups = $Groups
    }
}

$Users = (Get-ADGroupMember $TransferGroup)


$Output = @()

foreach ($User in $Users) {
    $Groups = (Get-ADPrincipalGroupMembership $User.SID).SamAccountName
    $ADUser = (Get-ADUser -Properties AccountExpirationDate $User.SID)

    if ($ADUser.AccountExpirationDate -ne $null){
        $ExpirationDate = ($ADUser.AccountExpirationDate | Get-Date -Format "o")
    } else {
        $ExpirationDate = $null
    }

    $UserObj = [User]::new($User.SamAccountName, $User.name, $ADUser.Enabled, $ADUser.GivenName, $ADUser.Surname, $ExpirationDate, $Groups)

    $Output += $UserObj
}

$OutputJson = $Output | ConvertTo-JSON

if (($OutputFile.Length -eq 0) -OR ($OutputFile -eq  "-")){
    Write-Host $OutputJson
} else {
    [void](New-Item -ItemType File -Force $OutputFile)
    Set-Content $OutputFile $OutputJson
}