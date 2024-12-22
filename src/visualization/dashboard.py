import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import numpy as np
from io import BytesIO
import xlsxwriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

class Dashboard:
    def __init__(self, cursor):
        self.cursor = cursor

    def _fetch_index_data(self):
        """Fetch index data from database"""
        self.cursor.execute('''
            SELECT date, index_value, composition
            FROM index_data
            ORDER BY date
        ''')
        data = self.cursor.fetchall()
        return pd.DataFrame(data, columns=['date', 'index_value', 'composition'])

    def _fetch_stock_data(self, ticker):
        """Fetch individual stock data from database"""
        self.cursor.execute('''
            SELECT date, share_price, market_cap
            FROM stocks
            WHERE ticker = ?
            ORDER BY date
        ''', (ticker,))
        data = self.cursor.fetchall()
        return pd.DataFrame(data, columns=['date', 'share_price', 'market_cap'])

    def _plot_index_chart(self, df, composition_changes_dates):
        """Create index chart using plotly"""
        fig = go.Figure()
        
        # Main index line
        fig.add_trace(
            go.Scatter(
                x=df['date'],
                y=df['index_value'],
                mode='lines',
                name='Index Value',
                line=dict(color='#ff0000', width=2)
            )
        )

        if composition_changes_dates:
            change_values = [df[df['date'] == date]['index_value'].iloc[0] for date in composition_changes_dates]
            fig.add_trace(
                go.Scatter(
                    x=composition_changes_dates,
                    y=change_values,
                    mode='markers',
                    name='Composition Change',
                    marker=dict(color='orange', size=10, symbol='star-triangle-down'),
                    hovertemplate='Composition changed on %{x}<extra></extra>'
                )
            )
        
        fig.update_layout(
            title='MarketViz Index Performance',
            xaxis_title='Date',
            yaxis_title='Index Value',
            template='plotly_dark',
            hovermode='x unified',
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01
            ),
            xaxis=dict(
                tickangle=45,
                tickmode='auto',
                nticks=20,
                tickformat='%d/%m'
            )
        )
        return fig

    def _plot_market_cap_distribution(self, latest_composition, k):
        """Create market cap distribution chart with a specified number of stocks"""
        stocks = latest_composition.split(',')
        top_stocks = stocks[:k]  # Top specified number of stocks
        others_stocks = stocks[k:]  # Rest of the stocks
        
        market_caps = []
        others_market_cap = 0
        
        for stock in top_stocks:
            self.cursor.execute('''
                SELECT market_cap
                FROM stocks
                WHERE ticker = ?
                ORDER BY date DESC
                LIMIT 1
            ''', (stock,))
            market_cap = self.cursor.fetchone()[0]
            market_caps.append({'Stock': stock, 'Market Cap': round(market_cap / 1e9, 1)})  # Convert to billion USD and round to 1 decimal place
        
        for stock in others_stocks:
            self.cursor.execute('''
                SELECT market_cap
                FROM stocks
                WHERE ticker = ?
                ORDER BY date DESC
                LIMIT 1
            ''', (stock,))
            market_cap = self.cursor.fetchone()[0]
            others_market_cap += market_cap / 1e9  # Convert to billion USD
        
        market_caps.append({'Stock': 'OTHERS', 'Market Cap': round(others_market_cap, 1)})
        
        df = pd.DataFrame(market_caps)
        fig = px.pie(
            df, 
            values='Market Cap',
            names='Stock',
            title=f'Top {k} Stocks by Market Cap'
        )
        fig.update_layout(
            template='plotly_dark',
            annotations=[
                dict(
                    text="Market Cap in BILLION USD",
                    showarrow=False,
                    x=0.95,
                    y=0.97,
                    xref="paper",
                    yref="paper",
                    font=dict(
                        size=10
                    )
                )
            ]
        )
        return fig

    def _calculate_statistics(self, df):
        """Calculate key statistics for the index"""
        current_value = df['index_value'].iloc[-1]
        daily_change = df['index_value'].iloc[-1] - df['index_value'].iloc[-2]
        daily_return = (daily_change / df['index_value'].iloc[-2]) * 100
        
        return {
            'current_value': current_value,
            'daily_change': daily_change,
            'daily_return': daily_return,
        }

    def _get_composition_changes_dates(self, df):
        """Identify dates when index composition changed"""
        changes = []
        prev_comp = None
        
        date_column = 'Date' if 'Date' in df.columns else 'date'
        comp_column = 'Composition' if 'Composition' in df.columns else 'composition'
        for date, comp in zip(df[date_column], df[comp_column]):
            current_comp = set(comp.split(','))
            
            if prev_comp is not None and current_comp != prev_comp:
                changes.append(date)
            
            prev_comp = current_comp
        return changes
    
    def _get_composition_changes_tickers(self, metrics_df):
        """Get composition changes in tickers for each date in the metrics dataframe"""
        changes = []
        for i in range(1, len(metrics_df)):
            prev_composition = metrics_df['Composition'].iloc[i-1].split(',')
            curr_composition = metrics_df['Composition'].iloc[i].split(',')
            added_tickers = [ticker for ticker in curr_composition if ticker not in prev_composition]
            removed_tickers = [ticker for ticker in prev_composition if ticker not in curr_composition]
            change = '+(' + ', '.join(added_tickers) + ') , -(' + ', '.join(removed_tickers) + ')'
            if change == "+() , -()":
                changes.append("-")
            else:
                changes.append(change)
        # Adjusting the length of changes to match the length of metrics_df
        while len(changes) < len(metrics_df):
            changes.append('-')
        return changes


    def _calculate_summary_metrics(self, df):
        """Calculate additional summary metrics"""
        # Calculate daily returns
        df['daily_return'] = (df['index_value'] - df['index_value'].shift(1)) / df['index_value'].shift(1) * 100
        
        # Calculate cumulative returns
        initial_value = df['index_value'].iloc[0]
        df['cumulative_return'] = ((df['index_value'] - initial_value) / initial_value) * 100
        return df

    def _export_to_excel(self, df):
        """Export data to Excel"""
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            # Performance sheet
            performance_df = df[['Date', 'Price', 'Daily Return (%)', 'Cumulative Return (%)']]
            performance_df.to_excel(writer, sheet_name='Performance', index=False)
            
            # Composition sheet
            composition_df = df[['Date', 'Composition']]
            composition_df.to_excel(writer, sheet_name='Composition', index=False)

            # Composition changes sheet
            changes_dates = df['Date']
            changes_tickers = self._get_composition_changes_tickers(df)
            composition_changes_df = pd.DataFrame({'Date': changes_dates, 'Composition Changes': changes_tickers})
            composition_changes_df.to_excel(writer, sheet_name='Composition Changes', index=False)
            
            # Format sheets
            workbook = writer.book
            for sheet in writer.sheets.values():
                sheet.set_column('A:D', 15)
                
        return output.getvalue()

    def _export_to_pdf(self, df):
        """Export data to PDF"""
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        elements = []

        # Add title
        styles = getSampleStyleSheet()
        elements.append(Paragraph("Index Report", styles['Title']))
        
        # Add performance table
        performance_data = [['Date', 'Index Value', 'Daily Return (%)', 'Cumulative Return (%)']]
        for _, row in df.iterrows():
            performance_data.append([
                row['Date'],
                f"{row['Price']:.2f}",
                f"{row['Daily Return (%)']:.2f}%",
                f"{row['Cumulative Return (%)']:.2f}%",
            ])
        
        t = Table(performance_data)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(t)
        
        doc.build(elements)
        return buffer.getvalue()

    def run(self):
        """Run the dashboard"""
        st.title('📈 MarketViz Index Dashboard')
        

        
        # Fetch and process data
        df = self._fetch_index_data()
        df = self._calculate_summary_metrics(df)
        stats = self._calculate_statistics(df)
        composition_changes_dates = self._get_composition_changes_dates(df)
        



        # Main metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(
                "Current Index Value", 
                f"{stats['current_value']:,.2f}",
                f"{stats['daily_change']:+,.2f} ({(stats['daily_change'] / stats['current_value']) * 100:+,.2f}%)"
            )
        with col2:
            st.metric(
                "Number of Constituents",
                len(df['composition'].iloc[-1].split(','))
            )
        with col3:
            st.metric(
                "Composition Changes (30d)",
                len(composition_changes_dates)
            )

        # Charts
        col_left, col_right = st.columns([2, 1])
        with col_left:
            st.subheader('Index Performance')
            fig = self._plot_index_chart(df, composition_changes_dates)
            st.plotly_chart(fig, use_container_width=True)
        
        with col_right:
            st.subheader('Market Cap Distribution')
            num_stocks = st.number_input("Enter the number of stocks to display:", min_value=1, value=20)
            pie_chart = self._plot_market_cap_distribution(df['composition'].iloc[-1], num_stocks)
            st.plotly_chart(pie_chart, use_container_width=True)
        
        



        col_left, col_right = st.columns([3, 2])  # Adjusted column widths
        with col_left:
            # Date selection and composition view (moved below performance chart)
            st.subheader('Index Composition')
            selected_date = st.date_input(
                "Select date to view composition",
                value=datetime.strptime(df['date'].iloc[-1], '%Y-%m-%d').date()
            )
            selected_date_str = selected_date.strftime('%Y-%m-%d')
        
            # Keep looking back up to 5 days
            current_date = pd.to_datetime(selected_date_str)
            composition_data = None
            days_checked = 0
        
            while composition_data is None or composition_data.empty:
                composition_data = df[df['date'] == current_date.strftime('%Y-%m-%d')]
                if composition_data.empty:
                    current_date -= pd.Timedelta(days=1)
                    days_checked += 1
                    if days_checked >= 5:
                        st.error(f"No data available for {selected_date_str} or the previous 5 trading days")
                        return
        
            actual_date = current_date.strftime('%Y-%m-%d')
            if actual_date != selected_date_str:
                st.warning(f"No data available for {selected_date_str} (Possible Holiday). Showing data for {actual_date} instead.")
            
            # Display composition in table format instead of text
            if composition_data is not None:
                selected_composition = composition_data.iloc[0]['composition'].split(',')
                composition_df = pd.DataFrame(selected_composition, columns=['Stock'])
                st.dataframe(composition_df, height=350, hide_index=True)
        
        with col_right:
            # Composition Changes (removed Count column)
            if composition_changes_dates:
                st.subheader('Composition Change Dates')
                changes_df = pd.DataFrame(composition_changes_dates[::-1], columns=['Date'])
                st.dataframe(changes_df, height=400, hide_index=True) 







        # Summary Metrics
        st.subheader('Summary Metrics')
        metrics_df = df[['date', 'index_value', 'daily_return', 'cumulative_return', 'composition']].tail(30)  # Show last 30 days
        metrics_df.columns = ['Date', 'Price' ,'Daily Return (%)', 'Cumulative Return (%)', 'Composition']
        changes = self._get_composition_changes_tickers(metrics_df)
        metrics_df['Composition Changes'] = changes
        metrics_df = metrics_df[['Date', 'Price', 'Daily Return (%)', 'Cumulative Return (%)', 'Composition Changes', 'Composition']]
        
        metrics_df = metrics_df[::-1]  # Reverse the order of the dataframe
        st.dataframe(metrics_df, hide_index=True)







        # Export options
        st.subheader('Export Data')
        col_left, col_right = st.columns(2)
        
        with col_left:
            if st.button('Export to Excel'):
                excel_data = self._export_to_excel(metrics_df)
                st.download_button(
                    label="Download Excel",
                    data=excel_data,
                    file_name="index_data.xlsx",
                    mime="application/vnd.ms-excel"
                )
        
        with col_right:
            if st.button('Export to PDF'):
                pdf_data = self._export_to_pdf(metrics_df)
                st.download_button(
                    label="Download PDF",
                    data=pdf_data,
                    file_name="index_data.pdf",
                    mime="application/pdf"
                )

        # Footer
        st.markdown('---')
        st.markdown('*Data updates daily. Last update: {}*'.format(
            df['date'].iloc[-1]
        ))