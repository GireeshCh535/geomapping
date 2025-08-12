# maps/management/commands/debug_excel.py
# Command to debug and check Excel file structure

from django.core.management.base import BaseCommand
import pandas as pd
import os

class Command(BaseCommand):
    help = 'Debug Excel file to see actual structure and columns'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default='Untitled spreadsheet.xlsx',
            help='Path to Excel file'
        )
    
    def handle(self, *args, **options):
        excel_file = options['file']
        
        # Try different possible paths
        possible_paths = [
            excel_file,
            f'data/{excel_file}',
            f'/app/{excel_file}',
            f'/app/data/{excel_file}',
            'Untitled spreadsheet.xlsx',
            'data/Untitled spreadsheet.xlsx'
        ]
        
        file_found = None
        for path in possible_paths:
            if os.path.exists(path):
                file_found = path
                break
        
        if not file_found:
            self.stdout.write(self.style.ERROR(f"❌ Excel file not found. Tried:"))
            for path in possible_paths:
                self.stdout.write(f"   - {path}")
            return
        
        self.stdout.write(f"✅ Found Excel file at: {file_found}")
        
        try:
            # Read Excel file - try different approaches
            self.stdout.write("\n📊 Reading Excel file...")
            
            # Method 1: Read all sheets
            excel_data = pd.read_excel(file_found, sheet_name=None)
            
            if isinstance(excel_data, dict):
                self.stdout.write(f"\n📑 Found {len(excel_data)} sheets:")
                for sheet_name in excel_data.keys():
                    self.stdout.write(f"   - {sheet_name}")
                
                # Use first sheet
                first_sheet_name = list(excel_data.keys())[0]
                df = excel_data[first_sheet_name]
                self.stdout.write(f"\n📋 Using sheet: '{first_sheet_name}'")
            else:
                df = excel_data
            
            # Show DataFrame info
            self.stdout.write(f"\n📏 DataFrame shape: {df.shape[0]} rows × {df.shape[1]} columns")
            
            # Show column names
            self.stdout.write("\n📝 Column names found:")
            for i, col in enumerate(df.columns, 1):
                self.stdout.write(f"   {i}. '{col}'")
            
            # Show first few rows
            self.stdout.write("\n👀 First 5 rows preview:")
            pd.set_option('display.max_columns', None)
            pd.set_option('display.width', None)
            pd.set_option('display.max_colwidth', 50)
            
            print(df.head())
            
            # Try to identify the structure
            self.stdout.write("\n🔍 Analyzing structure...")
            
            # Look for city/state columns
            city_columns = []
            state_columns = []
            name_columns = []
            category_columns = []
            
            for col in df.columns:
                col_lower = str(col).lower()
                if 'city' in col_lower:
                    city_columns.append(col)
                if 'state' in col_lower:
                    state_columns.append(col)
                if 'name' in col_lower:
                    name_columns.append(col)
                if 'category' in col_lower or 'categ' in col_lower:
                    category_columns.append(col)
            
            self.stdout.write(f"\n   City-related columns: {city_columns}")
            self.stdout.write(f"   State-related columns: {state_columns}")
            self.stdout.write(f"   Name columns: {name_columns}")
            self.stdout.write(f"   Category columns: {category_columns}")
            
            # Check for specific patterns
            if 'CITY (STATE)' in df.columns:
                self.stdout.write("\n✅ Found 'CITY (STATE)' column")
                # Show unique values
                unique_values = df['CITY (STATE)'].dropna().unique()[:10]
                self.stdout.write("   Sample values:")
                for val in unique_values:
                    self.stdout.write(f"      - {val}")
            
            # Try to extract city and state info from any available columns
            self.stdout.write("\n🏙️ Extracting location information...")
            
            # Method 1: Look for combined city-state column
            for col in df.columns:
                if pd.notna(df[col]).any():
                    sample = df[col].dropna().head(5)
                    # Check if it contains pattern like "City (State)"
                    if sample.astype(str).str.contains(r'\(.*\)').any():
                        self.stdout.write(f"\n   Column '{col}' might contain city-state info:")
                        for val in sample:
                            self.stdout.write(f"      - {val}")
            
            # Save cleaned column names for reference
            self.stdout.write("\n💡 Suggested column mapping:")
            self.stdout.write("   Update the setup_hierarchy_from_excel command with:")
            self.stdout.write(f"   - City column: {city_columns[0] if city_columns else 'Not found'}")
            self.stdout.write(f"   - State column: {state_columns[0] if state_columns else 'Not found'}")
            self.stdout.write(f"   - Name column: {name_columns[0] if name_columns else 'Not found'}")
            self.stdout.write(f"   - Category column: {category_columns[0] if category_columns else 'Not found'}")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error reading Excel: {e}"))