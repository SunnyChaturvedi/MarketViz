import yfinance as yf
import pandas as pd
import requests
from constants import NASDAQ_API_URL, YFINANCE_DEFAULT_LOOKBACK_PERIOD
from typing import Dict, Optional

class StockDataFetcher:
    def __init__(self, k):
        pd.set_option('display.width', None)
        pd.set_option('display.colheader_justify', 'center')
        pd.set_option('display.float_format', '{:,.2f}'.format)
        self.instruments_to_fetch_count = k

    def get_historical_market_cap(self, ticker_symbol: str, period: str) -> pd.DataFrame:
        """
        Fetches the historical market capitalization of a given stock ticker, adjusting for stock splits.

        This function retrieves the historical stock data (including adjusted closing prices) for the
        given ticker symbol using the Yahoo Finance API. It also adjusts the number of shares outstanding
        based on stock splits over time and calculates the market capitalization.

        Parameters:
        ----------
        ticker_symbol : str
        The stock ticker symbol for which to retrieve historical data (e.g., 'AAPL', 'MSFT').

        Returns:
        -------
        pandas.DataFrame
            A DataFrame containing the following columns:
            - 'Date': The date of the stock data.
            - 'Close': The adjusted closing price of the stock.
            - 'Market Cap': The market capitalization, calculated as the product of the adjusted
              closing price and the effective number of shares outstanding (adjusted for splits).
            - 'Effective Shares Outstanding': The number of shares outstanding, adjusted for stock splits.

        Raises:
        ------
        ValueError:
            If the shares outstanding data is not available for the ticker symbol.

        Notes:
        -----
        - The data is fetched using the Yahoo Finance API, and the historical data is reversed
          so the most recent data is at the end of the DataFrame.
        - The cumulative stock split factor is calculated by multiplying the previous split factor
          with the current split value.
        - The 'Stock Splits' data from Yahoo Finance is used to adjust for stock splits.
        """
        ticker = yf.Ticker(ticker_symbol)
        historical_data = ticker.history(period=period)
        historical_data = historical_data[::-1]
        historical_data.index = historical_data.index.date

        historical_data = historical_data.reset_index()

        historical_data.rename(columns={'index': 'Date', 'Close': 'Share Price'}, inplace=True)

        shares_outstanding = ticker.info.get("sharesOutstanding")
        
        if not shares_outstanding:
            raise ValueError(f"Shares outstanding data not available for {ticker_symbol}")

        historical_data['Cumulative Split Factor'] = historical_data['Stock Splits'].copy()
        historical_data.loc[ historical_data['Cumulative Split Factor'] == 0, 'Cumulative Split Factor'] = 1
        historical_data['Cumulative Split Factor'] = historical_data['Cumulative Split Factor'].cumprod()

        historical_data['Effective Shares Outstanding'] = shares_outstanding / historical_data['Cumulative Split Factor']
        historical_data['Market Cap'] = historical_data['Share Price'] * historical_data['Effective Shares Outstanding']

        return historical_data[['Date', 'Share Price', 'Market Cap', 'Effective Shares Outstanding']]

    def get_us_stocks_universe(self, period: str = YFINANCE_DEFAULT_LOOKBACK_PERIOD) -> Dict[str, pd.DataFrame]:
        """
        Fetches historical market capitalization data for a universe of US stocks.

        This method retrieves a list of US stock tickers from the Nasdaq API and then
        fetches the historical market capitalization data for each ticker using the
        `get_historical_market_cap` method. The data is returned as a dictionary where
        each key is a stock ticker symbol and the value is a DataFrame containing the
        historical data.

        Parameters:
        ----------
        period : str, optional
            The lookback period for fetching historical data (default is YFINANCE_DEFAULT_LOOKBACK_PERIOD).

        Returns:
        -------
        Dict[str, pd.DataFrame]
            A dictionary where each key is a stock ticker symbol and the value is a DataFrame
            containing the historical market capitalization data for that stock.

        Raises:
        ------
        ConnectionError:
            If there is an error fetching the stock universe from the Nasdaq API.

        Notes:
        -----
        - The method uses the Nasdaq API to fetch a list of stock tickers.
        - The Yahoo Finance API is used to fetch historical data for each ticker.
        - If an error occurs while fetching data for a specific ticker, it is logged and the method
          continues with the next ticker.
        """
        nasdaq_url = f'{NASDAQ_API_URL}?limit={self.instruments_to_fetch_count}'
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'application/json'
        }

        try:
            response = requests.get(nasdaq_url, headers=headers)
            nasdaq_data = response.json()
            nasdaq_tickers = [
                row['symbol'].replace('/', '-') 
                for row in nasdaq_data['data']['table']['rows']
            ]
        except Exception as e:
            raise ConnectionError(f"Error fetching stock universe: {e}")

        universe_data = {}
        for ticker in nasdaq_tickers:
            try:
                data = self.get_historical_market_cap(ticker, period)
                universe_data[ticker] = data
            except Exception as e:
                print(f"Error fetching data for {ticker}: {e}")

        return universe_data
