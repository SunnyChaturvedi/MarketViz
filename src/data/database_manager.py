import sqlite3
import pandas as pd
from typing import Dict, List, Optional

class DatabaseManager:
    def __init__(self):
        self.conn = sqlite3.connect(':memory:')
        self.cursor = self.conn.cursor()
        self._initialize_tables()

    def _initialize_tables(self):
        """Initialize database tables."""
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS stocks (
                ticker TEXT,
                date DATE,
                share_price REAL,
                market_cap REAL,
                effective_shares_outstanding REAL,
                PRIMARY KEY (ticker, date)
            );
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS index_data (
                date DATE,
                index_value REAL,
                composition TEXT,
                PRIMARY KEY (date)
            );
        ''')
        self.conn.commit()

    def insert_stock_data(self, us_stocks: Dict[str, pd.DataFrame]):
        """Insert stock data into the database."""
        for ticker, df in us_stocks.items():
            for index, row in df.iterrows():
                self.cursor.execute('''
                    INSERT OR REPLACE INTO stocks 
                    (ticker, date, share_price, market_cap, effective_shares_outstanding)
                    VALUES (?, ?, ?, ?, ?);
                ''', (ticker, row['Date'], row['Share Price'], row['Market Cap'], 
                     row['Effective Shares Outstanding']))
        self.conn.commit()

    def close(self):
        """Close the database connection."""
        self.conn.close()