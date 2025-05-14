# PowerShell script to run the learning path export

# Get the absolute path to the project root
$RootDir = (Get-Item (Split-Path -Parent $MyInvocation.MyCommand.Path)).Parent.Parent.FullName

# Change to the project root directory
Set-Location -Path $RootDir

# Set up Python path
$env:PYTHONPATH = "$RootDir;$env:PYTHONPATH"

# Default parameters
$ExcludeUsers = "1,13"
$Method = "efficient"
$Format = "both"
$OutputDir = "./output"
$SummaryOnly = $false

# Process command line arguments
foreach ($arg in $args) {
    if ($arg -match "^--exclude-users=(.+)$") {
        $ExcludeUsers = $Matches[1]
    }
    elseif ($arg -match "^--method=(standard|efficient)$") {
        $Method = $Matches[1]
    }
    elseif ($arg -match "^--format=(json|csv|both)$") {
        $Format = $Matches[1]
    }
    elseif ($arg -match "^--output-dir=(.+)$") {
        $OutputDir = $Matches[1]
    }
    elseif ($arg -eq "--summary-only") {
        $SummaryOnly = $true
    }
}

# Build the command
$Cmd = "python -m app.scripts.get_learning_paths --exclude-users=$ExcludeUsers --method=$Method --format=$Format --output-dir=$OutputDir"

if ($SummaryOnly) {
    $Cmd += " --summary-only"
}

# Print the command being executed
Write-Host "Executing: $Cmd"
Write-Host "From directory: $RootDir"
Write-Host "------------------------"

# Run the command
try {
    Invoke-Expression $Cmd
    $ExitCode = $LASTEXITCODE
    
    if ($ExitCode -eq 0) {
        Write-Host "------------------------"
        Write-Host "Export completed successfully." -ForegroundColor Green
        
        # Show output directory if files were exported
        if (-not $SummaryOnly) {
            Write-Host "Output files can be found in: $OutputDir"
            
            # List files in the output directory if it exists
            if (Test-Path -Path $OutputDir) {
                Write-Host "Files generated:"
                Get-ChildItem -Path $OutputDir | Format-Table Name, Length, LastWriteTime
            }
        }
    }
    else {
        Write-Host "------------------------"
        Write-Host "Export failed with exit code $ExitCode." -ForegroundColor Red
    }
}
catch {
    Write-Host "------------------------"
    Write-Host "Error executing command: $_" -ForegroundColor Red
} 