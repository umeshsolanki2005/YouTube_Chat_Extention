#!/bin/bash
# Automated setup script for YouTube RAG Chatbot Backend
# Usage: chmod +x setup.sh && ./setup.sh
# Or on Windows PowerShell: powershell -ExecutionPolicy Bypass -File setup.ps1

# This script automates the setup process:
# 1. Creates virtual environment
# 2. Installs dependencies
# 3. Creates .env file
# 4. Verifies setup

set -e  # Exit on error

echo "🚀 YouTube RAG Chatbot - Backend Setup"
echo "======================================"

# Check Python version
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo "❌ Python not found. Please install Python 3.9+"
    exit 1
fi

# Determine Python command
if command -v python3 &> /dev/null; then
    PYTHON=python3
else
    PYTHON=python
fi

echo "✓ Python found: $($PYTHON --version)"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    $PYTHON -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

# Activate virtual environment
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
else
    source venv\\Scripts\\activate  # Windows fallback
fi

echo "✓ Virtual environment activated"

# Install dependencies
echo "📥 Installing dependencies from requirements.txt..."
pip install --upgrade pip
pip install -r requirements.txt
echo "✓ Dependencies installed"

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "🔐 Creating .env file from template..."
    cp .env.example .env
    echo "✓ Created .env file"
    echo ""
    echo "⚠️  IMPORTANT: Edit .env and add your Gemini API key:"
    echo "   GEMINI_API_KEY=your_key_here"
    echo ""
else
    echo "✓ .env file already exists"
fi

# Verify setup
echo ""
echo "🔍 Verifying setup..."

# Check requirements are installed
$PYTHON -c "import fastapi; print('✓ FastAPI installed')" || echo "❌ FastAPI not found"
$PYTHON -c "import langchain; print('✓ LangChain installed')" || echo "❌ LangChain not found"
$PYTHON -c "import faiss; print('✓ FAISS installed')" || echo "❌ FAISS not found"
$PYTHON -c "import google.generativeai; print('✓ Google GenAI installed')" || echo "❌ Google GenAI not found"

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env and add your Gemini API key"
echo "2. Run: python app.py"
echo "3. In another terminal, load the Chrome extension"
echo ""
echo "For more help, see SETUP_GUIDE.md"
