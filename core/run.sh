# Clone the repository
# git clone https://github.com/leoz0610/interactive-brokers-web-api.git
# cd interactive-brokers-web-api/core

# Set up environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run tests
python3 backtests/test_basic.py

# Run examples
python3 backtests/example_backtest.py
