#!/usr/bin/env python3
"""
Simple test to examine the Sample_FixedIncome_Attribution_Q2_2025.xlsx file
"""

import pandas as pd
import os
import sys

# Add the backend path to sys.path so we can import the services
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

def examine_file():
    """Examine the structure of the fixed income attribution file"""
    print("Testing Attribution RAG with Real Fixed Income File")
    print("=" * 60)
    
    file_path = r"C:\Projects\enhanced-RAG-3\backend\uploads\Sample_FixedIncome_Attribution_Q2_2025.xlsx"
    
    # Check if file exists
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return
    
    print(f"File found: {os.path.basename(file_path)}")
    
    # First, let's examine the file structure
    print("\n1. Examining file structure...")
    try:
        excel_file = pd.ExcelFile(file_path)
        print(f"   Sheet names: {excel_file.sheet_names}")
        
        # Read each sheet to understand structure
        for sheet_name in excel_file.sheet_names:
            try:
                df = pd.read_excel(file_path, sheet_name=sheet_name)
                print(f"\n   Sheet '{sheet_name}': {df.shape[0]} rows x {df.shape[1]} columns")
                if len(df.columns) > 0:
                    print(f"      Columns: {list(df.columns)}")
                    
                    # Show first few rows if data exists
                    if not df.empty:
                        print(f"      Sample data:")
                        print(df.head().to_string())
                        
            except Exception as e:
                print(f"   Error reading sheet '{sheet_name}': {e}")
                
    except Exception as e:
        print(f"   Error reading Excel file: {e}")
        return

    # Test the parsing logic manually
    print("\n2. Testing column detection logic...")
    
    # Try to find the best sheet for attribution data
    best_sheet = None
    for sheet_name in excel_file.sheet_names:
        try:
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            if not df.empty and len(df.columns) > 3:  # Need multiple columns for attribution
                columns_lower = [str(col).lower() for col in df.columns]
                columns_str = " ".join(columns_lower)
                
                # Check for attribution indicators
                attribution_indicators = [
                    'attribution', 'allocation', 'selection', 'contribution',
                    'active', 'portfolio', 'benchmark', 'return', 'country', 'sector'
                ]
                
                matches = sum(1 for indicator in attribution_indicators if indicator in columns_str)
                print(f"   Sheet '{sheet_name}': {matches} attribution indicators found")
                
                if matches >= 3:  # Good candidate
                    best_sheet = sheet_name
                    break
                    
        except Exception as e:
            continue
    
    if best_sheet:
        print(f"\n3. Analyzing best attribution sheet: '{best_sheet}'")
        df = pd.read_excel(file_path, sheet_name=best_sheet)
        
        columns_lower = [str(col).lower() for col in df.columns]
        columns_str = " ".join(columns_lower)
        
        # Asset class detection
        if any(term in columns_str for term in ["gics", "sector", "industry"]):
            asset_class = "Equity"
            attribution_level = "Sector"
        elif any(term in columns_str for term in ["country", "region", "currency"]):
            asset_class = "Fixed Income"  
            attribution_level = "Country"
        else:
            asset_class = "Unknown"
            attribution_level = "Unknown"
        
        print(f"   Detected Asset Class: {asset_class}")
        print(f"   Detected Attribution Level: {attribution_level}")
        
        # Effect detection
        effects_map = {
            'allocation': ['allocation', 'alloc'],
            'selection': ['selection', 'select', 'security_selection'],
            'fx': ['fx', 'currency', 'foreign_exchange'],
            'carry': ['carry', 'yield'],
            'roll': ['roll', 'rolldown'],
            'price': ['price', 'price_return']
        }
        
        print(f"   Effect detection:")
        for effect_name, patterns in effects_map.items():
            found = False
            for pattern in patterns:
                if any(pattern in col.lower() for col in df.columns):
                    found = True
                    break
            print(f"      {effect_name}: {'Found' if found else 'Not found'}")
        
        # Show sample rows
        print(f"\n   Sample data from '{best_sheet}':")
        print(df.head().to_string())
    
    else:
        print("\n   No suitable attribution sheet found")

if __name__ == "__main__":
    examine_file()