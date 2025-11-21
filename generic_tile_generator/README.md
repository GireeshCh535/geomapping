# Tile Generation System Context

## Overview
This system is designed to generate high-quality, anti-aliased map tiles from GeoJSON data for multiple city master plans. It was built to scale from a single Noida implementation to 20+ cities.

## Project Evolution & Learnings
This system is the culmination of learnings from previous implementations:
1.  **Amaravati Master Plan**: The initial proof-of-concept. Established the core logic for GeoJSON-to-Tile rendering using `geopandas` and `mercantile`.
2.  **Noida Master Plan**: Refined the rendering quality. Introduced **4x supersampling** (LANCZOS) to fix jagged edges and **buffered clipping** to eliminate tile boundary artifacts (grid lines).
3.  **Generic System**: The current iteration. Decoupled the logic from the data, allowing for a config-driven approach to handle 20+ distinct cities with varying schemas and legends.

## Directory Structure
```
tile_generation_system/
├── generic_tile_generator.py  # Main engine: Generates tiles based on a JSON config
├── create_city_config.py      # Helper tool: Auto-generates JSON config from data folder + CSV
├── configs/                   # Stores city-specific configurations
│   └── noida/
│       ├── noida_config.json
│       └── noida_legend.csv
└── output/                    # Default output directory for generated tiles
```

## Workflow for New Cities

### 1. Prepare Data
*   Create a folder (e.g., `data/Ayodhya`) containing all `.geojson` files.
*   Create a `legend.csv` in that folder with two columns: `Zone` and `Color` (Hex codes).

### 2. Generate Configuration
Run the helper script to map filenames to zones and create the config file.
```powershell
python tile_generation_system/create_city_config.py --name "Ayodhya Master Plan" --data "data/Ayodhya" --legend "data/Ayodhya/legend.csv" --output "tile_generation_system/configs/ayodhya.json" --tiles-out "output/ayodhya"
```
*   *Note: Check the console output for any "WARNING: Could not map file..." messages and adjust the generated JSON if necessary.*

### 3. Generate Tiles
Run the generic generator using the created config.
```powershell
python tile_generation_system/generic_tile_generator.py --config "tile_generation_system/configs/ayodhya.json"
```

## Key Features Implemented
*   **Buffered Clipping**: Tiles are generated with a 10% buffer to prevent artifacts/grid lines on tile boundaries.
*   **Supersampling**: Tiles are rendered at 4x resolution (1024x1024) and downscaled to 256x256 for high-quality anti-aliasing.
*   **Conditional Outlines**: Dark gray outlines are drawn only at Zoom Levels >= 15 to avoid clutter at lower zooms.
*   **Parallel Processing**: Uses `ThreadPoolExecutor` for fast generation.

## Current Status (as of Nov 19, 2025)
*   **Noida**: Fully generated (Zoom 10-18). Grid line artifacts fixed.
*   **System**: Ready for new city data.

## Next Steps
*   User will provide data for additional cities.
*   Test the `create_city_config.py` workflow on a new city.
