#!/bin/bash
# Railway initialization script

echo "🚀 Starting Railway initialization..."

# Always ensure database exists and is initialized
echo "📊 Checking database..."
python3 auto_init.py

echo "🚀 Starting bot..."
python3 bot.py
