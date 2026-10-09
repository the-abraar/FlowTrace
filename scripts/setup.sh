#!/usr/bin/env bash
# setup.sh — One-command FlowTrace development environment setup
# Usage: bash scripts/setup.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
echo "  █████╗ ██╗   ██╗██████╗  █████╗ "
echo " ██╔══██╗██║   ██║██╔══██╗██╔══██╗"
echo " ███████║██║   ██║██████╔╝███████║"
echo " ██╔══██║██║   ██║██╔══██╗██╔══██║"
echo " ██║  ██║╚██████╔╝██║  ██║██║  ██║"
echo " ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝"
echo " BlankFrame Technologies — Project FlowTrace Setup"
echo -e "${NC}"

# ─── Check Python ─────────────────────────────────────────────────────────────
echo -e "${YELLOW}[1/5] Checking Python...${NC}"
if ! command -v python3 &>/dev/null; then
    echo "❌ Python 3 not found. Install Python 3.11+ first."
    exit 1
fi
python3 --version

# ─── Backend setup ────────────────────────────────────────────────────────────
echo -e "${YELLOW}[2/5] Setting up Python backend...${NC}"
cd "$ROOT_DIR/backend"

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "  ✅ Virtual environment created"
fi

source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
echo "  ✅ Python dependencies installed"

if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "  ⚠️  Created .env from template. Edit it with your OPENAI_API_KEY!"
fi

python database/init_db.py
echo "  ✅ Database initialized"

# ─── Dashboard setup ──────────────────────────────────────────────────────────
echo -e "${YELLOW}[3/5] Setting up dashboard...${NC}"
cd "$ROOT_DIR/dashboard"

if ! command -v node &>/dev/null; then
    echo "  ⚠️  Node.js not found. Install Node.js 20+ to run the dashboard."
else
    npm install --silent
    echo "  ✅ Dashboard dependencies installed"
fi

# ─── Print start instructions ─────────────────────────────────────────────────
echo -e "${YELLOW}[4/5] Checking firmware tools...${NC}"
if command -v arduino-cli &>/dev/null; then
    echo "  ✅ arduino-cli found"
    arduino-cli core install esp32:esp32 --quiet 2>/dev/null || true
else
    echo "  ⚠️  arduino-cli not found. Install from: https://arduino.github.io/arduino-cli/"
fi

echo ""
echo -e "${GREEN}✅ Setup complete!${NC}"
echo ""
echo "──────────────────────────────────────────────────"
echo "  TO START FLOWTRACE:"
echo ""
echo "  Terminal 1 (Backend):"
echo "    cd backend && source .venv/bin/activate && python run.py"
echo ""
echo "  Terminal 2 (Dashboard):"
echo "    cd dashboard && npm run dev"
echo ""
echo "  Terminal 3 (Simulator — no hardware needed):"
echo "    cd backend && source .venv/bin/activate"
echo "    python ../scripts/simulate.py --users 5 --duration 600"
echo ""
echo "  Dashboard: http://localhost:5173"
echo "  API docs:  http://localhost:8000/docs"
echo "──────────────────────────────────────────────────"
echo ""
echo -e "${YELLOW}⚠️  Don't forget to set OPENAI_API_KEY in backend/.env${NC}"
