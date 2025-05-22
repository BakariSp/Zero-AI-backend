# Set environment variables for debugging
$env:LOG_LEVEL = "DEBUG"
$env:PYTHONUNBUFFERED = "1"
$env:PYTHONTRACEMALLOC = "1"

# Kill any existing API server (try different process names)
Write-Host "Stopping any existing API server processes..."
try {
    # Try to find uvicorn processes
    $processes = Get-Process -Name uvicorn -ErrorAction SilentlyContinue
    if ($processes) {
        foreach ($process in $processes) {
            Write-Host "Stopping uvicorn process: $($process.Id)"
            Stop-Process -Id $process.Id -Force
        }
    }
    
    # Try to find Python processes running uvicorn
    $processes = Get-Process -Name python* -ErrorAction SilentlyContinue
    foreach ($process in $processes) {
        $processInfo = Get-WmiObject Win32_Process -Filter "ProcessId = $($process.Id)"
        if ($processInfo -and $processInfo.CommandLine -like "*uvicorn*") {
            Write-Host "Stopping Python process running uvicorn: $($process.Id)"
            Stop-Process -Id $process.Id -Force
        }
    }
} catch {
    Write-Host "Error stopping processes: $_"
}

# Add Supabase environment variables for testing
Write-Host "Setting Supabase environment variables..."
Write-Host "IMPORTANT: Replace these placeholder values with your actual Supabase URL and key" -ForegroundColor Yellow

# IMPORTANT: Replace the placeholders below with your actual Supabase values
$env:SUPABASE_URL = "https://ecwdxlkvqiqyjffcovby.supabase.co"  # e.g., "https://xyzabc123.supabase.co"
$env:SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImVjd2R4bGt2cWlxeWpmZmNvdmJ5Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0Nzg0NTI1OSwiZXhwIjoyMDYzNDIxMjU5fQ.jGPnftTyITJUsa9FvelgweOCx-zPYOuUsxkvH_fRwOM"  # Your Supabase anon/public key

# Start the API server with enhanced debugging
Write-Host "Starting API server with enhanced debugging..."
uvicorn main:app --reload --log-level debug 