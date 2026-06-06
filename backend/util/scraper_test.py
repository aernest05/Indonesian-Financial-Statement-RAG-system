import yfinance as yf

# Download data for Microsoft (MSFT)
data = yf.download('BBCA.JK')

# View the first few rows of data
print(data.head())