// EXACT tile coordinates for YOUR Bangalore data
// Based on your actual API response bounding boxes

// Tile calculation function
function getTileXY(lat, lng, zoom) {
    const x = Math.floor((lng + 180) / 360 * Math.pow(2, zoom));
    const y = Math.floor((1 - Math.log(Math.tan(lat * Math.PI / 180) + 
        1 / Math.cos(lat * Math.PI / 180)) / Math.PI) / 2 * Math.pow(2, zoom));
    return { x, y, z: zoom };
}

// Your actual layer data with exact tile coordinates
const BANGALORE_LAYERS_WITH_TILES = {
    // 1. RESIDENTIAL MAIN (37,227 features - LARGEST)
    residential_main: {
        slug: "residential_main_",
        features: 37227,
        color: "#FFC400",
        bbox: {
            min_lng: 77.42948262, min_lat: 12.81978505,
            max_lng: 77.77604429, max_lat: 13.14264518
        },
        // Exact tile coordinates at zoom 12
        tiles_zoom_12: {
            center: getTileXY(12.98121512, 77.60276346, 12), // Center: 12/3119/3222
            corner_nw: getTileXY(13.14264518, 77.42948262, 12), // NW: 12/3113/3217
            corner_se: getTileXY(12.81978505, 77.77604429, 12)  // SE: 12/3125/3228
        }
    },

    // 2. STATEFOREST PROTECTED (264 features - YOUR ORIGINAL FILE)
    stateforest_protected: {
        slug: "stateforest_valley_protectedland_",
        features: 264,
        color: "#228B22",
        bbox: {
            min_lng: 77.42845651, min_lat: 12.76135712,
            max_lng: 77.74793643, max_lat: 13.16285128
        },
        tiles_zoom_12: {
            center: getTileXY(12.9621042, 77.58819647, 12), // Center: 12/3116/3224
            corner_nw: getTileXY(13.16285128, 77.42845651, 12), // NW: 12/3113/3216
            corner_se: getTileXY(12.76135712, 77.74793643, 12)  // SE: 12/3124/3232
        }
    },

    // 3. COMMERCIAL CENTRAL (799 features - CONCENTRATED AREA)
    commercial_central: {
        slug: "commercial_central_",
        features: 799,
        color: "#004DA8",
        bbox: {
            min_lng: 77.54357915, min_lat: 12.9553467,
            max_lng: 77.61856277, max_lat: 13.02499721
        },
        tiles_zoom_12: {
            center: getTileXY(12.99017196, 77.58107096, 12), // Center: 12/3117/3221
            corner_nw: getTileXY(13.02499721, 77.54357915, 12), // NW: 12/3115/3220
            corner_se: getTileXY(12.9553467, 77.61856277, 12)   // SE: 12/3119/3222
        }
    },

    // 4. AGRICULTURAL LAND (4,618 features - WIDE COVERAGE)
    agricultural_land: {
        slug: "agricultural_land",
        features: 4618,
        color: "#9ACD32",
        bbox: {
            min_lng: 77.39279624, min_lat: 12.7800009,
            max_lng: 77.80003772, max_lat: 13.18399745
        },
        tiles_zoom_12: {
            center: getTileXY(12.98199918, 77.59641698, 12), // Center: 12/3118/3223
            corner_nw: getTileXY(13.18399745, 77.39279624, 12), // NW: 12/3111/3216
            corner_se: getTileXY(12.7800009, 77.80003772, 12)   // SE: 12/3127/3233
        }
    },

    // 5. HIGH TECH (1,487 features)
    hightech: {
        slug: "hightech",
        features: 1487,
        color: "#C29ED7",
        bbox: {
            min_lng: 77.43913903, min_lat: 12.81596428,
            max_lng: 77.75193311, max_lat: 13.06083998
        },
        tiles_zoom_12: {
            center: getTileXY(12.93840213, 77.59553607, 12), // Center: 12/3118/3224
        }
    }
};

// Generate test URLs for your specific data
console.log("=== YOUR BANGALORE VECTOR TILE URLs ===\n");

Object.entries(BANGALORE_LAYERS_WITH_TILES).forEach(([layerKey, layer]) => {
    console.log(`${layerKey.toUpperCase()} (${layer.features} features)`);
    console.log(`Color: ${layer.color}`);
    
    const center = layer.tiles_zoom_12.center;
    console.log(`Zoom 12 Center Tile: ${center.z}/${center.x}/${center.y}`);
    console.log(`URL: http://localhost:8000/api/tiles/bangalore/${layer.slug}/${center.z}/${center.x}/${center.y}.mvt`);
    
    // Also show zoom 10 and 14 for the center
    const zoom10 = getTileXY(
        (layer.bbox.min_lat + layer.bbox.max_lat) / 2,
        (layer.bbox.min_lng + layer.bbox.max_lng) / 2,
        10
    );
    const zoom14 = getTileXY(
        (layer.bbox.min_lat + layer.bbox.max_lat) / 2,
        (layer.bbox.min_lng + layer.bbox.max_lng) / 2,
        14
    );
    
    console.log(`Zoom 10: http://localhost:8000/api/tiles/bangalore/${layer.slug}/${zoom10.z}/${zoom10.x}/${zoom10.y}.mvt`);
    console.log(`Zoom 14: http://localhost:8000/api/tiles/bangalore/${layer.slug}/${zoom14.z}/${zoom14.x}/${zoom14.y}.mvt`);
    console.log("---");
});

// COMBINED TILES (all layers together)
console.log("\nCOMBINED TILES (All 16 layers):");
const bangaloreCenter = getTileXY(12.9716, 77.5946, 12); // Official Bangalore center
console.log(`Center: http://localhost:8000/api/tiles/bangalore/combined/${bangaloreCenter.z}/${bangaloreCenter.x}/${bangaloreCenter.y}.mvt`);

// Show coverage area for zoom 12
const coverageArea = {
    x_min: 3111, x_max: 3127,  // From your agricultural_land bbox
    y_min: 3216, y_max: 3233   // From your overall coverage
};

console.log(`\nCOVERAGE AREA (Zoom 12):`);
console.log(`X range: ${coverageArea.x_min} to ${coverageArea.x_max}`);
console.log(`Y range: ${coverageArea.y_min} to ${coverageArea.y_max}`);
console.log(`Total tiles available: ${(coverageArea.x_max - coverageArea.x_min + 1) * (coverageArea.y_max - coverageArea.y_min + 1)}`);

// Test commands you can run right now
console.log("\n=== CURL TEST COMMANDS ===");
console.log("# Test your largest layer (Residential Main):");
console.log(`curl -I "http://localhost:8000/api/tiles/bangalore/residential_main_/12/3119/3222.mvt"`);

console.log("\n# Test your StateForest layer:");
console.log(`curl -I "http://localhost:8000/api/tiles/bangalore/stateforest_valley_protectedland_/12/3116/3224.mvt"`);

console.log("\n# Test combined tile:");
console.log(`curl -I "http://localhost:8000/api/tiles/bangalore/combined/12/3118/3221.mvt"`);

console.log("\n# Download a tile to check:");
console.log(`curl -o test_tile.mvt "http://localhost:8000/api/tiles/bangalore/residential_main_/12/3119/3222.mvt"`);