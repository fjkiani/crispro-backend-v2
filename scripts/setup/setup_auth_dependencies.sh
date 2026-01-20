#!/bin/bash
# Setup script for Auth dependencies
# Installs required Python packages for authentication

echo "🔧 Setting up Auth Dependencies"
echo "================================"
echo ""

# Check if we're in a virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  Warning: Not in a virtual environment"
    echo "   Consider activating your venv first:"
    echo "   source venv/bin/activate"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

cd "$PROJECT_ROOT"

echo "📦 Installing Python dependencies..."
pip install supabase==2.9.2 PyJWT==2.9.0 python-multipart==0.0.12

if [ $? -eq 0 ]; then
    echo "✅ Dependencies installed successfully!"
    echo ""
    echo "📋 Next steps:"
    echo "1. Add SUPABASE_JWT_SECRET to .env file"
    echo "2. Run database schema in Supabase SQL Editor"
    echo "3. Test: bash scripts/test_auth_endpoints.sh"
else
    echo "❌ Failed to install dependencies"
    exit 1
fi








