#!/bin/bash
# Railway initialization script

echo "🚀 Starting Railway initialization..."
echo "📊 Running auto_init.py..."

python3 auto_init.py || {
    echo "❌ auto_init.py failed with exit code $?"
    exit 1
}

echo "✅ auto_init.py completed successfully"

echo "🚀 Starting bot..."
python3 bot.py
