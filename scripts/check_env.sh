#!/usr/bin/env bash

# Check Python, Git, and project directory; display versions; return a nonzero exit code if a required tool is missing

# Exit immediately if a command exits with a non-zero status
set -e

echo "=============================="
echo "    Tempo Environment Check   "
echo "=============================="
echo

# Flag to track if all checks passed
FAILED=0

# 1. Check Python availability and version
if command -v python3 &> /dev/null; then    # silence the command completely
    PYTHON_VERSION=$(python3 --version 2>&1)
    echo "✅ Python is available: $PYTHON_VERSION"
elif command -v python &> /dev/null; then
    PYTHON_VERSION=$(python --version 2>&1)
    echo "✅ Python is available: $PYTHON_VERSION"
else
    echo "❌ Python is not installed or not in your PATH."
    FAILED=1
fi

# 2. Check Git availability and version
if command -v git &> /dev/null; then
    GIT_VERSION=$(git --version)
    echo "✅ Git is installed: $GIT_VERSION"
else
    echo "❌ Git is not installed or not in your PATH."
    FAILED=1
fi

# 3. Verify required directories exist
REQUIRED_DIRS=("app/" "scripts/" "tests/")
echo
echo "Checking required directories..."

for dir in "${REQUIRED_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        echo " 📂 $dir exists"
    else
        echo " ❌ $dir is missing"
        FAILED=1
    fi
done

echo
# 4. Final verification and exit status
if [ $FAILED -eq 0 ]; then
    echo "=============================="
    echo "🎉 Success! All checks passed."
    echo "=============================="
    exit 0
else
    echo "================================="
    echo "🚨 Environment check failed."
    echo "================================="
    exit 1
fi