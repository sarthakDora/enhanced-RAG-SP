"""
Create a test Excel file for upload verification
"""
import pandas as pd
import os

def create_test_excel_file():
    """Create a test Excel file with financial data"""
    print("Creating test Excel file...")
    
    # Create test financial data
    data = {
        'Date': ['2024-Q1', '2024-Q2', '2024-Q3', '2024-Q4'],
        'Revenue': [1000000, 1200000, 1100000, 1300000],
        'Expenses': [800000, 950000, 900000, 1050000],
        'Net_Income': [200000, 250000, 200000, 250000],
        'EBITDA': [300000, 350000, 320000, 380000],
        'Total_Assets': [5000000, 5200000, 5100000, 5400000]
    }
    
    df = pd.DataFrame(data)
    
    # Create in uploads directory
    upload_dir = "C:/Projects/enhanced-RAG-3/backend/uploads"
    os.makedirs(upload_dir, exist_ok=True)
    
    excel_file = os.path.join(upload_dir, "test_financial_data.xlsx")
    
    # Create Excel file with multiple sheets
    with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Financial_Data', index=False)
        
        # Add another sheet with different data
        performance_data = {
            'Portfolio': ['Growth Fund', 'Value Fund', 'Index Fund', 'Bond Fund'],
            'Return_1Y': [12.5, 8.3, 10.2, 4.1],
            'Return_3Y': [15.2, 9.8, 11.5, 3.8],
            'Volatility': [18.5, 14.2, 15.8, 2.5],
            'Sharpe_Ratio': [0.68, 0.58, 0.65, 1.64]
        }
        perf_df = pd.DataFrame(performance_data)
        perf_df.to_excel(writer, sheet_name='Performance_Data', index=False)
    
    print(f"Created test Excel file: {excel_file}")
    print(f"File size: {os.path.getsize(excel_file)} bytes")
    
    return excel_file

if __name__ == "__main__":
    create_test_excel_file()