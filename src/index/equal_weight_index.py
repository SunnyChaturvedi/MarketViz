from typing import Dict, List, Optional
import pandas as pd
from constants import INDEX_CONSTITUENTS_COUNT

class Equal_Weight_Index:
    def __init__(self, cursor):
        self.cursor = cursor

    def calculate_index_for_day(self, date: str):
        """
        Calculate and store the equal_weight index for a specific day.

        This method retrieves stock data for the given date, sorts the stocks
        by market capitalization in descending order, and selects the top
        stocks based on the INDEX_CONSTITUENTS_COUNT. It then calculates the
        index value as the average share price of these top stocks and stores
        the result in the 'index_data' table along with the composition of
        the index.

        Parameters:
        date (str): The date for which to calculate the index, in 'YYYY-MM-DD' format.

        Returns:
        None
        """
        self.cursor.execute('''
            SELECT name FROM sqlite_master WHERE type='table' AND name='stocks';
        ''')
        if not self.cursor.fetchone():
            print("Stocks table does not exist")
            return
        
        self.cursor.execute('''
            SELECT ticker, share_price, market_cap
            FROM stocks
            WHERE date = ?
        ''', (date,))
        stock_data = self.cursor.fetchall()

        if not stock_data:
            return

        stock_data_sorted = sorted(stock_data, key=lambda x: x[2], reverse=True)
        top_k_stocks = stock_data_sorted[:INDEX_CONSTITUENTS_COUNT]

        total_price = sum(stock[1] for stock in top_k_stocks)
        index_value = total_price / INDEX_CONSTITUENTS_COUNT
        composition = ",".join(stock[0] for stock in top_k_stocks)

        self.cursor.execute('''
            INSERT OR REPLACE INTO index_data (date, index_value, composition)
            VALUES (?, ?, ?);
        ''', (date, index_value, composition))
        self.cursor.connection.commit()

    def get_index_at_date(self, query_date: str) -> Optional[Dict]:
        """Get index data for a specific date."""
        self.cursor.execute('''
            SELECT date, index_value, composition
            FROM index_data
            WHERE date = ?
        ''', (query_date,))
        result = self.cursor.fetchone()
        
        if result:
            return {
                "date": result[0],
                "index_value": result[1],
                "composition": result[2]
            }
        return None