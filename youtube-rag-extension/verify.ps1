# Project Verification Script for Windows PowerShell
# Checks that all required files exist and are valid
# Run this to verify everything is set up correctly

Write-Host "🔍 YouTube RAG Chatbot - Project Verification" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""

# Track results
$total_checks = 0
$passed_checks = 0

# Function to check file exists
function Check-File($path, $description) {
    global:$total_checks += 1
    if (Test-Path $path) {
        Write-Host "✅ $description" -ForegroundColor Green
        global:$passed_checks += 1
    } else {
        Write-Host "❌ $description - NOT FOUND" -ForegroundColor Red
    }
}

# Function to check directory exists
function Check-Dir($path, $description) {
    global:$total_checks += 1
    if (Test-Path $path -PathType Container) {
        Write-Host "✅ $description/" -ForegroundColor Green
        global:$passed_checks += 1
    } else {
        Write-Host "❌ $description - NOT FOUND" -ForegroundColor Red
    }
}

Write-Host "📁 Directory Structure" -ForegroundColor Yellow
Write-Host "---------------------" -ForegroundColor Yellow
Check-Dir "extension" "extension"
Check-Dir "extension\icons" "extension/icons"
Check-Dir "backend" "backend"
Write-Host ""

Write-Host "🎨 Chrome Extension Files" -ForegroundColor Yellow
Write-Host "------------------------" -ForegroundColor Yellow
Check-File "extension\manifest.json" "extension/manifest.json"
Check-File "extension\service-worker.js" "extension/service-worker.js"
Check-File "extension\content.js" "extension/content.js"
Check-File "extension\sidepanel.html" "extension/sidepanel.html"
Check-File "extension\sidepanel.js" "extension/sidepanel.js"
Check-File "extension\sidepanel.css" "extension/sidepanel.css"
Check-File "extension\icons\README.txt" "extension/icons/README.txt"
Write-Host ""

Write-Host "🐍 Python Backend Files" -ForegroundColor Yellow
Write-Host "----------------------" -ForegroundColor Yellow
Check-File "backend\app.py" "backend/app.py"
Check-File "backend\rag_pipeline.py" "backend/rag_pipeline.py"
Check-File "backend\requirements.txt" "backend/requirements.txt"
Check-File "backend\.env.example" "backend/.env.example"
Check-File "backend\setup.ps1" "backend/setup.ps1"
Write-Host ""

Write-Host "📚 Documentation Files" -ForegroundColor Yellow
Write-Host "---------------------" -ForegroundColor Yellow
Check-File "INDEX.md" "INDEX.md"
Check-File "START_HERE.md" "START_HERE.md"
Check-File "YOU_ARE_READY.md" "YOU_ARE_READY.md"
Check-File "SETUP_GUIDE.md" "SETUP_GUIDE.md"
Check-File "README.md" "README.md"
Check-File "ARCHITECTURE.md" "ARCHITECTURE.md"
Check-File "PROJECT_SUMMARY.md" "PROJECT_SUMMARY.md"
Check-File "INTEGRATION_GUIDE.md" "INTEGRATION_GUIDE.md"
Write-Host ""

Write-Host "🔐 Configuration Files" -ForegroundColor Yellow
Write-Host "---------------------" -ForegroundColor Yellow
if (Test-Path "backend\.env") {
    Write-Host "✅ backend/.env exists" -ForegroundColor Green
    $passed_checks += 1
    
    # Check if key is configured
    $content = Get-Content "backend\.env"
    if ($content -match "your_gemini_api_key_here") {
        Write-Host "   ⚠️  API key not configured yet" -ForegroundColor Yellow
    } elseif ($content -match "GEMINI_API_KEY=") {
        Write-Host "   ✓ API key configured" -ForegroundColor Green
    }
} else {
    Write-Host "❌ backend/.env - NOT FOUND" -ForegroundColor Red
    Write-Host "   ℹ️  Run: cd backend && Copy-Item .env.example .env" -ForegroundColor Yellow
}
$total_checks += 1
Write-Host ""

Write-Host "📊 Results" -ForegroundColor Yellow
Write-Host "----------" -ForegroundColor Yellow
Write-Host "Passed: $passed_checks / $total_checks checks"
Write-Host ""

if ($passed_checks -eq $total_checks) {
    Write-Host "✅ All files verified!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "1. Edit backend\.env with your Gemini API key"
    Write-Host "2. Run: cd backend && python app.py"
    Write-Host "3. In another terminal: load extension in Chrome"
    Write-Host ""
} else {
    $missing = $total_checks - $passed_checks
    Write-Host "❌ $missing files missing!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Make sure:" -ForegroundColor Yellow
    Write-Host "- You're in the youtube-rag-extension directory"
    Write-Host "- All folders exist (extension/, backend/)"
    Write-Host "- All code files are present"
    Write-Host ""
}
