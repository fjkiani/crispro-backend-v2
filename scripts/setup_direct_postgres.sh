#!/bin/bash
# Setup Direct PostgreSQL Connection for Research Intelligence
# Bypasses Supabase PostgREST cache issue

set -e

echo "🔧 Setting up Direct PostgreSQL Connection..."
echo ""

# Check if psycopg2-binary is installed
if ! python3 -c "import psycopg2" 2>/dev/null; then
    echo "📦 Installing psycopg2-binary..."
    pip install psycopg2-binary
    echo "✅ psycopg2-binary installed"
else
    echo "✅ psycopg2-binary already installed"
fi

echo ""
echo "🔍 Checking environment variables..."

# Check for DATABASE_URL
if [ -n "$DATABASE_URL" ]; then
    echo "✅ DATABASE_URL is set"
else
    echo "⚠️  DATABASE_URL not set"
fi

# Check for SUPABASE_URL
if [ -n "$SUPABASE_URL" ]; then
    echo "✅ SUPABASE_URL is set"
else
    echo "⚠️  SUPABASE_URL not set"
fi

# Check for SUPABASE_DB_PASSWORD
if [ -n "$SUPABASE_DB_PASSWORD" ]; then
    echo "✅ SUPABASE_DB_PASSWORD is set"
else
    echo "⚠️  SUPABASE_DB_PASSWORD not set"
    echo ""
    echo "📋 To set SUPABASE_DB_PASSWORD:"
    echo "   1. Go to Supabase Dashboard → Project Settings → Database"
    echo "   2. Copy the database password"
    echo "   3. Add to .env: SUPABASE_DB_PASSWORD=your_password"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "🚀 Next steps:"
echo "   1. Ensure DATABASE_URL or (SUPABASE_URL + SUPABASE_DB_PASSWORD) is set in .env"
echo "   2. Run: python3 tests/test_research_intelligence_api.py"
echo "   3. Verify database persistence works"
