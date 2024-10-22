
param(
    [string]$ConfigFile = "ExportConfig.json",
    [string]$OutputFile = ""
)

$CONFIG = (Get-Content -Raw $ConfigFile | ConvertFrom-Json)

$FilterGroupNames = $CONFIG.FilterGroupNames

$SearchSubPaths = $CONFIG.SearchSubPaths
if (($SearchSubPaths -eq $null) -or ($SearchSubPaths.Length -eq 0)) { SearchSubPaths = @("CN=Users") }

$BasePath = $CONFIG.BasePath
if (($BasePath -eq $null) -or ($BasePath -eq "")) { Write-Host('Error: Domain "BasePath" must be set in config'); exit($false) }

if ($OutputFile -eq "") { $OutputFile = $CONFIG.OutputFile }
if ($OutputFile -eq "") { $OutputFile = "Users.json" }



class User {
    [string]$SubPath
    [string]$UserName
    [string]$Name
    [string]$DisplayName
    [boolean]$Enabled
    [string]$GivenName
    [string]$Surname
    [string]$Mail
    [string]$basfSIAMID
    [string]$Country
    [string]$City
    [string]$Company
    [string]$Department
    $AccountExpirationDate
    [string[]]$Groups

    User([string]$SubPath, [string]$UserName, [string]$Name, [string]$DisplayName, [boolean]$Enabled, [string]$GivenName, [string]$Surname, [string]$Mail, [string]$basfSIAMID, [string]$Country, [string]$City, [string]$Company, [string]$Department, $AccountExpirationDate, [string[]]$Groups) {
        $this.SubPath = $SubPath
        $this.UserName = $UserName
        $this.Name = $Name
        $this.DisplayName = $DisplayName
        $this.Surname = $Surname
        $this.GivenName = $GivenName
        $this.Mail = $Mail
        $this.basfSIAMID = $basfSIAMID
        $this.Country = $Country
        $this.City = $City
        $this.Company = $Company
        $this.Department = $Department
        $this.Enabled = $Enabled
        $this.AccountExpirationDate = $AccountExpirationDate
        $this.Groups = $Groups
    }
}


#Collect all users in the specified AD paths
$Users = @()
$SubPathsMap = @{}
foreach ($SearchSubPath in $CONFIG.SearchSubPaths){
    $SearchPath = $SearchSubPath + "," + $BasePath
    $PathUsers = Get-ADUser -SearchBase $SearchPath -Filter '*' # 'objectClass -eq "user"'
    foreach ($User in $PathUsers){
        $Users += $User
        $SubPathsMap[$User.SID] = $SearchSubPath
    }
}



$Output = @()

foreach ($User in $Users) {
    $Groups = (Get-ADPrincipalGroupMembership $User.SID).SamAccountName

    if ($FilterGroupNames -eq $null){
        #No group name filter
        $Include = $true
    } else {
        #Filter my security group name: User must be a member of at least one of them.
        $Include = $false
        foreach ($Filter in $FilterGroupNames){
            if ($Groups.Contains($Filter)){
                $Include = $true
                break
            }
        }
    }
    if ($Include){

        $ADUser = (Get-ADUser -Properties DisplayName,AccountExpirationDate,Mail,Company,Department,Country,City $User.SID) #basfSIAMID

        if ($ADUser.AccountExpirationDate -ne $null){
            $ExpirationDate = ($ADUser.AccountExpirationDate | Get-Date -Format "o")
        } else {
            $ExpirationDate = $null
        }

        $Path = $SubPathsMap[$ADUser.SID]

        $UserObj = [User]::new($Path, $User.SamAccountName, $User.Name, $ADUser.DisplayName, $ADUser.Enabled, $ADUser.GivenName, $ADUser.Surname, $ADUser.Mail, $ADUser.basfSIAMID, $ADUser.Country, $ADUser.City, $ADUser.Company, $ADUser.Department, $ExpirationDate, $Groups)

        $Output += $UserObj
   }
}

$OutputJson = $Output | ConvertTo-JSON

if (($OutputFile.Length -eq 0) -OR ($OutputFile -eq  "-")){
    Write-Host $OutputJson
} else {
    [void](New-Item -ItemType File -Force $OutputFile)
    Set-Content $OutputFile $OutputJson
}