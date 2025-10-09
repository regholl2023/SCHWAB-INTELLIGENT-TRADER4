**📈 Algorithmic Trading Bot (Paper Bot)**

An AI-assisted algorithmic trading bot built with Python, Streamlit, and Alpaca Paper Trading API.
This project simulates SMA/EMA crossover trading strategies, enables paper trading directly from the dashboard, and visualizes live market data fetched via Alpaca or yFinance.

🚀 Features

✅ SMA & EMA Strategy Visualization

Automatically computes Simple and Exponential Moving Averages

Displays buy/sell signal zones on price charts

✅ Multi-Ticker Dashboard

Select up to 6 tickers at a time

View daily or weekly data (configurable)

Charts powered by Streamlit’s interactive plotting

✅ Paper Trading Integration

Fully integrated with Alpaca Paper Broker

Place Market or Limit orders directly from the dashboard

Real-time order confirmations

✅ Account & Portfolio Display

View paper-trading account equity

Track open positions per stock

✅ Dynamic Position Sizing

Automatic position size calculation using % of total equity

Adjustable allocation slider (1–100%)

✅ Trade History

Session-level trade logging

Persistent database logging (optional via quantbot.db)

✅ Data Fallback

If Alpaca API keys are missing, automatically falls back to yFinance for historical price data

🧠 Project Architecture
Algorithmic-Trading-Bot/
│
├── quantbot/
│   ├── __init__.py
│   ├── broker.py        # Handles paper/live trading via Alpaca
│   ├── utils.py         # Fetches OHLC data (Alpaca/yFinance)
│   ├── db.py            # Optional SQLite persistence
│   ├── strategy.py      # Technical indicators and logic helpers
│   └── runner.py        # Command-line bot runner
│
├── streamlit_app.py     # Interactive Streamlit dashboard
├── run_bot.py           # CLI script to run trading loop
├── test_alpaca.py       # Test script to verify Alpaca API connection
├── requirements.txt     # Python dependencies
├── .env.example         # Template for API keys and environment vars
├── quantbot.db          # SQLite database (auto-created if enabled)
└── README.md            # Documentation (this file)

⚙️ Setup Guide
1️⃣ Clone the repository
git clone https://github.com/your-username/Algorithmic-Trading-Bot.git
cd Algorithmic-Trading-Bot

2️⃣ Create and activate virtual environment
python -m venv venv
venv\Scripts\activate  # (Windows)
# or
source venv/bin/activate  # (Mac/Linux)

3️⃣ Install dependencies
pip install -r requirements.txt

4️⃣ Set up .env file

Create a .env file in the root directory based on .env.example:

MODE=ALPACA
ALPACA_KEY=your_alpaca_api_key
ALPACA_SECRET=your_alpaca_secret_key
ALPACA_BASE_URL=https://paper-api.alpaca.markets


To run purely in simulation mode (no external API calls):

MODE=SIM

🧩 Running the Project
🧮 Option 1: Run the CLI bot
python run_bot.py


This will start the continuous trading loop and execute simulated/paper trades automatically.

🖥️ Option 2: Launch the Streamlit Dashboard
streamlit run streamlit_app.py


Then open the provided localhost URL (usually http://localhost:8501
) in your browser.

📊 Streamlit Dashboard Overview
Section	Description
Configuration Panel	Choose tickers, timeframe, SMA/EMA parameters, and position size.
Charts	Live price, SMA, and EMA visualization per ticker.
Trading Controls	Place Buy/Sell market or limit orders directly.
Account Summary	Displays total paper account equity.
Trade History	Shows recent session trades and order results.
🧱 Dependencies
Library	Purpose
streamlit	Dashboard UI framework
alpaca-trade-api	Broker connection for Alpaca paper/live trading
pandas	Data manipulation
yfinance	Fallback price data provider
python-dotenv	Environment variable loading
matplotlib / altair	Chart rendering
sqlite3	Local trade persistence (optional)

Install them via:

pip install streamlit alpaca-trade-api yfinance pandas python-dotenv matplotlib

🧩 Example Workflow

Launch streamlit_app.py

Select a stock (e.g., AAPL)

Choose time frame and indicators (SMA/EMA)

Review signal — if SMA > EMA, bot suggests BUY

Execute trade using market or limit order

Observe updated position and history below chart

💾 Database Integration (Optional)

The bot supports trade persistence via SQLite database (quantbot.db):

Trades are stored using db.persist_trade() when orders execute.

You can use this to compute historical P&L, win ratio, or build analytics dashboards.

🧠 Future Improvements

📊 P&L tracking and historical performance analysis

🔔 Email / Telegram trade alerts

🧮 Risk-based position sizing (stop-loss based)

🌐 WebSocket live price streaming

🔐 Secure authentication for hosted dashboard

🧑‍💻 Contributors

Codeless Technologies
🚀 Empowering no-code and low-code automation with AI integration.

⚠️ Disclaimer

This bot is intended for educational and research purposes only.
Trading and investment involve risk. Use the paper trading mode for experimentation — do not deploy live trading strategies without thorough testing.
