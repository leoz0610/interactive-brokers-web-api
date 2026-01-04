# Clone the repository
# git clone -b backtest https://github.com/leoz0610/interactive-brokers-web-api.git
cd interactive-brokers-web-api/simulation

# Set up environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run tests
python3 test_basic.py

# Run examples
python3 example_backtest.py
