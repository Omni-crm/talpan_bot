#!/bin/bash
# Railway initialization script

echo "🚀 Starting Railway initialization..."

# Check if database exists
if [ ! -f "/data/database.db" ]; then
    echo "📊 Database not found, initializing..."
    python3 auto_init.py
else
    echo "✅ Database exists, skipping initialization"
fi

echo "🚀 Starting bot..."
python3 bot.py
