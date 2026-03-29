# YouTube RAG Chatbot - Windows Setup Script
# Run this in PowerShell: powershell -ExecutionPolicy Bypass -File setup.ps1

Write-Host "🚀 YouTube RAG Chatbot - Backend Setup" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan

# Check Python
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✓ Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Python not found. Please install Python 3.9+" -ForegroundColor Red
    exit 1
}

# Create virtual environment
if (-not (Test-Path "venv")) {
    Write-Host "📦 Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
    Write-Host "✓ Virtual environment created" -ForegroundColor Green
} else {
    Write-Host "✓ Virtual environment already exists" -ForegroundColor Green
}

# Activate virtual environment
Write-Host "✓ Activating virtual environment..." -ForegroundColor Green
& "venv\Scripts\Activate.ps1"

# Install dependencies
Write-Host "📥 Installing dependencies from requirements.txt..." -ForegroundColor Yellow
python -m pip install --upgrade pip
pip install -r requirements.txt
Write-Host "✓ Dependencies installed" -ForegroundColor Green

# Create .env file
if (-not (Test-Path ".env")) {
    Write-Host "🔐 Creating .env file from template..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "✓ Created .env file" -ForegroundColor Green
    Write-Host ""
    Write-Host "⚠️  IMPORTANT: Edit .env and add your Gemini API key:" -ForegroundColor Yellow
    Write-Host "   GEMINI_API_KEY=your_key_here" -ForegroundColor Yellow
    Write-Host ""
} else {
    Write-Host "✓ .env file already exists" -ForegroundColor Green
}

Write-Host ""
Write-Host "✅ Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Edit .env and add your Gemini API key"
Write-Host "2. Run: python app.py"
Write-Host "3. In another terminal, load the Chrome extension"
Write-Host ""
Write-Host "For more help, see SETUP_GUIDE.md" -ForegroundColor Cyan
