param(
    [string] $InputFile = "Users.json",
    [string] $ConfigFile = "ImportConfig.json"
)

#$BASE_PATH = "CN=P3KI Managed,DC=l2,DC=dev,DC=p3ki,DC=com"

function Get-ExpirationDate($User) {
    if (($User.AccountExpirationDate -eq $null) -or ($User.AccountExpirationDate -eq "")){
        $ExpirationDate = (Get-Date).AddMonths($CONFIG.DefaultExpiery.Months).AddDays($CONFIG.DefaultExpiery.Days)
    } else {
        $ExpirationDate = (Get-Date $User.AccountExpirationDate)
    }
    return $ExpirationDate
}

function Config-GetManagedGroups() {
    param($Config)

    return $Config.GroupMap.psobject.Properties.Value
}

function Config-GetGroupMapping() {
    param($Config)
    
    $map = @{}
    $Config.GroupMap.psobject.Properties | Foreach { $map[$_.Name] = $_.Value }

    return $map
}

function Config-GetSubPathMapping() {
    param($Config)

    $map = @{}
    $Config.SubPathMap.psobject.properties | Foreach { $map[$_.Name] = $_.Value }

    #Add default mapping
    if ($map["*"] -eq $null ) { $map["*"] = "CN=Users" }

    return $map
}

function Users-Import() {
    param($InputFile)
    return (Get-Content -Raw $InputFile | ConvertFrom-Json)
}


function Create-User() {
    param($User)
	
    $AccountParams = @{
        #AccountPassword       = ConvertTo-SecureString $passCT -AsPlainText -Force;
        Path                  = (Map-Path $User.SubPath);
        AccountExpirationDate = (Get-ExpirationDate $User);
        CannotChangePassword  = $false;
        ChangePasswordAtLogon = $false;
        Name                  = $User.Name;
        DisplayName           = $User.DisplayName;
        SAMAccountName        = $User.UserName;
        Surname               = $User.Surname;
        GivenName             = $User.GivenName;
        EMail                 = $User.Mail;
        Country               = $User.Country;
        City                  = $User.City;
        Company               = $User.Company;
        Department            = $User.Department;
        Enabled               = $false;
    }

    Write-Host "Create User: " ($AccountParams | Format-Table | Out-String)

    $ADUser = New-ADUser -PassThru @AccountParams
	if ($ADUser -ne $null){
		Update-Groups $ADUser.SID $User.Groups
	}
}

function Update-User(){
	param($ADUser, $User)

    $ExpirationDate = Get-ExpirationDate($User)
	$Enabled = $ADUser.Enabled -AND $User.Enabled #Users must be manuelly (re-)enabled.
	
    #Write-Host "Update" $ADUser "->" ($User)
	
    #For Some properties you can only set non-empty values otherwise Set-ADUser will fail.
    #To set to an empty string, you have to use Set-ADUser -Clear
    #Can not update the "Name" Property
    if ($User.DisplayName){Set-ADUser -Identity $ADUser.SID -DisplayName           $User.DisplayName} else {Set-ADUser -Identity $ADUser.SID -Clear "displayName"}
	if ($User.GivenName)  {Set-ADUser -Identity $ADUser.SID -GivenName             $User.GivenName}   else {Set-ADUser -Identity $ADUser.SID -Clear "givenName"}
	if ($User.Surname)    {Set-ADUser -Identity $ADUser.SID -Surname               $User.Surname}     else {Set-ADUser -Identity $ADUser.SID -Clear "sn"} #If you want to set the surname, you need to set the Surname property, if you want to clear it you need to clear the "sn" attribute. Fuck that shit.
    if ($User.Mail)       {Set-ADUser -Identity $ADUser.SID -EMail                 $User.Mail}        else {Set-ADUser -Identity $ADUser.SID -Clear "Mail"} #If you want to set the email address, you need to set the EMail property, if you want to clear it you need to clear the "Mail" attribute. Fuck that shit.
    if ($User.Country)    {Set-ADUser -Identity $ADUser.SID -Country               $User.Country}     else {Set-ADUser -Identity $ADUser.SID -Clear "c"} #If you want to set the country, you need to set the Country property, if you want to clear it you need to clear the "c" attribute. Fuck fuck that shit.
    if ($User.City)       {Set-ADUser -Identity $ADUser.SID -City                  $User.City}        else {Set-ADUser -Identity $ADUser.SID -Clear "l"} #If you want to set the city, you need to set the city property, if you want to clear it you need to clear the "l" attribute. Fuck fuck fuck that shit.
    if ($User.Company)    {Set-ADUser -Identity $ADUser.SID -Company               $User.Company}     else {Set-ADUser -Identity $ADUser.SID -Clear "company"}
    if ($User.Department) {Set-ADUser -Identity $ADUser.SID -Department            $User.Department}  else {Set-ADUser -Identity $ADUser.SID -Clear "department"}
	Set-ADUser -Identity $ADUser.SID -AccountExpirationDate $ExpirationDate #This one could actually be set to null directly. We don't currently use that, but may later.

    Set-ADUser -Identity $ADUser.SID -Enabled $Enabled
	
	Update-Groups $ADUser.SID $User.Groups
}

function Map-Groups(){
    param($Groups)

    $Ret = $Groups | % { $GROUP_MAP[$_]}
    $Ret += $GROUP_MAP["*"]

    return $Ret | Where { $_ }
}

function Update-Groups() {
    param(
        [string] $UserName,
        [string[]] $GroupSet
    )
	
	$GroupSet = (Map-Groups $GroupSet)
	
	
    Get-ADPrincipalGroupMembership $UserName |
        Where { ($MANAGED_GROUPS).Contains($_.Name) -and -not ($GroupSet).Contains($_.Name) } |
        Remove-ADGroupMember -Members $UserName -Confirm:$false
		
    Add-ADPrincipalGroupMembership -Identity $UserName -MemberOf ($GroupSet | Where { ($MANAGED_GROUPS).Contains($_) })
}

function Map-Path(){
    param($SubPath)

    $MappedPath = $SUB_PATH_MAP[$SubPath]

    if (($MappedPath -eq $null) -or ($MappedPath -eq "")) { 
        $MappedPath = $SUB_PATH_MAP["*"]
    }

    #Write-Host "Path Map" $SubPath "->" $MappedPath

    return $MappedPath + "," + $BASE_PATH
}

Write-Host "Config File:" $ConfigFile
Write-Host "Input File" $InputFile

$CONFIG = (Get-Content -Raw $ConfigFile | ConvertFrom-Json)
$BASE_PATH = $CONFIG.BasePath
$MANAGED_GROUPS = Config-GetManagedGroups($CONFIG)
$GROUP_MAP = Config-GetGroupMapping($CONFIG)
$SUB_PATH_MAP = Config-GetSubPathMapping($CONFIG)

$USERS = Users-Import $InputFile

#Write-Host $MANAGED_GROUPS
#Write-Host $GROUP_MAP

foreach ($User in $USERS){
    
    $UserName = $User.UserName
    $ADUser = (Get-ADUser -Filter { SamAccountName -eq $UserName }) 
	Write-Host "===== Username:" $UserName " ( Exists:" ($ADUser -ne $null)") ====="
    #Write-Host ($User | Format-Table | Out-String)


    if ($ADUser -eq $null){
        Create-User $User
    } else {
        Update-User $ADUser $User
    }
}