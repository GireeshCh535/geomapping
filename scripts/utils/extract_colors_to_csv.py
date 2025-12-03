#!/usr/bin/env python3
"""
Extract color mappings from existing tile generator files and convert to CSV
Usage: python extract_colors_to_csv.py <input_python_file> <output_csv_file>
"""

import re
import sys
import csv
from pathlib import Path


def extract_color_map_from_python(python_file):
    """Extract color mapping dictionary from Python file"""
    with open(python_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find get_color_map method
    pattern = r'def get_color_map\(self\):.*?return\s*{(.*?)\n\s*}'
    match = re.search(pattern, content, re.DOTALL)
    
    if not match:
        print("❌ Could not find get_color_map() method")
        return []
    
    map_content = match.group(1)
    
    # Parse each entry
    entries = []
    entry_pattern = r'"([^"]+)":\s*{([^}]+)}'
    
    for match in re.finditer(entry_pattern, map_content):
        category = match.group(1)
        props_str = match.group(2)
        
        # Skip underscore variations (they're duplicates)
        if '_' in category and category.replace('_', ' ') in [e['category'] for e in entries]:
            continue
        
        entry = {
            'category': category,
            'fill': '',
            'outline': '',
            'pattern': '',
            'pattern_color': ''
        }
        
        # Extract fill
        fill_match = re.search(r"'fill':\s*'([^']*)'", props_str)
        if fill_match:
            entry['fill'] = fill_match.group(1)
        
        # Extract outline
        outline_match = re.search(r"'outline':\s*'([^']*)'", props_str)
        if outline_match:
            entry['outline'] = outline_match.group(1)
        
        # Extract pattern
        pattern_match = re.search(r"'pattern':\s*'([^']*)'", props_str)
        if pattern_match:
            entry['pattern'] = pattern_match.group(1)
        
        # Extract pattern_color
        pattern_color_match = re.search(r"'pattern_color':\s*'([^']*)'", props_str)
        if pattern_color_match:
            entry['pattern_color'] = pattern_color_match.group(1)
        
        entries.append(entry)
    
    return entries


def write_to_csv(entries, output_file):
    """Write entries to CSV file"""
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['category', 'fill_color', 'outline_color', 'pattern', 'pattern_color'])
        writer.writeheader()
        
        for entry in entries:
            writer.writerow({
                'category': entry['category'],
                'fill_color': entry['fill'],
                'outline_color': entry['outline'],
                'pattern': entry['pattern'],
                'pattern_color': entry['pattern_color']
            })
    
    print(f"✅ Wrote {len(entries)} entries to {output_file}")


def main():
    if len(sys.argv) < 3:
        print("Usage: python extract_colors_to_csv.py <input_python_file> <output_csv_file>")
        print("\nExample:")
        print("  python extract_colors_to_csv.py \\")
        print("    scripts/tiles_generation/rajasthan/jaipur_masterplan_tile_generator.py \\")
        print("    data/rajasthan/jaipur/master_plan/legend.csv")
        sys.exit(1)
    
    input_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2])
    
    if not input_file.exists():
        print(f"❌ Input file not found: {input_file}")
        sys.exit(1)
    
    print(f"📖 Reading from: {input_file}")
    entries = extract_color_map_from_python(input_file)
    
    if not entries:
        print("❌ No entries found")
        sys.exit(1)
    
    # Create output directory if needed
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"✍️  Writing to: {output_file}")
    write_to_csv(entries, output_file)
    
    print("\n📊 Preview:")
    print("-" * 80)
    for i, entry in enumerate(entries[:5], 1):
        print(f"{i}. {entry['category']:<40} Fill: {entry['fill']:<10} Pattern: {entry['pattern']}")
    if len(entries) > 5:
        print(f"... and {len(entries) - 5} more")
    print("-" * 80)


if __name__ == '__main__':
    main()

