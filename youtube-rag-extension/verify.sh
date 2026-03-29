#!/bin/bash
# Project Verification Script
# Checks that all required files exist and are valid
# Run this to verify everything is set up correctly

echo "🔍 YouTube RAG Chatbot - Project Verification"
echo "=============================================="
echo ""

# Track results
total_checks=0
passed_checks=0

# Function to check file exists
check_file() {
    total_checks=$((total_checks + 1))
    if [ -f "$1" ]; then
        echo "✅ $1"
        passed_checks=$((passed_checks + 1))
    else
        echo "❌ $1 - NOT FOUND"
    fi
}

# Function to check directory exists
check_dir() {
    total_checks=$((total_checks + 1))
    if [ -d "$1" ]; then
        echo "✅ $1/"
        passed_checks=$((passed_checks + 1))
    else
        echo "❌ $1 - NOT FOUND"
    fi
}

echo "📁 Directory Structure"
echo "---------------------"
check_dir "extension"
check_dir "extension/icons"
check_dir "backend"
echo ""

echo "🎨 Chrome Extension Files"
echo "------------------------"
check_file "extension/manifest.json"
check_file "extension/service-worker.js"
check_file "extension/content.js"
check_file "extension/sidepanel.html"
check_file "extension/sidepanel.js"
check_file "extension/sidepanel.css"
check_file "extension/icons/README.txt"
echo ""

echo "🐍 Python Backend Files"
echo "----------------------"
check_file "backend/app.py"
check_file "backend/rag_pipeline.py"
check_file "backend/requirements.txt"
check_file "backend/.env.example"
check_file "backend/setup.sh"
check_file "backend/setup.ps1"
echo ""

echo "📚 Documentation Files"
echo "---------------------"
check_file "INDEX.md"
check_file "START_HERE.md"
check_file "YOU_ARE_READY.md"
check_file "SETUP_GUIDE.md"
check_file "README.md"
check_file "ARCHITECTURE.md"
check_file "PROJECT_SUMMARY.md"
check_file "INTEGRATION_GUIDE.md"
echo ""

echo "🔐 Configuration Files"
echo "---------------------"
if [ -f "backend/.env" ]; then
    echo "✅ backend/.env exists"
    passed_checks=$((passed_checks + 1))
    
    # Check if key is configured
    if grep -q "your_gemini_api_key_here" "backend/.env"; then
        echo "   ⚠️  API key not configured yet"
    elif grep -q "GEMINI_API_KEY=" "backend/.env"; then
        echo "   ✓ API key configured"
    fi
else
    echo "❌ backend/.env - NOT FOUND"
    echo "   ℹ️  Run: cd backend && cp .env.example .env"
fi
total_checks=$((total_checks + 1))
echo ""

echo "📊 Results"
echo "----------"
echo "Passed: $passed_checks / $total_checks checks"
echo ""

if [ $passed_checks -eq $total_checks ]; then
    echo "✅ All files verified!"
    echo ""
    echo "Next steps:"
    echo "1. Edit backend/.env with your Gemini API key"
    echo "2. Run: cd backend && python app.py"
    echo "3. In another terminal: load extension in Chrome"
    echo ""
    exit 0
else
    missing=$((total_checks - passed_checks))
    echo "❌ $missing files missing!"
    echo ""
    echo "Make sure:"
    echo "- You're in the youtube-rag-extension directory"
    echo "- All folders exist (extension/, backend/)"
    echo "- All code files are present"
    echo ""
    exit 1
fi
