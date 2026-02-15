# Fill color script – run commands

Run from **project root**. Use `--dry-run` first to preview.

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py --legend "<LEGEND_PATH>" --data-dir "<DATA_DIR>" [--recursive] [--dry-run]
```

---

## 1. Tirupati Air Funnel Zones

- **Data:** `data/andhra-pradesh/tirupati/air_funnel_zones/Tirupati.geojson`
- **Legend:** created from `tirupati_air_funnel_tiles.py`

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/andhra-pradesh/tirupati/air_funnel_zones/legend.csv" \
  --data-dir "data/andhra-pradesh/tirupati/air_funnel_zones"
```

---

## 2. Visakhapatnam Master Plan

- **Data:** `data/andhra_pradesh/visakhapatnam/master_plan/*`
- **Legend:** existing

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/andhra_pradesh/visakhapatnam/master_plan/legend.csv" \
  --data-dir "data/andhra_pradesh/visakhapatnam/master_plan"
```

---

## 3. Warangal Air Funnel Zones

- **Data:** `data/andhra-pradesh/warangal/air_funnel_zones/Warangal.geojson`
- **Legend:** created from `warangal_air_funnel_tiles.py`

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/andhra-pradesh/warangal/air_funnel_zones/legend.csv" \
  --data-dir "data/andhra-pradesh/warangal/air_funnel_zones"
```

---

## 4. Guwahati Air Funnel Zones

- **Data:** `data/assam/guwahati/air_funnel_zones/Guwahati.geojson`
- **Legend:** created from `guwahati_air_funnel_tiles.py`

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/assam/guwahati/air_funnel_zones/legend.csv" \
  --data-dir "data/assam/guwahati/air_funnel_zones"
```

---

## 5. Patna Air Funnel Zones

- **Data:** `data/bihar/patna/air_funnel_zones/Patna.geojson`
- **Legend:** created from `patna_air_funnel_tiles.py`

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/bihar/patna/air_funnel_zones/legend.csv" \
  --data-dir "data/bihar/patna/air_funnel_zones"
```

---

## 6. Chandigarh Master Plan

- **Data:** `data/punjab/chandigarh/master_plan/*`
- **Legend:** created from `chandigarh_masterplan_tile_generator.py`

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/punjab/chandigarh/master_plan/legend.csv" \
  --data-dir "data/punjab/chandigarh/master_plan"
