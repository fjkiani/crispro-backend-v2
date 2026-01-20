#!/bin/bash
# Create .env template with auth variables
# Adds auth-related environment variables to .env if they don't exist

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
ENV_FILE="$PROJECT_ROOT/.env"

cd "$PROJECT_ROOT"

echo "📝 Creating .env template for Auth"
echo "=================================="
echo ""

# Check if .env exists
if [ ! -f "$ENV_FILE" ]; then
    echo "⚠️  .env file not found. Creating template..."
    touch "$ENV_FILE"
fi

# Function to add env var if it doesn't exist
add_env_var() {
    local var_name=$1
    local var_value=$2
    
    if grep -q "^${var_name}=" "$ENV_FILE"; then
        echo "✅ $var_name already exists"
    else
        echo "$var_name=$var_value" >> "$ENV_FILE"
        echo "✅ Added $var_name"
    fi
}

echo "Adding auth-related environment variables..."
echo ""

# Add auth variables
add_env_var "SUPABASE_JWT_SECRET" "your-jwt-secret-from-supabase-dashboard"
add_env_var "# Supabase Auth (should already exist)" ""
add_env_var "# SUPABASE_URL" "https://your-project.supabase.co"
add_env_var "# SUPABASE_ANON_KEY" "your-anon-key"
add_env_var "# SUPABASE_KEY" "your-service-role-key"

echo ""
echo "✅ .env template updated!"
echo ""
echo "📋 NEXT STEPS:"
echo "1. Get JWT Secret from Supabase Dashboard → Settings → API"
echo "2. Replace 'your-jwt-secret-from-supabase-dashboard' with actual value"
echo "3. Ensure SUPABASE_URL and SUPABASE_ANON_KEY are set"
echo "4. Run database schema in Supabase SQL Editor"








