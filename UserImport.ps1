param(
    [string] $InputFile = "Users.json",
    [string] $ConfigFile = "ImportConfig.json"
)

$BASE_PATH = "CN=P3KI Managed,DC=l2,DC=dev,DC=p3ki,DC=com"

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

function Users-Import() {
    param($InputFile)
    return (Get-Content -Raw $InputFile | ConvertFrom-Json)
}


function Create-User() {
    param($User)
	
    $AccountParams = @{
        #AccountPassword       = ConvertTo-SecureString $passCT -AsPlainText -Force;
        #Path                  = $BASE_PATH;
        AccountExpirationDate = Get-ExpirationDate($User);
        CannotChangePassword  = $false;
        ChangePasswordAtLogon = $false;
        Name                  = $User.name;
        SAMAccountName        = $User.UserName;
        Surname               = $User.Surname;
        GivenName             = $User.GivenName;
        Enabled               = $false;
    }

    $ADUser = New-ADUser -PassThru @AccountParams
	if ($ADUser -ne $null){
		Update-Groups $ADUser.SID $User.Groups
	}
}

function Update-User(){
	param($ADUser, $User)

    $ExpirationDate = Get-ExpirationDate($User)
	$Enabled = $ADUser.Enabled -AND $User.Enabled #Users must be manuelly (re-)enabled.
	
    Write-Host "Update" $ADUser "->" ($User)
	
    #For Some properties you can only set non-empty values otherwise Set-ADUser will fail.
    #To set to an empty string, you have to use Set-ADUser -Clear
	if ($User.name)      {Set-ADUser -Identity $ADUser.SID -DisplayName           $User.name}      else {Set-ADUser -Identity $ADUser.SID -Clear "DisplayName"}
	if ($User.GivenName) {Set-ADUser -Identity $ADUser.SID -GivenName             $User.GivenName} else {Set-ADUser -Identity $ADUser.SID -Clear "GivenName"}
	if ($User.Surname)   {Set-ADUser -Identity $ADUser.SID -Surname               $User.Surname}   else {Set-ADUser -Identity $ADUser.SID -Clear "sn"} #If you want to set the surname, you need to set the Surname property, if you want to clear it you need to clear the "sn" attribute. Fuck that shit.
	Set-ADUser -Identity $ADUser.SID -AccountExpirationDate $ExpirationDate #This one could actually be set to null directly. We don't currently use that, but may later.
    Set-ADUser -Identity $ADUser.SID -Enabled $Enabled
	
	Update-Groups $ADUser.SID $User.Groups
}

function Map-Groups(){
    param($Groups)

    return $Groups | % { $GROUP_MAP[$_]} | Where { $_ }
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


Write-Host "Config File:" $ConfigFile
Write-Host "Input File" $InputFile

$CONFIG = (Get-Content -Raw $ConfigFile | ConvertFrom-Json)
$MANAGED_GROUPS = Config-GetManagedGroups($CONFIG)
$GROUP_MAP = Config-GetGroupMapping($CONFIG)

$USERS = Users-Import $InputFile

#Write-Host $MANAGED_GROUPS
#Write-Host $GROUP_MAP


foreach ($User in $USERS){
    
    $UserName = $User.UserName
    $ADUser = (Get-ADUser -Filter { SamAccountName -eq $UserName }) 
	Write-Host "===== Username:" $UserName " ( Exists:" ($ADUser -ne $null)") ====="

    if ($ADUser -eq $null){
        Create-User $User
    } else {
        Update-User $ADUser $User
    }
}