```

---

## 7. Durg-Bihlai Master Plan

- **Data:** `data/chhatisgarh/durg-bihlai/master_plan/*`
- **Legend:** existing

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/chhatisgarh/durg-bihlai/master_plan/legend.csv" \
  --data-dir "data/chhatisgarh/durg-bihlai/master_plan"
```

---

## 8. Rajnandgaon Master Plan

- **Data:** `data/chhatisgarh/rajnandgaon/master_plan/*`
- **Legend:** existing

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/chhatisgarh/rajnandgaon/master_plan/legend.csv" \
  --data-dir "data/chhatisgarh/rajnandgaon/master_plan"
```

---

## 9. Raigarh Master Plan

- **Data:** `data/chhatisgarh/raigarh/master_plan/*`
- **Legend:** existing

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/chhatisgarh/raigarh/master_plan/legend.csv" \
  --data-dir "data/chhatisgarh/raigarh/master_plan"
```

---

## 10. Jagdalpur Master Plan

- **Data:** `data/chhatisgarh/jagdalpur/master_plan/*`
- **Legend:** `legend.csv` (folder has `legend.csv`; if yours is `lengnd.csv`, rename or use that path)

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/chhatisgarh/jagdalpur/master_plan/legend.csv" \
  --data-dir "data/chhatisgarh/jagdalpur/master_plan"
```

---

## 11. Arang Master Plan

- **Data:** `data/chhatisgarh/arang/master_plan/*`
- **Legend:** existing

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/chhatisgarh/arang/master_plan/legend.csv" \
  --data-dir "data/chhatisgarh/arang/master_plan"
```

---

## 12. Balodabazaar Master Plan

- **Data:** `data/chhatisgarh/balodabazaar/master_plan/*`
- **Legend:** existing

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/chhatisgarh/balodabazaar/master_plan/legend.csv" \
  --data-dir "data/chhatisgarh/balodabazaar/master_plan"
```

---

## 13. Bhatapara Master Plan

- **Data:** `data/chhatisgarh/bhatapara/master_plan/*`
- **Legend:** existing

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/chhatisgarh/bhatapara/master_plan/legend.csv" \
  --data-dir "data/chhatisgarh/bhatapara/master_plan"
```

---

## 14. Mahasamund Master Plan

- **Data:** `data/chhatisgarh/mahasamund/master_plan/*`
- **Legend:** existing

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/chhatisgarh/mahasamund/master_plan/legend.csv" \
  --data-dir "data/chhatisgarh/mahasamund/master_plan"
```

---

## 15. Raigarh Air Funnel Zones

- **Data:** `data/chhatisgarh/raigarh/air_funnel_zones/*`
- **Legend:** created from `raigarh_air_funnel_tiles.py`

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/chhatisgarh/raigarh/air_funnel_zones/legend.csv" \
  --data-dir "data/chhatisgarh/raigarh/air_funnel_zones"
```

---

## 16. New Raipur Air Funnel Zones

- **Data:** `data/chhatisgarh/new-raipur/air_funnel_zones/*`
- **Legend:** created from `raipur_air_funnel_tiles.py`

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/chhatisgarh/new-raipur/air_funnel_zones/legend.csv" \
  --data-dir "data/chhatisgarh/new-raipur/air_funnel_zones"
```

---

## 17. Daman & Diu Air Funnel Zones

- **Data:** `data/dadra-nagar-haveli-daman-diu/daman-and-diu/air_funnel_zones/*`
- **Legend:** create from `scripts/tiles_generation/dadra_nagar_haveli_daman_diu/diu/air_funnel/diu_air_funnel_tiles.py` (`get_color_map`)

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/dadra-nagar-haveli-daman-diu/daman-and-diu/air_funnel_zones/legend.csv" \
  --data-dir "data/dadra-nagar-haveli-daman-diu/daman-and-diu/air_funnel_zones"
```

---

## 18. Delhi IGI Air Funnel Zones

- **Data:** `data/delhi/delhi-ncr/air_funnel_zones/*`
- **Legend:** create from `scripts/tiles_generation/delhi_ncr/delhi_igi/air_funnel/delhi_igi_air_funnel_tiles.py` (`get_color_map`)

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/delhi/delhi-ncr/air_funnel_zones/legend.csv" \
  --data-dir "data/delhi/delhi-ncr/air_funnel_zones"
```

---

## 19. Delhi NCR Master Plan

- **Data:** `data/delhi_ncr/master_plan/*`
- **Legend:** create from `scripts/tiles_generation/delhi_ncr/delhi_masterplan_tile_generator.py` (`get_color_map`)

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/delhi_ncr/master_plan/legend.csv" \
  --data-dir "data/delhi_ncr/master_plan"
```

---

## 20. Faridabad Master Plan

- **Data:** `data/delhi_ncr/faridabad/master_plan/*`
- **Legend:** create from `scripts/tiles_generation/delhi_ncr/faridabad_masterplan_tile_generator.py`

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/delhi_ncr/faridabad/master_plan/legend.csv" \
  --data-dir "data/delhi_ncr/faridabad/master_plan"
```

---

## 21. Greater Noida Master Plan

- **Data:** `data/delhi_ncr/greater_noida/master_plan/*`
- **Legend:** create from `scripts/tiles_generation/delhi_ncr/greater_noida_masterplan_tile_generator.py`

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/delhi_ncr/greater_noida/master_plan/legend.csv" \
  --data-dir "data/delhi_ncr/greater_noida/master_plan"
```

---

## 22. Noida Master Plan

- **Data:** `data/delhi_ncr/noida/master_plan/`
- **Legend:** create from `scripts/tiles_generation/delhi_ncr/noida_masterplan_tile_generator.py`

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/delhi_ncr/noida/master_plan/legend.csv" \
  --data-dir "data/delhi_ncr/noida/master_plan"
```

---

## 23. Gurgaon Master Plan

- **Data:** `data/delhi_ncr/gurgaon/master_plan/*`
- **Legend:** create from `scripts/tiles_generation/delhi_ncr/gurgaon_masterplan_tile_generator.py`

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/delhi_ncr/gurgaon/master_plan/legend.csv" \
  --data-dir "data/delhi_ncr/gurgaon/master_plan"
```

---

## 24. Noida Jewar Air Funnel Zones

- **Data:** `data/delhi-ncr/delhi-ncr/air_funnel_zones/*`
- **Legend:** create from `scripts/tiles_generation/delhi_ncr/noida_jewar/air_funnel/noida_jewar_air_funnel_tiles.py`

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/delhi-ncr/delhi-ncr/air_funnel_zones/legend.csv" \
  --data-dir "data/delhi-ncr/delhi-ncr/air_funnel_zones"
```

---

## 25. Yamuna Expressway Master Plan

- **Data:** `data/delhi_ncr/yamuna_expressway/master_plan/*`
- **Legend:** create from `scripts/tiles_generation/delhi_ncr/yamuna_expressway_masterplan_tile_generator.py`

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/delhi_ncr/yamuna_expressway/master_plan/legend.csv" \
  --data-dir "data/delhi_ncr/yamuna_expressway/master_plan"
```

---

## 26. Ahmedabad–Gandhinagar Air Funnel Zones

- **Data:** `data/gujarat/ahmedabad-gandhinagar/air_funnel_zones/*`
- **Legend:** create from `scripts/tiles_generation/gujarat/ahmedabad/air_funnel/ahmedabad_gandhinagar_air_funnel_tiles.py`

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/gujarat/ahmedabad-gandhinagar/air_funnel_zones/legend.csv" \
  --data-dir "data/gujarat/ahmedabad-gandhinagar/air_funnel_zones"
```

---

## 27. Dholera Air Funnel Zones

- **Data:** `data/gujarat/dholera/air_funnel_zones/*`
- **Legend:** create from `scripts/tiles_generation/gujarat/dohlera/air_funnel/dohlera_air_funnel_tiles.py`

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/gujarat/dholera/air_funnel_zones/legend.csv" \
  --data-dir "data/gujarat/dholera/air_funnel_zones"
```

---

## 28. Heritage Sites – Bengaluru

- **Data:** `data/heritage_sites/bengaluru/*` (multiple GeoJSONs: Bengaluru Fort, Bhoga Nandishwara Temple, Devanahalli Fort, Kolaramma Temple, Someswara Temple, Tippu Sultan’s Palace, etc.)
- **Legend:** each site has its own `*_legend.csv` (e.g. `Bengaluru Fort_legend.csv`). If all use the same category names (e.g. Protected, Prohibited, Regulated), use one legend for the directory; else run per site with the matching legend.

```bash
# Option A: one legend for whole directory (if categories are same)
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/heritage_sites/bengaluru/Bengaluru Fort_legend.csv" \
  --data-dir "data/heritage_sites/bengaluru"

# Option B: per site (if categories differ) – repeat for each site’s .geojson and _legend.csv
```

---

## 29. Heritage Sites – Hyderabad

- **Data:** `data/heritage_sites/hyderabad/*` (charminar.geojson, golconda_fort.geojson, ancient_mound.geojson)
- **Legend:** each site has its own `*_legend.csv` (charminar_legend.csv, golconda_fort_legend.csv, ancient_mound_legend.csv). Use one if categories match; else run per site.

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/heritage_sites/hyderabad/charminar_legend.csv" \
  --data-dir "data/heritage_sites/hyderabad"
```

---

## 30. Karnataka Bengaluru Master Plan

- **Data:** `data/karnataka/bengaluru/master_plan/*`
- **Legend:** create `legend.csv` from `maps/config.py` (lines 105–186): use `name` as category and `color` as fill_color for each entry in `files`.

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/karnataka/bengaluru/master_plan/legend.csv" \
  --data-dir "data/karnataka/bengaluru/master_plan"
```

---

## 31. Karnataka Bengaluru Roads

- **Data:** `data/karnataka/bengaluru/roads/*`
- **Legend:** create from `scripts/tiles_generation/karnataka_bengaluru_roads_tiles.py` (if it has a color map), or use existing legend in data dir.

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/karnataka/bengaluru/roads/legend.csv" \
  --data-dir "data/karnataka/bengaluru/roads"
```

---

## 32. Karnataka Bengaluru Highways

- **Data:** `data/karnataka/bengaluru/highways/*`
- **Legend:** create from `scripts/tiles_generation/karnataka/karnataka_bengaluru_highways_tiles_fixed.py`

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/karnataka/bengaluru/highways/legend.csv" \
  --data-dir "data/karnataka/bengaluru/highways"
```

---

## 33. Karnataka Bengaluru Metro

- **Data:** `data/karnataka/bengaluru/metro/*`
- **Legend:** create from `scripts/tiles_generation/karnataka_bengaluru_metro_tiles.py`

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/karnataka/bengaluru/metro/legend.csv" \
  --data-dir "data/karnataka/bengaluru/metro"
```

---

## 34. Karnataka Bengaluru Air Funnel Zones

- **Data:** `data/karnataka/bengaluru/air_funnel_zones/*`
- **Legend:** create from `scripts/tiles_generation/karnataka_bengaluru_air_funnel_tiles.py`

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/karnataka/bengaluru/air_funnel_zones/legend.csv" \
  --data-dir "data/karnataka/bengaluru/air_funnel_zones"
```

---

## 35. Karnataka Bengaluru STRR

- **Data:** `data/karnataka/bengaluru/strr/*`
- **Legend:** create from `scripts/tiles_generation/karnataka/strr_tile_generator.py`

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/karnataka/bengaluru/strr/legend.csv" \
  --data-dir "data/karnataka/bengaluru/strr"
```

---

## 36. Kerala Kochi Air Funnel Zones

- **Data:** `data/kerala/kochi/air_funnel_zones/*`
- **Legend:** create from `scripts/tiles_generation/kerala/kochi/air_funnel/kochi_air_funnel_tiles.py`

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/kerala/kochi/air_funnel_zones/legend.csv" \
  --data-dir "data/kerala/kochi/air_funnel_zones"
```

---

## 37. Kerala Kozhikode Air Funnel Zones

- **Data:** `data/kerala/kozhikode/air_funnel_zones/*`
- **Legend:** create from `scripts/tiles_generation/kerala/kozhikode/air_funnel/kozhikode_air_funnel_tiles.py`

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/kerala/kozhikode/air_funnel_zones/legend.csv" \
  --data-dir "data/kerala/kozhikode/air_funnel_zones"
```

---

## 38. Maharashtra Mumbai Air Funnel Zones

- **Data:** `data/maharashtra/mumbai/air_funnel_zones/*`
- **Legend:** create from `scripts/tiles_generation/maharashtra/navi_mumbai/air_funnel/navi_mumbai_air_funnel_tiles.py`

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/maharashtra/mumbai/air_funnel_zones/legend.csv" \
  --data-dir "data/maharashtra/mumbai/air_funnel_zones"
```

---

## 39. Maharashtra Nagpur Air Funnel Zones

- **Data:** `data/maharashtra/nagpur/air_funnel_zones/*`
- **Legend:** create from `scripts/tiles_generation/maharashtra/nagpur/air_funnel/nagpur_air_funnel_tiles.py`

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/maharashtra/nagpur/air_funnel_zones/legend.csv" \
  --data-dir "data/maharashtra/nagpur/air_funnel_zones"
```

---

## 40. Odisha Bhubaneshwar Air Funnel Zones

- **Data:** `data/odisha/bhubaneshwar/air_funnel_zones/*`
- **Legend:** create from `scripts/tiles_generation/odisha/bhubaneswar/air_funnel/bhubaneswar_air_funnel_tiles.py`

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/odisha/bhubaneshwar/air_funnel_zones/legend.csv" \
  --data-dir "data/odisha/bhubaneshwar/air_funnel_zones"
```

---

## 41. Odisha Bhubaneshwar Master Plan

- **Data:** `data/odisha/bhubaneshwar/master_plan/*`
- **Legend:** create from `scripts/tiles_generation/odisha/bhubaneshwar_masterplan_tile_generator.py`

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/odisha/bhubaneshwar/master_plan/legend.csv" \
  --data-dir "data/odisha/bhubaneshwar/master_plan"
```

---

## 42. Puducherry Master Plan

- **Data:** `data/puducherry/master_plan/*`
- **Legend:** create from `scripts/tiles_generation/puducherry/puducherry_masterplan_tile_generator.py`

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/puducherry/master_plan/legend.csv" \
  --data-dir "data/puducherry/master_plan"
```

---

## 43. Tamil Nadu Chennai Air Funnel Zones

- **Data:** `data/tamil-nadu/chennai/air_funnel_zones/*`
- **Legend:** create from `scripts/tiles_generation/tamil_nadu/chennai/air_funnel/chennai_air_funnel_tiles.py`

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/tamil-nadu/chennai/air_funnel_zones/legend.csv" \
  --data-dir "data/tamil-nadu/chennai/air_funnel_zones"
```

---

## 44. Uttar Pradesh Ayodhya Air Funnel Zones

- **Data:** `data/uttar-pradesh/ayodhya/air_funnel_zones/*`
- **Legend:** create from `scripts/tiles_generation/uttar_pradesh/ayodhya/air_funnel/ayodhya_air_funnel_tiles.py`

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/uttar-pradesh/ayodhya/air_funnel_zones/legend.csv" \
  --data-dir "data/uttar-pradesh/ayodhya/air_funnel_zones"
```

---

## 45. Uttar Pradesh Lucknow Air Funnel Zones

- **Data:** `data/uttar-pradesh/lucknow/air_funnel_zones/*`
- **Legend:** create from `scripts/tiles_generation/uttar_pradesh/lucknow/air_funnel/lucknow_air_funnel_tiles.py`

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/uttar-pradesh/lucknow/air_funnel_zones/legend.csv" \
  --data-dir "data/uttar-pradesh/lucknow/air_funnel_zones"
```

---

## 46. Telangana Warangal Master Plan

- **Data:** `data/Telangana/warangal/master_plan/*`
- **Legend:** from `scripts/tiles_generation/telangana/warangal_masterplan_tile_generator.py` (`get_color_map()`)

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/Telangana/warangal/master_plan/legend.csv" \
  --data-dir "data/Telangana/warangal/master_plan"
```

---

## 47. Rajasthan Jaipur Air Funnel Zones

- **Data:** `data/rajasthan/jaipur/air_funnel_zones/*`
- **Legend:** from `scripts/tiles_generation/rajasthan/jaipur/air_funnel/jaipur_air_funnel_tiles.py` (`get_color_map()`)

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/rajasthan/jaipur/air_funnel_zones/legend.csv" \
  --data-dir "data/rajasthan/jaipur/air_funnel_zones"
```

---

## 48. Telangana Hyderabad (all layers under `data/Telangana/Hyderabad/*`)

Run fill_color for each layer **before** insertion. Legends and colours are aligned with tile scripts: `hyderabad_air_funnel_tiles.py`, `hyderabad_hmda_boundary_tiles.py`, `hyderabad_metro.py`, `telangana_hyderabad_rrr.py`, `hyd_highways.py`, `hyderabad_ratan_tata_road.py`.

### 48.1 Hyderabad Air Funnel Zones

- **Data:** `data/Telangana/Hyderabad/air_funnel_zones/*`
- **Legend:** `scripts/tiles_generation/telangana/hyderabad_air_funnel_tiles.py` (`get_color_map()`); matches on `Pemissible Height` / `Permissible Height`.

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/Telangana/Hyderabad/air_funnel_zones/legend.csv" \
  --data-dir "data/Telangana/Hyderabad/air_funnel_zones"
```

### 48.2 Hyderabad HMDA Extended Area

- **Data:** `data/Telangana/Hyderabad/hmda_extended_area/*` (e.g. `HMDABoundaryExpansion.geojson`)
- **Legend:** from `hyderabad_hmda_boundary_tiles.py` – category `NEW HMDA BOUNDARY`, fill `#3B3B3B` (match on `LAYER`).

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/Telangana/Hyderabad/hmda_extended_area/legend.csv" \
  --data-dir "data/Telangana/Hyderabad/hmda_extended_area"
```

### 48.3 Hyderabad Metro Lines

- **Data:** `data/Telangana/Hyderabad/metro-lines/*` (e.g. `Hyd_metro_lines_ph_1&2_Final(Updated).geojson`)
- **Legend:** from `hyderabad_metro.py` `color_mapping` (Green/Blue/Red/Purple/Future City, Phase 1/2A/2B). Match on `linecolour` or line name.

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/Telangana/Hyderabad/metro-lines/legend.csv" \
  --data-dir "data/Telangana/Hyderabad/metro-lines"
```

### 48.4 Hyderabad RRR (Regional Ring Road)

- **Data:** `data/Telangana/Hyderabad/rrr/RRR_Final.geojson`
- **Legend:** single colour `#14E098` from `telangana_hyderabad_rrr.py`.

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/Telangana/Hyderabad/rrr/legend.csv" \
  --data-dir "data/Telangana/Hyderabad/rrr"
```

### 48.5 Hyderabad Highways

- **Data:** `data/Telangana/Hyderabad/highways/*` (e.g. `hyd_highways_merged.geojson`)
- **Legend:** single colour `#14E098` from `hyd_highways.py`.

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/Telangana/Hyderabad/highways/legend.csv" \
  --data-dir "data/Telangana/Hyderabad/highways"
```

### 48.6 Hyderabad Ratan Tata Road

- **Data:** `data/Telangana/Hyderabad/ratan-tata-road/*` (e.g. `RatanTataRoad.geojson`)
- **Legend:** single colour `#14e098` from `hyderabad_ratan_tata_road.py`.

```bash
python scripts/utils/geojson_add_fill_color_from_legend.py \
  --legend "data/Telangana/Hyderabad/ratan-tata-road/legend.csv" \
  --data-dir "data/Telangana/Hyderabad/ratan-tata-road"
```

**Run order (Hyderabad):** Run 48.1–48.6 above, then run insertion commands from `air_funnel_insert_commands.sh` (Hyderabad Air Funnel, HMDA Extended Area, and `insert_hyderabad_data` for highways, metro, rrr, ratan-tata-road).

---

## Notes

- **Air funnel zones:** Features are matched using `Pemissible Height`, `Permissible Height`, `Height`, or `Zone` (script already includes these).
- **Jagdalpur:** Path above uses `legend.csv`. If your file is named `lengnd.csv`, use `--legend "data/chhatisgarh/jagdalpur/master_plan/lengnd.csv"` or rename the file to `legend.csv`.
- **“Create from &lt;script&gt;”:** For entries that say “create from &lt;tile_generator&gt;”, add a `legend.csv` in the data dir with columns `category,fill_color,outline_color,pattern,pattern_color`. Copy category names and fill/outline hex from the script’s `get_color_map()` (or equivalent) into the CSV.
- **Heritage (Bengaluru / Hyderabad):** Multiple GeoJSONs and per-site `*_legend.csv` files. Use one legend for the whole directory if all sites share the same category names; otherwise run the script per site with the matching legend.
- Add `--recursive` if GeoJSON files lie in subdirectories of `--data-dir`.
- Add `--dry-run` to see what would be updated without writing files.
- Add `--report-missing` to print category values that had no match (then add those to `legend.csv`).
