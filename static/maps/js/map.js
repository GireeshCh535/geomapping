
// Configuration from Django template
const API_BASE = window.API_BASE || '/api';
const BANGALORE_CENTER = [12.9716, 77.5946];

// Color schemes (consistent with backend)
const CATEGORY_COLORS = {
    'RESIDENTIAL': '#FFC400',      // Yellow - Residential
    'COMMERCIAL': '#004DA8',       // Blue - Commercial  
    'INDUSTRIAL': '#AA66B2',       // Purple - Industrial
    'HIGH_TECH': '#C29ED7',        // Light Purple - High Tech
    'PUBLIC': '#E60000',           // Red - Public/Semi Public
    'DEFENSE': '#8B4513',          // Brown - Defense
    'PROTECTED': '#228B22',        // Forest Green - State Forest/Protected
    'PARKS_GREEN': '#98E600',      // Bright Green - Parks and Green Spaces
    'WATER_BODIES': '#1E90FF',     // Dodger Blue - Lake/Tank
    'TRANSPORT': '#808080',        // Gray - Road/Rail/Airport Transport
    'UTILITIES': '#FF6347',        // Tomato - Power/Water/Utilities
    'AGRICULTURAL': '#9ACD32',     // Yellow Green - Agricultural Land
    'UNCLASSIFIED': '#D3D3D3',     // Light Gray - Unclassified Use
    'DRAINS': '#4682B4',           // Steel Blue - Drains
    'MIXED_USE': '#FFAA00',        // Mixed Use
    'GOVERNMENT': '#FF0000',       // Government
    'EDUCATION': '#FF0000',        // Education
    'HEALTHCARE': '#FF0000',       // Healthcare
    'CULTURAL': '#FF0000',         // Cultural
    'CEMETERY': '#FFFFFF',         // Cemetery
    'HILLS': '#A87000',           // Hills
    'SPECIAL': '#FFFFFF'           // Special
};

// Global state variables
let map;
let currentLayers = [];
let activeMVTLayers = new Map();
let currentOpacity = 0.9;
let currentCity = null;
let mapInitialized = false;

// Progressive loading state
let progressiveLoadingActive = false;
let currentProgressiveChunk = 0;
let totalExpectedFeatures = 0;
let loadedFeatures = 0;
let progressiveLayerGroup = null;
let preferredChunkSize = 100;

// Search state
let searchMarker = null;
let highlightedFeature = null;
let searchResults = [];

// Vector grid state
let vectorGridAttempts = 0;
let usePNGFallback = false;

/* ==========================================================================
   Application Initialization
   ========================================================================== */
document.addEventListener('DOMContentLoaded', function() {
    initializeApplication();
});

function initializeApplication() {
    if (mapInitialized) return;
    mapInitialized = true;
    
    updateStatus('Initializing progressive map interface...', 'loading');
    
    // Check VectorGrid availability
    setTimeout(() => {
        if (!checkVectorGrid()) {
            loadAlternativeVectorGrid();
        }
    }, 1000);
    
    initializeMap();
    loadCities();
    setupEventListeners();
}

function initializeMap() {
    updateStatus('Initializing map...', 'loading');
    
    // Initialize Leaflet map
    map = L.map('map').setView(BANGALORE_CENTER, 11);

    // Add base tile layer
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 18
    }).addTo(map);

    // Add event listeners
    map.on('moveend', updateMapInfo);
    map.on('zoomend', updateMapInfo);
    map.on('click', enhancedHandleMapClick);

    updateStatus('Map ready - loading cities...', 'success');
    updateMapInfo();
}

function setupEventListeners() {
    // City selection change
    document.getElementById('citySelect').addEventListener('change', function() {
        const citySlug = this.value;
        if (citySlug) {
            loadCityLayers(citySlug);
        } else {
            clearLayers();
        }
    });

    // Category filter change
    document.getElementById('categorySelect').addEventListener('change', function() {
        filterLayersByCategory(this.value);
    });

    // Opacity control
    const opacitySlider = document.getElementById('opacity-slider');
    const opacityValue = document.getElementById('opacity-value');
    
    opacitySlider.addEventListener('input', function() {
        currentOpacity = parseFloat(this.value);
        opacityValue.textContent = currentOpacity;
        
        // Update all active layers
        activeMVTLayers.forEach(layer => {
            if (layer.setOpacity) {
                layer.setOpacity(currentOpacity);
            } else if (layer.setStyle) {
                layer.setStyle({ 
                    opacity: currentOpacity, 
                    fillOpacity: currentOpacity * 0.8 
                });
            }
        });
    });
}

/* ==========================================================================
   VectorGrid Loading and Fallback
   ========================================================================== */
function checkVectorGrid() {
    if (typeof L !== 'undefined' && L.vectorGrid && L.vectorGrid.protobuf) {
        console.log('✅ VectorGrid loaded successfully');
        return true;
    }
    return false;
}

function loadAlternativeVectorGrid() {
    if (vectorGridAttempts >= 2) {
        console.log('🔄 VectorGrid failed to load, using PNG fallback');
        usePNGFallback = true;
        return;
    }
    
    vectorGridAttempts++;
    console.log(`⚠️ VectorGrid not loaded, trying alternative CDN (attempt ${vectorGridAttempts})`);
    
    const script = document.createElement('script');
    script.src = vectorGridAttempts === 1 
        ? 'https://cdn.jsdelivr.net/npm/leaflet-vectorgrid@1.3.0/dist/Leaflet.VectorGrid.bundled.min.js'
        : 'https://cdnjs.cloudflare.com/ajax/libs/leaflet-vectorgrid/1.3.0/Leaflet.VectorGrid.bundled.min.js';
        
    script.onload = function() {
        if (checkVectorGrid()) {
            console.log('✅ Alternative VectorGrid CDN loaded successfully');
        } else {
            setTimeout(loadAlternativeVectorGrid, 1000);
        }
    };
    
    script.onerror = function() {
        console.warn('❌ Alternative VectorGrid CDN failed');
        setTimeout(loadAlternativeVectorGrid, 1000);
    };
    
    document.head.appendChild(script);
}

/* ==========================================================================
   City and Layer Management
   ========================================================================== */
async function loadCities() {
    try {
        updateStatus('Loading cities...', 'loading');
        
        const response = await fetch(`${API_BASE}/cities/`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        console.log(`✅ Cities loaded:`, data.results);

        const citySelect = document.getElementById('citySelect');
        citySelect.innerHTML = '<option value="">Choose a city...</option>';

        data.results.forEach(city => {
            const option = document.createElement('option');
            option.value = city.slug;
            option.textContent = `${city.name} (${city.total_features.toLocaleString()} features)`;
            citySelect.appendChild(option);
        });

        // Auto-select Bangalore
        setTimeout(() => {
            citySelect.value = 'bangalore';
            citySelect.dispatchEvent(new Event('change'));
        }, 1000);

        updateStatus('Cities loaded', 'success');
        
    } catch (error) {
        console.error('Error loading cities:', error);
        updateStatus(`Error loading cities: ${error.message}`, 'error');
    }
}

async function loadCityLayers(citySlug) {
    try {
        showLoadingOverlay(true);
        updateStatus(`Analyzing ${citySlug} dataset...`, 'loading');
        currentCity = citySlug;

        // Get dataset info first
        const layersResponse = await fetch(`${API_BASE}/cities/${citySlug}/layers/`);
        if (!layersResponse.ok) {
            throw new Error(`HTTP ${layersResponse.status}: ${layersResponse.statusText}`);
        }
        
        const layersData = await layersResponse.json();
        const totalFeatures = layersData.layers.reduce((sum, layer) => sum + (layer.feature_count || 0), 0);
        
        console.log(`📊 ${citySlug} has ${totalFeatures} total features`);
        
        // 🚀 OPTIMIZED LOADING STRATEGY
        if (totalFeatures > 100000) {
            // Large datasets (100k+) - Use vector tiles for instant loading
            console.log(`🗺️ Using VECTOR TILES for large dataset (${totalFeatures} features)`);
            document.getElementById('loadingMode').textContent = 'Vector Tiles';
            await loadCityWithTiles(citySlug, layersData);
            
        } else if (totalFeatures > 5000) {
            // Medium datasets (5k-100k) - Use optimized progressive loading
            console.log(`🚀 Using OPTIMIZED PROGRESSIVE for medium dataset (${totalFeatures} features)`);
            document.getElementById('loadingMode').textContent = 'Progressive+';
            await loadCityProgressiveOptimized(citySlug, Math.min(2000, totalFeatures / 10));
            
        } else {
            // Small datasets (<5k) - Load everything at once
            console.log(`📦 Using COMPLETE loading for small dataset (${totalFeatures} features)`);
            document.getElementById('loadingMode').textContent = 'Complete';
            await loadCityComplete(citySlug);
        }
        
    } catch (error) {
        console.error('Error loading city:', error);
        updateStatus(`Error loading ${citySlug}: ${error.message}`, 'error');
        showLoadingOverlay(false);
    }
}

async function loadCityWithTiles(citySlug, layersData) {
    try {
        updateStatus(`Loading ${citySlug} with vector tiles...`, 'loading');
        
        // Clear existing layers
        clearAllLayers();
        
        // Force use of the complete endpoint which should return tile strategy
        const completeResponse = await fetch(`${API_BASE}/cities/${citySlug}/complete/?force_tiles=true`);
        if (!completeResponse.ok) {
            throw new Error(`HTTP ${completeResponse.status}: ${completeResponse.statusText}`);
        }
        
        const tileData = await completeResponse.json();
        
        if (tileData.strategy === 'tile_based' || tileData.combined_tile_url) {
            await loadTileBased(tileData);
        } else {
            // Fallback: Create tile-based loading manually
            await loadTileBasedFallback(citySlug, layersData);
        }

        // Setup UI
        renderLayersList(layersData.layers.map(layer => ({
            slug: layer.slug,
            name: layer.name,
            category_name: layer.category_name,
            feature_count: layer.feature_count,
            style: { fill_color: getLayerColorFromCategory(layer.category_name) }
        })));

        // Fit to bounds
        const bounds = calculateBoundsFromLayers(layersData.layers);
        if (bounds) {
            map.fitBounds([
                [bounds.min_lat, bounds.min_lng],
                [bounds.max_lat, bounds.max_lng]
            ], { padding: [50, 50] });
        }

        updateStatus(`✅ ${citySlug} loaded instantly with vector tiles!`, 'success');
        showLoadingOverlay(false);
        
    } catch (error) {
        console.error('Tile loading failed:', error);
        updateStatus(`Tile loading failed: ${error.message}`, 'error');
        // Fallback to optimized progressive
        await loadCityProgressiveOptimized(citySlug, 5000);
    }
}



async function loadCityProgressiveOptimized(citySlug, chunkSize = 5000) {
    try {
        showLoadingOverlay(true);
        updateProgressiveOverlay(true);
        updateStatus(`Fast progressive loading for ${citySlug}...`, 'loading');
        
        // Clear existing layers
        clearAllLayers();
        
        // Initialize progressive layer group
        progressiveLayerGroup = L.layerGroup().addTo(map);
        
        // Reset counters
        currentProgressiveChunk = 0;
        loadedFeatures = 0;
        totalExpectedFeatures = 0;
        progressiveLoadingActive = true;
        
        // Show progressive status panel
        document.getElementById('progressiveStatus').style.display = 'block';
        
        // 🔥 PARALLEL LOADING: Load multiple chunks simultaneously
        const parallelChunks = 3; // Load 3 chunks at once
        const promises = [];
        
        // Start first chunk to get metadata
        const firstChunk = await loadNextProgressiveChunk(citySlug, chunkSize);
        if (!firstChunk) throw new Error('Failed to load first chunk');
        
        totalExpectedFeatures = firstChunk.metadata.total_available_features;
        
        // Set up map bounds
        if (firstChunk.metadata.bounds) {
            const bounds = firstChunk.metadata.bounds;
            map.fitBounds([
                [bounds.min_lat, bounds.min_lng],
                [bounds.max_lat, bounds.max_lng]
            ], { padding: [50, 50] });
        }
        
        // Update UI with layer info
        if (firstChunk.metadata.layers) {
            renderLayersList(firstChunk.metadata.layers.map(layer => ({
                slug: layer.slug,
                name: layer.name,
                category_name: 'Progressive Loading',
                feature_count: layer.total_features,
                style: { fill_color: layer.color }
            })));
            markAllLayersAsLoading();
        }
        
        // 🚀 PARALLEL CHUNK LOADING
        const totalChunks = Math.ceil(totalExpectedFeatures / chunkSize);
        const batchSize = 5; // Process 5 chunks per batch
        
        for (let batchStart = 1; batchStart < totalChunks; batchStart += batchSize) {
            const batchPromises = [];
            
            for (let i = 0; i < batchSize && (batchStart + i) < totalChunks; i++) {
                const chunkIndex = batchStart + i;
                batchPromises.push(loadChunkOptimized(citySlug, chunkSize, chunkIndex));
            }
            
            // Wait for this batch to complete
            await Promise.allSettled(batchPromises);
            
            // Small delay between batches to prevent overwhelming
            await new Promise(resolve => setTimeout(resolve, 10));
            
            if (!progressiveLoadingActive) break;
        }
        
        // Mark completion
        markAllLayersAsLoaded();
        document.getElementById('progressiveStatus').style.display = 'none';
        updateStatus(`✅ Fast progressive loading completed: ${loadedFeatures} features loaded`, 'success');
        showLoadingOverlay(false);
        
    } catch (error) {
        console.error('Optimized progressive loading failed:', error);
        updateStatus(`Progressive loading failed: ${error.message}`, 'error');
        showLoadingOverlay(false);
        progressiveLoadingActive = false;
        document.getElementById('progressiveStatus').style.display = 'none';
    }
}

async function loadChunkOptimized(citySlug, chunkSize, chunkIndex) {
    try {
        const url = `${API_BASE}/cities/${citySlug}/progressive/?chunk=${chunkIndex}&chunk_size=${chunkSize}`;
        
        const response = await fetch(url);
        if (!response.ok) return null;
        
        const chunkData = await response.json();
        
        // Add features to map efficiently
        if (chunkData.features && chunkData.features.length > 0) {
            addChunkToMapOptimized(chunkData);
            loadedFeatures += chunkData.features.length;
            
            // Update progress less frequently
            if (chunkIndex % 3 === 0) {
                updateProgressiveStatus(chunkData.chunk_info);
            }
        }
        
        return chunkData;
        
    } catch (error) {
        console.error(`Error loading chunk ${chunkIndex}:`, error);
        return null;
    }
}

function addChunkToMapOptimized(chunkData) {
    // Create layer with simplified style function for performance
    const chunkLayer = L.geoJSON(chunkData, {
        style: function(feature) {
            const color = feature.properties.color || '#666666';
            return {
                color: color,
                fillColor: color,
                fillOpacity: 0.6,
                opacity: 0.8,
                weight: 1
            };
        },
        onEachFeature: function(feature, layer) {
            // Only add click handler, skip hover for performance
            layer.on('click', function(e) {
                showEnhancedFeaturePopup(feature.properties, e.latlng);
            });
        },
        // Add renderer optimization
        renderer: L.svg({ padding: 0.1 })
    });
    
    progressiveLayerGroup.addLayer(chunkLayer);
}

async function loadTileBasedFallback(citySlug, layersData) {
    console.log(`🗺️ Creating tile-based loading for ${citySlug}`);
    
    // Use combined tile URL
    const combinedTileUrl = `${window.location.origin}${API_BASE}/tiles/${citySlug}/combined/{z}/{x}/{y}`;
    
    if (!usePNGFallback && typeof L !== 'undefined' && L.vectorGrid && L.vectorGrid.protobuf) {
        // MVT tiles
        const mvtUrl = combinedTileUrl + '.mvt';
        const combinedLayer = L.vectorGrid.protobuf(mvtUrl, {
            rendererFactory: L.svg.tile,
            vectorTileLayerStyles: createCombinedStylesFromLayers(layersData.layers),
            interactive: true,
            getFeatureId: function(feature) {
                return feature.properties.id;
            }
        });
        
        combinedLayer.addTo(map);
        activeMVTLayers.set('combined_tiles', combinedLayer);
        
        // Add click handler
        combinedLayer.on('click', function(e) {
            if (e.layer && e.layer.properties) {
                showEnhancedFeaturePopup(e.layer.properties, e.latlng);
            }
        });
        
    } else {
        // PNG tiles fallback
        const pngUrl = combinedTileUrl + '.png';
        const pngLayer = L.tileLayer(pngUrl, { 
            opacity: 0.8,
            maxZoom: 16
        });
        pngLayer.addTo(map);
        activeMVTLayers.set('combined_png', pngLayer);
    }
    
    document.getElementById('tileType').textContent = 'COMBINED-TILES';
}

// Utility functions
function createCombinedStylesFromLayers(layers) {
    const styles = {};
    layers.forEach(layer => {
        const color = getLayerColorFromCategory(layer.category_name);
        styles[layer.slug] = {
            color: color,
            fillColor: color,
            fillOpacity: 0.7,
            opacity: 0.9,
            weight: 1
        };
    });
    return styles;
}

function getLayerColorFromCategory(categoryName) {
    const categoryKey = categoryName?.toUpperCase().replace(/\s+/g, '_');
    return CATEGORY_COLORS[categoryKey] || '#666666';
}

function calculateBoundsFromLayers(layers) {
    // Calculate bounds from layer data if available
    const bounds = {
        min_lng: Infinity,
        min_lat: Infinity,
        max_lng: -Infinity,
        max_lat: -Infinity
    };
    
    let hasBounds = false;
    layers.forEach(layer => {
        if (layer.bbox) {
            bounds.min_lng = Math.min(bounds.min_lng, layer.bbox.min_lng);
            bounds.min_lat = Math.min(bounds.min_lat, layer.bbox.min_lat);
            bounds.max_lng = Math.max(bounds.max_lng, layer.bbox.max_lng);
            bounds.max_lat = Math.max(bounds.max_lat, layer.bbox.max_lat);
            hasBounds = true;
        }
    });
    
    return hasBounds ? bounds : null;
}

async function loadCityComplete(citySlug) {
    try {
        updateStatus(`Loading complete city view for ${citySlug}...`, 'loading');
        
        // Clear existing layers
        clearAllLayers();
        
        // Load complete city data
        const completeResponse = await fetch(`${API_BASE}/cities/${citySlug}/complete/`);
        if (!completeResponse.ok) {
            throw new Error(`HTTP ${completeResponse.status}: ${completeResponse.statusText}`);
        }
        
        const completeData = await completeResponse.json();
        console.log(`✅ Complete city data loaded:`, completeData);

        // Handle response based on strategy
        if (completeData.strategy === 'complete_geojson') {
            await loadCompleteGeoJSON(completeData);
        } else {
            await loadTileBased(completeData);
        }

        // Setup UI
        if (completeData.metadata?.layers) {
            renderLayersList(completeData.metadata.layers.map(layer => ({
                slug: layer.slug,
                name: layer.name,
                category_name: 'Complete Loading',
                feature_count: layer.feature_count,
                style: { fill_color: layer.color }
            })));
        }

        // Fit map to city bounds
        if (completeData.metadata?.bounds || completeData.bounds) {
            const bounds = completeData.metadata?.bounds || completeData.bounds;
            map.fitBounds([
                [bounds.min_lat, bounds.min_lng],
                [bounds.max_lat, bounds.max_lng]
            ], { padding: [50, 50] });
        }

        updateStatus(`✅ ${citySlug} loaded: ${completeData.metadata?.total_features || 0} features`, 'success');
        showLoadingOverlay(false);
        
    } catch (error) {
        console.error('Complete loading failed:', error);
        updateStatus(`Complete loading failed: ${error.message}`, 'error');
        showLoadingOverlay(false);
    }
}

/* ==========================================================================
   Progressive Loading System
   ========================================================================== */
async function loadCityProgressive(citySlug, chunkSize = 100) {
    try {
        showLoadingOverlay(true);
        updateProgressiveOverlay(true);
        updateStatus(`Starting progressive loading for ${citySlug}...`, 'loading');
        
        // Clear existing layers
        clearAllLayers();
        
        // Initialize progressive layer group
        progressiveLayerGroup = L.layerGroup().addTo(map);
        
        // Reset counters
        currentProgressiveChunk = 0;
        loadedFeatures = 0;
        totalExpectedFeatures = 0;
        progressiveLoadingActive = true;
        
        // Show progressive status panel
        document.getElementById('progressiveStatus').style.display = 'block';
        
        // Load first chunk to get metadata
        const firstChunk = await loadNextProgressiveChunk(citySlug, chunkSize);
        if (!firstChunk) {
            throw new Error('Failed to load first chunk');
        }
        
        // Get total expected features
        totalExpectedFeatures = firstChunk.metadata.total_available_features;
        
        // Set up map bounds from first chunk
        if (firstChunk.metadata.bounds) {
            const bounds = firstChunk.metadata.bounds;
            map.fitBounds([
                [bounds.min_lat, bounds.min_lng],
                [bounds.max_lat, bounds.max_lng]
            ], { padding: [50, 50] });
        }
        
        // Update UI with layer info
        if (firstChunk.metadata.layers) {
            renderLayersList(firstChunk.metadata.layers.map(layer => ({
                slug: layer.slug,
                name: layer.name,
                category_name: 'Progressive Loading',
                feature_count: layer.total_features,
                style: { fill_color: layer.color }
            })));
            
            // Mark all layers as loading in UI
            markAllLayersAsLoading();
        }
        
        // Continue loading remaining chunks
        await loadRemainingChunks(citySlug, chunkSize);
        
        // Mark completion
        markAllLayersAsLoaded();
        document.getElementById('progressiveStatus').style.display = 'none';
        updateStatus(`✅ Progressive loading completed: ${loadedFeatures} features loaded`, 'success');
        showLoadingOverlay(false);
        
    } catch (error) {
        console.error('Progressive loading failed:', error);
        updateStatus(`Progressive loading failed: ${error.message}`, 'error');
        showLoadingOverlay(false);
        progressiveLoadingActive = false;
        document.getElementById('progressiveStatus').style.display = 'none';
    }
}

async function loadNextProgressiveChunk(citySlug, chunkSize) {
    try {
        const url = `${API_BASE}/cities/${citySlug}/progressive/?chunk=${currentProgressiveChunk}&chunk_size=${chunkSize}`;
        console.log(`🔄 Loading chunk ${currentProgressiveChunk}: ${url}`);
        
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const chunkData = await response.json();
        console.log(`✅ Chunk ${currentProgressiveChunk} loaded:`, chunkData.chunk_info);
        
        // Add features to map
        if (chunkData.features && chunkData.features.length > 0) {
            addChunkToMap(chunkData);
            loadedFeatures += chunkData.features.length;
        }
        
        // Update progress
        updateProgressiveStatus(chunkData.chunk_info);
        
        // Prepare for next chunk
        currentProgressiveChunk++;
        
        return chunkData;
        
    } catch (error) {
        console.error(`Error loading chunk ${currentProgressiveChunk}:`, error);
        throw error;
    }
}

async function loadRemainingChunks(citySlug, chunkSize) {
    let isLastChunk = false;
    
    while (!isLastChunk && progressiveLoadingActive) {
        try {
            const chunkData = await loadNextProgressiveChunk(citySlug, chunkSize);
            isLastChunk = chunkData.chunk_info.is_last_chunk;
            
            // Add small delay to prevent overwhelming the browser
            if (!isLastChunk) {
                await new Promise(resolve => setTimeout(resolve, 50));
            }
            
        } catch (error) {
            console.error(`Failed to load chunk ${currentProgressiveChunk}:`, error);
            currentProgressiveChunk++;
            
            // Stop if too many failures
            if (currentProgressiveChunk > (totalExpectedFeatures / chunkSize) + 10) {
                console.warn('Too many failed chunks, stopping progressive loading');
                break;
            }
        }
    }
}

function addChunkToMap(chunkData) {
    const chunkLayer = L.geoJSON(chunkData, {
        style: function(feature) {
            const color = feature.properties.color || '#666666';
            return {
                color: color,
                fillColor: color,
                fillOpacity: 0.7,
                opacity: 0.9,
                weight: 1
            };
        },
        onEachFeature: function(feature, layer) {
            layer.on('click', function(e) {
                showEnhancedFeaturePopup(feature.properties, e.latlng);
            });
            
            layer.on('mouseover', function(e) {
                e.target.setStyle({
                    weight: 2,
                    fillOpacity: 0.9
                });
            });
            
            layer.on('mouseout', function(e) {
                e.target.setStyle({
                    weight: 1,
                    fillOpacity: 0.7
                });
            });
        }
    });
    
    progressiveLayerGroup.addLayer(chunkLayer);
    console.log(`➕ Added ${chunkData.features.length} features to map (total: ${loadedFeatures + chunkData.features.length})`);
}

function updateProgressiveStatus(chunkInfo) {
    const progress = chunkInfo.progress_percentage;
    const message = `Loading ${currentCity}... ${progress}% complete (${loadedFeatures}/${totalExpectedFeatures} features)`;
    
    updateStatus(message, 'loading');
    
    // Update progress bars
    document.getElementById('progressFill').style.width = `${progress}%`;
    document.getElementById('progressText').textContent = `${progress}% - Chunk ${chunkInfo.chunk_index + 1}`;
    
    // Update loading overlay progress
    const progressContainer = document.getElementById('progressContainer');
    const progressFillLarge = document.getElementById('progressFillLarge');
    const progressTextLarge = document.getElementById('progressTextLarge');
    
    if (progressContainer && progressFillLarge && progressTextLarge) {
        progressContainer.style.display = 'block';
        progressFillLarge.style.width = `${progress}%`;
        progressTextLarge.textContent = message;
    }
    
    console.log(`📊 Progress: ${progress}% (chunk ${chunkInfo.chunk_index + 1})`);
}

function updateProgressiveOverlay(show) {
    const progressContainer = document.getElementById('progressContainer');
    if (progressContainer) {
        progressContainer.style.display = show ? 'block' : 'none';
    }
}

/* ==========================================================================
   Progressive Loading Controls
   ========================================================================== */
function setChunkSize(size) {
    preferredChunkSize = size;
    updateStatus(`Chunk size set to ${size} features`, 'success');
    
    // Highlight selected button
    document.querySelectorAll('.quick-actions .btn-sm').forEach(btn => {
        btn.classList.remove('btn-primary');
        btn.classList.add('btn-info');
    });
    
    event.target.classList.remove('btn-info');
    event.target.classList.add('btn-primary');
}

function startProgressiveLoading() {
    if (currentCity) {
        loadCityProgressive(currentCity, preferredChunkSize);
    } else {
        updateStatus('Please select a city first', 'error');
    }
}

function stopProgressiveLoading() {
    progressiveLoadingActive = false;
    updateStatus('Progressive loading stopped by user', 'warning');
    showLoadingOverlay(false);
    document.getElementById('progressiveStatus').style.display = 'none';
}

function showProgressStats() {
    if (!progressiveLoadingActive && loadedFeatures === 0) {
        updateStatus('No progressive loading data available', 'info');
        return;
    }
    
    const stats = `📊 Progressive Loading Stats:
• City: ${currentCity}
• Features loaded: ${loadedFeatures}
• Expected total: ${totalExpectedFeatures}
• Current chunk: ${currentProgressiveChunk}
• Chunk size: ${preferredChunkSize}
• Active: ${progressiveLoadingActive ? 'Yes' : 'No'}`;
    
    alert(stats);
}

function adjustChunkSize() {
    const newSize = prompt('Enter new chunk size (features per request):', preferredChunkSize);
    if (newSize && !isNaN(newSize) && newSize > 0) {
        setChunkSize(parseInt(newSize));
    }
}

/* ==========================================================================
   Complete GeoJSON Loading
   ========================================================================== */
async function loadCompleteGeoJSON(completeData) {
    console.log(`🎯 Loading complete city as GeoJSON: ${completeData.metadata.total_features} features`);
    
    clearAllLayers();
    
    const cityLayer = L.geoJSON(completeData, {
        style: function(feature) {
            const color = feature.properties.color || '#666666';
            return {
                color: color,
                fillColor: color,
                fillOpacity: 0.7,
                opacity: 0.9,
                weight: 1
            };
        },
        onEachFeature: function(feature, layer) {
            layer.on('click', function(e) {
                showEnhancedFeaturePopup(feature.properties, e.latlng);
            });
            
            layer.on('mouseover', function(e) {
                e.target.setStyle({
                    weight: 2,
                    fillOpacity: 0.9
                });
            });
            
            layer.on('mouseout', function(e) {
                e.target.setStyle({
                    weight: 1,
                    fillOpacity: 0.7
                });
            });
        }
    });
    
    cityLayer.addTo(map);
    activeMVTLayers.set('complete_city', cityLayer);
    document.getElementById('tileType').textContent = 'COMPLETE-GEOJSON';
    
    console.log(`✅ Complete city loaded as single layer`);
}

async function loadTileBased(tileData) {
    console.log(`🗺️ Loading city using tiles (large dataset)`);
    
    const combinedTileUrl = tileData.combined_tile_url.replace('{z}', '{z}').replace('{x}', '{x}').replace('{y}', '{y}');
    
    if (!usePNGFallback && typeof L !== 'undefined' && L.vectorGrid && L.vectorGrid.protobuf) {
        const combinedLayer = L.vectorGrid.protobuf(combinedTileUrl, {
            rendererFactory: L.svg.tile,
            vectorTileLayerStyles: createCombinedStyles(tileData.layers),
            interactive: true
        });
        
        combinedLayer.addTo(map);
        activeMVTLayers.set('combined_tiles', combinedLayer);
        
    } else {
        const pngTileUrl = combinedTileUrl.replace('.mvt', '.png');
        const pngLayer = L.tileLayer(pngTileUrl, { opacity: 0.8 });
        pngLayer.addTo(map);
        activeMVTLayers.set('combined_png', pngLayer);
    }
    
    document.getElementById('tileType').textContent = 'COMBINED-TILES';
}

function createCombinedStyles(layers) {
    const styles = {};
    layers.forEach(layer => {
        styles[layer.slug] = {
            color: layer.color,
            fillColor: layer.color,
            fillOpacity: 0.7,
            opacity: 0.9,
            weight: 1
        };
    });
    return styles;
}

/* ==========================================================================
   Layer UI Management
   ========================================================================== */
function renderLayersList(layers) {
    const layersList = document.getElementById('layersList');
    layersList.innerHTML = '';

    layers.forEach(layer => {
        const layerItem = document.createElement('div');
        layerItem.className = 'layer-item';
        layerItem.dataset.layerId = layer.slug;

        const color = getLayerColor(layer);

        layerItem.innerHTML = `
            <div class="layer-color" style="background-color: ${color}"></div>
            <div class="layer-info">
                <div class="layer-name">${layer.name}</div>
                <div class="layer-details">
                    ${layer.category_name} • ${layer.feature_count.toLocaleString()} features
                </div>
            </div>
            <div class="layer-status" id="status-${layer.slug}">Ready</div>
        `;

        layerItem.addEventListener('click', () => toggleLayer(layer));
        layersList.appendChild(layerItem);
    });

    console.log(`Rendered ${layers.length} layers in sidebar`);
}

function markAllLayersAsLoading() {
    document.querySelectorAll('.layer-item').forEach(item => {
        const statusElement = item.querySelector('.layer-status');
        if (statusElement) {
            item.classList.add('loading');
            statusElement.textContent = 'Loading...';
            statusElement.className = 'layer-status status-loading';
        }
    });
}

function markAllLayersAsLoaded() {
    document.querySelectorAll('.layer-item').forEach(item => {
        const statusElement = item.querySelector('.layer-status');
        if (statusElement) {
            item.classList.remove('loading');
            item.classList.add('active');
            statusElement.textContent = 'Loaded ✓';
            statusElement.className = 'layer-status status-success';
        }
    });
    updateLayerCount();
}

function getLayerColor(layer) {
    const categoryKey = layer.category_code?.toUpperCase() || layer.category_name?.toUpperCase();
    if (categoryKey && CATEGORY_COLORS[categoryKey]) {
        return CATEGORY_COLORS[categoryKey];
    }
    
    if (layer.style?.fill_color) {
        return layer.style.fill_color;
    }
    
    return '#666666';
}

/* ==========================================================================
   Coordinate Search Functionality
   ========================================================================== */
async function searchByCoordinates() {
    const latitude = parseFloat(document.getElementById('searchLatitude').value);
    const longitude = parseFloat(document.getElementById('searchLongitude').value);
    
    if (isNaN(latitude) || isNaN(longitude)) {
        updateStatus('Please enter valid latitude and longitude', 'error');
        return;
    }
    
    if (latitude < -90 || latitude > 90) {
        updateStatus('Latitude must be between -90 and 90', 'error');
        return;
    }
    
    if (longitude < -180 || longitude > 180) {
        updateStatus('Longitude must be between -180 and 180', 'error');
        return;
    }
    
    if (!currentCity) {
        updateStatus('Please select a city first', 'error');
        return;
    }
    
    try {
        updateStatus(`Searching location ${latitude}, ${longitude}...`, 'loading');
        
        const response = await fetch(`${API_BASE}/cities/${currentCity}/search-coords/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({
                latitude: latitude,
                longitude: longitude
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const searchData = await response.json();
        console.log('🔍 Search results:', searchData);
        
        processSearchResults(searchData);
        zoomToSearchLocation(latitude, longitude);
        
        updateStatus(searchData.summary, 'success');
        
    } catch (error) {
        console.error('Error searching coordinates:', error);
        updateStatus(`Search failed: ${error.message}`, 'error');
    }
}

function processSearchResults(searchData) {
    searchResults = searchData;
    
    document.getElementById('searchResultsSection').style.display = 'block';
    
    const resultsContainer = document.getElementById('searchResults');
    resultsContainer.innerHTML = '';
    
    const summaryDiv = document.createElement('div');
    summaryDiv.innerHTML = `
        <div style="font-weight: bold; margin-bottom: 10px; color: #495057;">
            📍 Location: ${searchData.search_point.latitude.toFixed(6)}, ${searchData.search_point.longitude.toFixed(6)}
        </div>
        <div style="margin-bottom: 10px; padding: 8px; background: #e3f2fd; border-radius: 4px; font-size: 12px;">
            ${searchData.summary}
        </div>
    `;
    resultsContainer.appendChild(summaryDiv);
    
    if (searchData.containing_features && searchData.containing_features.length > 0) {
        const containingTitle = document.createElement('div');
        containingTitle.innerHTML = '<strong>🎯 This location is in:</strong>';
        containingTitle.style.marginBottom = '8px';
        resultsContainer.appendChild(containingTitle);
        
        searchData.containing_features.forEach((feature, index) => {
            const featureDiv = createFeatureResultDiv(feature, 'search-result-primary');
            resultsContainer.appendChild(featureDiv);
        });
    }
    
    if (searchData.nearby_features && searchData.nearby_features.length > 0) {
        const nearbyTitle = document.createElement('div');
        nearbyTitle.innerHTML = '<strong>📍 Nearby features:</strong>';
        nearbyTitle.style.marginTop = '15px';
        nearbyTitle.style.marginBottom = '8px';
        resultsContainer.appendChild(nearbyTitle);
        
        searchData.nearby_features.forEach(feature => {
            const featureDiv = createFeatureResultDiv(feature, 'search-result-nearby');
            resultsContainer.appendChild(featureDiv);
        });
    }
}

function createFeatureResultDiv(feature, className) {
    const featureDiv = document.createElement('div');
    featureDiv.className = `search-result-item ${className}`;
    featureDiv.style.borderLeftColor = feature.color;
    
    featureDiv.innerHTML = `
        <div style="font-weight: bold; color: ${feature.color};">
            ${feature.layer_name}
        </div>
        <div>Category: ${feature.category}</div>
        ${feature.land_use ? `<div>Land Use: ${feature.land_use}</div>` : ''}
        ${feature.plu_code ? `<div>PLU Code: ${feature.plu_code}</div>` : ''}
        ${feature.area > 0 ? `<div>Area: ${feature.area.toLocaleString()} sq units</div>` : ''}
        ${feature.distance_meters ? `<div>Distance: ${feature.distance_meters}m away</div>` : ''}
        ${feature.administrative_info?.village ? `<div>Village: ${feature.administrative_info.village}</div>` : ''}
    `;
    
    if (feature.feature_id) {
        featureDiv.addEventListener('click', () => highlightFeatureOnMap(feature));
        featureDiv.style.cursor = 'pointer';
    }
    
    return featureDiv;
}

function zoomToSearchLocation(latitude, longitude) {
    if (searchMarker) {
        map.removeLayer(searchMarker);
    }
    
    const searchIcon = L.divIcon({
        className: 'search-marker',
        html: '📍',
        iconSize: [24, 24],
        iconAnchor: [12, 24],
        popupAnchor: [0, -24]
    });
    
    searchMarker = L.marker([latitude, longitude], {
        icon: searchIcon
    }).addTo(map);
    
    const popupContent = `
        <div style="text-align: center;">
            <strong>🔍 Search Location</strong><br>
            <code>${latitude.toFixed(6)}, ${longitude.toFixed(6)}</code><br>
            <small>Click on results below to highlight features</small>
        </div>
    `;
    
    searchMarker.bindPopup(popupContent).openPopup();
    map.setView([latitude, longitude], 16);
    
    console.log(`🎯 Zoomed to search location: ${latitude}, ${longitude}`);
}

function highlightFeatureOnMap(featureData) {
    console.log('🎯 Highlighting feature:', featureData);
    
    const detailsPopup = `
        <div style="max-width: 300px;">
            <h4 style="color: ${featureData.color}; margin: 0 0 10px 0;">
                🎯 ${featureData.layer_name}
            </h4>
            <div><strong>Category:</strong> ${featureData.category}</div>
            ${featureData.land_use ? `<div><strong>Land Use:</strong> ${featureData.land_use}</div>` : ''}
            ${featureData.plu_code ? `<div><strong>PLU Code:</strong> ${featureData.plu_code}</div>` : ''}
            ${featureData.area > 0 ? `<div><strong>Area:</strong> ${featureData.area.toLocaleString()} sq units</div>` : ''}
            <div style="margin-top: 10px; padding-top: 8px; border-top: 1px solid #eee; font-size: 12px; color: #666;">
                Feature ID: ${featureData.feature_id}
            </div>
        </div>
    `;
    
    if (searchMarker) {
        searchMarker.setPopupContent(detailsPopup).openPopup();
    }
    
    updateStatus(`Highlighted: ${featureData.layer_name}`, 'success');
}

function getCurrentLocation() {
    if (!navigator.geolocation) {
        updateStatus('Geolocation is not supported by this browser', 'error');
        return;
    }
    
    updateStatus('Getting your current location...', 'loading');
    
    navigator.geolocation.getCurrentPosition(
        function(position) {
            const latitude = position.coords.latitude;
            const longitude = position.coords.longitude;
            
            document.getElementById('searchLatitude').value = latitude.toFixed(6);
            document.getElementById('searchLongitude').value = longitude.toFixed(6);
            
            searchByCoordinates();
            updateStatus(`Found your location: ${latitude.toFixed(4)}, ${longitude.toFixed(4)}`, 'success');
        },
        function(error) {
            let errorMessage = 'Unable to get location';
            switch(error.code) {
                case error.PERMISSION_DENIED:
                    errorMessage = 'Location access denied by user';
                    break;
                case error.POSITION_UNAVAILABLE:
                    errorMessage = 'Location information unavailable';
                    break;
                case error.TIMEOUT:
                    errorMessage = 'Location request timed out';
                    break;
            }
            updateStatus(errorMessage, 'error');
        },
        {
            enableHighAccuracy: true,
            timeout: 10000,
            maximumAge: 60000
        }
    );
}

function getCsrfToken() {
    const cookieValue = document.cookie
        .split('; ')
        .find(row => row.startsWith('csrftoken='))
        ?.split('=')[1];
    return cookieValue || '';
}

/* ==========================================================================
   Enhanced Map Interaction
   ========================================================================== */
function enhancedHandleMapClick(e) {
    handleMapClick(e);
    
    document.getElementById('searchLatitude').value = e.latlng.lat.toFixed(6);
    document.getElementById('searchLongitude').value = e.latlng.lng.toFixed(6);
    
    console.log(`📍 Map clicked: ${e.latlng.lat.toFixed(6)}, ${e.latlng.lng.toFixed(6)}`);
}

function handleMapClick(e) {
    console.log(`Map clicked at: ${e.latlng.lat.toFixed(4)}, ${e.latlng.lng.toFixed(4)}`);
    
    const zoom = map.getZoom();
    const tileX = Math.floor((e.latlng.lng + 180) / 360 * Math.pow(2, Math.floor(zoom)));
    const tileY = Math.floor((1 - Math.log(Math.tan(e.latlng.lat * Math.PI / 180) + 1 / Math.cos(e.latlng.lat * Math.PI / 180)) / Math.PI) / 2 * Math.pow(2, Math.floor(zoom)));
    
    document.getElementById('zoom').value = Math.floor(zoom);
    document.getElementById('tile-x').value = tileX;
    document.getElementById('tile-y').value = tileY;
}

function showEnhancedFeaturePopup(properties, latlng) {
    let popupContent = `
        <div style="max-width: 300px;">
            <h4 style="margin: 0 0 10px 0; color: ${properties.color};">
                ${properties.layer_name}
            </h4>
            <div style="margin-bottom: 8px;">
                <strong>Category:</strong> ${properties.category}
            </div>
    `;
    
    if (properties.name) {
        popupContent += `<div style="margin-bottom: 8px;"><strong>Name:</strong> ${properties.name}</div>`;
    }
    
    if (properties.land_use) {
        popupContent += `<div style="margin-bottom: 8px;"><strong>Land Use:</strong> ${properties.land_use}</div>`;
    }
    
    if (properties.plu_code) {
        popupContent += `<div style="margin-bottom: 8px;"><strong>PLU Code:</strong> ${properties.plu_code}</div>`;
    }
    
    if (properties.area > 0) {
        popupContent += `<div style="margin-bottom: 8px;"><strong>Area:</strong> ${properties.area.toLocaleString()} sq units</div>`;
    }
    
    popupContent += `
            <div style="margin-top: 10px; padding-top: 8px; border-top: 1px solid #eee; font-size: 12px; color: #666;">
                Feature ID: ${properties.id}
            </div>
        </div>
    `;

    L.popup()
        .setLatLng(latlng)
        .setContent(popupContent)
        .openOn(map);
}

/* ==========================================================================
   Quick Action Functions
   ========================================================================== */
async function loadAllLayers() {
    if (activeMVTLayers.has('complete_city') || activeMVTLayers.has('combined_tiles') || progressiveLoadingActive) {
        updateStatus('All layers already loaded!', 'success');
        return;
    }
    
    updateStatus('Loading all layers...', 'loading');
    
    for (const layer of currentLayers.slice(0, 8)) {
        if (!activeMVTLayers.has(layer.slug)) {
            await toggleLayer(layer);
            await new Promise(resolve => setTimeout(resolve, 200));
        }
    }
    
    updateStatus(`Loaded multiple layers`, 'success');
}

function clearAllLayers() {
    activeMVTLayers.forEach((layer, slug) => {
        map.removeLayer(layer);
        const layerItem = document.querySelector(`[data-layer-id="${slug}"]`);
        const statusElement = layerItem?.querySelector('.layer-status');
        
        if (layerItem) {
            layerItem.classList.remove('active', 'loading');
            if (statusElement) {
                statusElement.textContent = 'Ready';
                statusElement.className = 'layer-status';
            }
        }
    });
    
    // Clear progressive loading
    if (progressiveLayerGroup) {
        map.removeLayer(progressiveLayerGroup);
        progressiveLayerGroup = null;
    }
    
    activeMVTLayers.clear();
    progressiveLoadingActive = false;
    loadedFeatures = 0;
    currentProgressiveChunk = 0;
    
    document.getElementById('progressiveStatus').style.display = 'none';
    updateLayerCount();
    updateStatus('All layers cleared', 'success');
}

function testBigLayer() {
    clearAllLayers();
    
    const bigLayer = currentLayers.find(layer => 
        layer.slug.includes('residential_main') || 
        layer.feature_count > 30000
    ) || currentLayers.find(layer => layer.feature_count > 10000);
    
    if (bigLayer) {
        updateStatus(`Testing big layer: ${bigLayer.name}`, 'loading');
        toggleLayer(bigLayer);
    } else {
        updateStatus('No big layer found', 'error');
    }
}

function fitToLayers() {
    if (currentLayers.length === 0) return;
    
    let bounds = L.latLngBounds();
    let hasBounds = false;
    
    currentLayers.forEach(layer => {
        if (layer.bbox) {
            bounds.extend([layer.bbox.min_lat, layer.bbox.min_lng]);
            bounds.extend([layer.bbox.max_lat, layer.bbox.max_lng]);
            hasBounds = true;
        }
    });
    
    if (hasBounds) {
        map.fitBounds(bounds, { padding: [20, 20] });
        updateStatus('View fitted to all layers', 'success');
    }
}

/* ==========================================================================
   Debug and Testing Functions
   ========================================================================== */
function showTileUrls() {
    if (currentLayers.length === 0) {
        alert('No layers loaded. Select a city first.');
        return;
    }
    
    const urlList = currentLayers.slice(0, 5).map(layer => {
        const testUrl = `${API_BASE}/tiles/${currentCity}/${layer.slug}/12/2931/1899.mvt`;
        return `${layer.name}: ${testUrl}`;
    }).join('\n\n');
    
    const popup = document.createElement('div');
    popup.innerHTML = `
        <div style="position: fixed; top: 50px; left: 50px; right: 50px; background: white; padding: 20px; border: 2px solid #333; border-radius: 5px; z-index: 10000; max-height: 70vh; overflow-y: auto;">
            <h3>🔗 Test Tile URLs</h3>
            <p>Copy these URLs and paste in browser to see actual tiles:</p>
            <textarea style="width: 100%; height: 200px; font-size: 10px; font-family: monospace;">${urlList}</textarea>
            <br><br>
            <button onclick="this.parentElement.parentElement.remove()" style="padding: 10px 20px; background: #dc3545; color: white; border: none; border-radius: 3px;">Close</button>
        </div>
    `;
    document.body.appendChild(popup);
}

function testHighContrast() {
    activeMVTLayers.forEach((layer, slug) => {
        if (layer.setOpacity) {
            layer.setOpacity(1.0);
        }
    });
    
    document.getElementById('opacity-slider').value = 1.0;
    document.getElementById('opacity-value').textContent = '1.0';
    currentOpacity = 1.0;
    
    updateStatus('Applied high contrast mode', 'success');
}

let isDarkBase = false;
function changeBaseMap() {
    map.eachLayer(layer => {
        if (layer.options && layer.options.attribution && layer.options.attribution.includes('OpenStreetMap')) {
            map.removeLayer(layer);
        }
    });
    
    if (!isDarkBase) {
        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
            attribution: '© CARTO © OpenStreetMap contributors',
            maxZoom: 18
        }).addTo(map);
        updateStatus('Switched to dark base map', 'success');
        isDarkBase = true;
    } else {
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors',
            maxZoom: 18
        }).addTo(map);
        updateStatus('Switched to light base map', 'success');
        isDarkBase = false;
    }
}

let tileGridVisible = false;
function showTileGrid() {
    if (!tileGridVisible) {
        const tileGrid = L.gridLayer({
            attribution: 'Tile Grid',
            opacity: 0.5
        });
        
        tileGrid.createTile = function(coords) {
            const tile = document.createElement('div');
            tile.style.border = '1px solid red';
            tile.style.backgroundColor = 'rgba(255,0,0,0.1)';
            tile.innerHTML = `<div style="color: red; font-size: 10px; font-weight: bold; padding: 2px;">${coords.z}/${coords.x}/${coords.y}</div>`;
            return tile;
        };
        
        tileGrid.addTo(map);
        window.tileGridLayer = tileGrid;
        tileGridVisible = true;
        updateStatus('Tile grid overlay enabled', 'success');
    } else {
        map.removeLayer(window.tileGridLayer);
        tileGridVisible = false;
        updateStatus('Tile grid overlay disabled', 'success');
    }
}

function forceMVTMode() {
    usePNGFallback = false;
    document.getElementById('tileType').textContent = 'MVT (Forced)';
    clearAllLayers();
    updateStatus('Forced MVT mode - will only use vector tiles', 'success');
    console.log('🔥 Forced MVT mode enabled');
}

function forcePNGMode() {
    usePNGFallback = true;
    document.getElementById('tileType').textContent = 'PNG (Forced)';
    clearAllLayers();
    updateStatus('Forced PNG mode - will only use raster tiles', 'success');
    console.log('🖼️ Forced PNG mode enabled');
}

function autoMode() {
    usePNGFallback = !checkVectorGrid();
    const mode = usePNGFallback ? 'PNG (Auto)' : 'MVT (Auto)';
    document.getElementById('tileType').textContent = mode;
    clearAllLayers();
    updateStatus(`Auto mode - will use ${usePNGFallback ? 'PNG' : 'MVT'} tiles`, 'success');
    console.log(`🤖 Auto mode: ${mode}`);
}

function reloadLayers() {
    updateStatus('Reloading layers...', 'loading');
    clearAllLayers();
    if (currentCity) {
        loadCityLayers(currentCity);
    } else {
        updateStatus('No city selected', 'error');
    }
}

/* ==========================================================================
   Manual Tile Testing
   ========================================================================== */
function updateMapFromCoords() {
    const zoom = parseInt(document.getElementById('zoom').value);
    const x = parseInt(document.getElementById('tile-x').value);
    const y = parseInt(document.getElementById('tile-y').value);
    
    const bounds = tileToBounds(x, y, zoom);
    const centerLat = (bounds.north + bounds.south) / 2;
    const centerLng = (bounds.east + bounds.west) / 2;
    
    map.setView([centerLat, centerLng], zoom);
    
    if (window.tileBoundary) {
        map.removeLayer(window.tileBoundary);
    }
    
    window.tileBoundary = L.rectangle([
        [bounds.south, bounds.west],
        [bounds.north, bounds.east]
    ], {
        color: 'red',
        weight: 2,
        fillOpacity: 0.1
    }).addTo(map);
    
    updateStatus(`Moved to tile ${zoom}/${x}/${y}`, 'info');
}

function testSpecificTile() {
    const zoom = document.getElementById('zoom').value;
    const x = document.getElementById('tile-x').value;
    const y = document.getElementById('tile-y').value;
    
    if (!currentLayers.length) {
        updateStatus('No layers loaded. Select a city first.', 'error');
        return;
    }
    
    const testLayer = currentLayers[0];
    const testUrl = `${API_BASE}/tiles/${currentCity}/${testLayer.slug}/${zoom}/${x}/${y}.mvt`;
    
    console.log(`🧪 Testing tile: ${testUrl}`);
    
    const tilePreview = document.createElement('div');
    tilePreview.innerHTML = `
        <div style="position: fixed; top: 100px; right: 10px; background: white; padding: 15px; border: 2px solid #333; border-radius: 5px; z-index: 10000; max-width: 350px;">
            <h4>🔍 Testing Tile: ${testLayer.name}</h4>
            <p><strong>Coordinates:</strong> ${zoom}/${x}/${y}</p>
            <p><strong>URL:</strong><br><a href="${testUrl}" target="_blank" style="font-size: 10px; word-break: break-all;">${testUrl}</a></p>
            <button onclick="this.parentElement.remove()" style="margin-top: 10px; padding: 5px 10px; background: #dc3545; color: white; border: none; border-radius: 3px;">Close</button>
            <button onclick="window.open('${testUrl}', '_blank')" style="margin-top: 10px; margin-left: 5px; padding: 5px 10px; background: #007bff; color: white; border: none; border-radius: 3px;">Open Tile</button>
        </div>
    `;
    document.body.appendChild(tilePreview);
    
    setTimeout(() => {
        if (tilePreview.parentElement) {
            tilePreview.remove();
        }
    }, 10000);
}

/* ==========================================================================
   Utility Functions
   ========================================================================== */
function tileToBounds(x, y, zoom) {
    const n = Math.PI - 2 * Math.PI * y / Math.pow(2, zoom);
    const west = x / Math.pow(2, zoom) * 360 - 180;
    const east = (x + 1) / Math.pow(2, zoom) * 360 - 180;
    const north = 180 / Math.PI * Math.atan(0.5 * (Math.exp(n) - Math.exp(-n)));
    
    const n2 = Math.PI - 2 * Math.PI * (y + 1) / Math.pow(2, zoom);
    const south = 180 / Math.PI * Math.atan(0.5 * (Math.exp(n2) - Math.exp(-n2)));
    
    return { north, south, east, west };
}

function updateStatus(message, type = 'info') {
    const statusElement = document.getElementById('statusMessage');
    const indicatorElement = document.getElementById('statusIndicator');
    const sidebarStatus = document.getElementById('status');
    
    if (statusElement) statusElement.textContent = message;
    if (indicatorElement) indicatorElement.className = `status-indicator indicator-${type}`;
    if (sidebarStatus) sidebarStatus.textContent = message;
    
    console.log(`[${type.toUpperCase()}] ${message}`);
}

function updateMapInfo() {
    const center = map.getCenter();
    const zoom = map.getZoom();
    
    document.getElementById('coordinates').textContent = 
        `${center.lat.toFixed(4)}, ${center.lng.toFixed(4)}`;
    document.getElementById('zoom-display').textContent = zoom.toFixed(1);
    
    const tileX = Math.floor((center.lng + 180) / 360 * Math.pow(2, Math.floor(zoom)));
    const tileY = Math.floor((1 - Math.log(Math.tan(center.lat * Math.PI / 180) + 1 / Math.cos(center.lat * Math.PI / 180)) / Math.PI) / 2 * Math.pow(2, Math.floor(zoom)));
    
    document.getElementById('currentTile').textContent = `${Math.floor(zoom)}/${tileX}/${tileY}`;
    document.getElementById('current-tile-info').textContent = `${Math.floor(zoom)}/${tileX}/${tileY}`;
}

function updateLayerCount() {
    const count = progressiveLoadingActive ? 1 : activeMVTLayers.size;
    document.getElementById('layerCount').textContent = count;
}

function showLoadingOverlay(show) {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) {
        overlay.style.display = show ? 'flex' : 'none';
        
        if (!show) {
            // Reset progress container
            const progressContainer = document.getElementById('progressContainer');
            if (progressContainer) {
                progressContainer.style.display = 'none';
            }
        }
    }
}

/* ==========================================================================
   Layer Management Functions
   ========================================================================== */
async function toggleLayer(layer) {
    const layerItem = document.querySelector(`[data-layer-id="${layer.slug}"]`);
    const statusElement = layerItem?.querySelector('.layer-status');
    
    if (!layerItem || !statusElement) return;
    
    if (activeMVTLayers.has(layer.slug)) {
        removeLayer(layer);
        layerItem.classList.remove('active');
        statusElement.textContent = 'Ready';
        statusElement.className = 'layer-status';
    } else {
        layerItem.classList.add('loading');
        statusElement.textContent = 'Loading...';
        statusElement.className = 'layer-status status-loading';
        
        const success = await addLayer(layer);
        
        layerItem.classList.remove('loading');
        if (success) {
            layerItem.classList.add('active');
            statusElement.textContent = 'Loaded ✓';
            statusElement.className = 'layer-status status-success';
        } else {
            statusElement.textContent = 'Failed ✗';
            statusElement.className = 'layer-status status-error';
        }
    }
    
    updateLayerCount();
}

async function addLayer(layer) {
    try {
        updateStatus(`Loading ${layer.name}...`, 'loading');
        
        const color = getLayerColor(layer);
        console.log(`Loading layer: ${layer.name} with color: ${color}`);

        let layerToAdd;
        let usesPNG = false;

        if (!usePNGFallback && typeof L !== 'undefined' && L.vectorGrid && L.vectorGrid.protobuf) {
            try {
                console.log(`🎯 Using MVT tiles for ${layer.name}`);
                
                const mvtTileUrl = `${window.location.origin}${API_BASE}/tiles/${currentCity}/${layer.slug}/{z}/{x}/{y}.mvt`;
                
                layerToAdd = L.vectorGrid.protobuf(mvtTileUrl, {
                    rendererFactory: L.svg.tile,
                    vectorTileLayerStyles: {
                        [layer.slug]: {
                            color: color,
                            fillColor: color,
                            fillOpacity: currentOpacity * 0.8,
                            weight: 1,
                            opacity: currentOpacity
                        }
                    },
                    interactive: true
                });

                layerToAdd.on('click', function(e) {
                    if (e.layer && e.layer.properties) {
                        showFeaturePopup(e.layer.properties, e.latlng, layer.name);
                    }
                });

            } catch (mvtError) {
                console.warn(`❌ MVT failed for ${layer.name}:`, mvtError);
                layerToAdd = null;
            }
        }

        if (!layerToAdd) {
            console.log(`🖼️ Using PNG tiles for ${layer.name} (fallback)`);
            usesPNG = true;
            
            const pngTileUrl = `${window.location.origin}${API_BASE}/tiles/${currentCity}/${layer.slug}/{z}/{x}/{y}.png`;
            
            layerToAdd = L.tileLayer(pngTileUrl, {
                attribution: `${layer.name} Data`,
                opacity: Math.max(currentOpacity, 0.8),
                maxZoom: 16,
                className: `layer-${layer.slug}`
            });
        }

        layerToAdd.addTo(map);
        activeMVTLayers.set(layer.slug, layerToAdd);

        if (layer.bbox && activeMVTLayers.size === 1) {
            setTimeout(() => {
                console.log(`🎯 Zooming to ${layer.name} bounds:`, layer.bbox);
                map.fitBounds([
                    [layer.bbox.min_lat, layer.bbox.min_lng],
                    [layer.bbox.max_lat, layer.bbox.max_lng]
                ], { 
                    padding: [50, 50], 
                    maxZoom: 14 
                });
            }, 500);
        }

        const tileType = usesPNG ? 'PNG' : 'MVT';
        updateStatus(`${layer.name} loaded successfully (${tileType})`, 'success');
        document.getElementById('tileType').textContent = tileType;
        
        return true;

    } catch (error) {
        console.error(`Error loading layer ${layer.name}:`, error);
        updateStatus(`Failed to load ${layer.name}: ${error.message}`, 'error');
        return false;
    }
}

function removeLayer(layer) {
    const mvtLayer = activeMVTLayers.get(layer.slug);
    if (mvtLayer) {
        map.removeLayer(mvtLayer);
        activeMVTLayers.delete(layer.slug);
        console.log(`Removed layer: ${layer.name}`);
    }
}

function showFeaturePopup(properties, latlng, layerName) {
    let popupContent = `<div><h4>${layerName}</h4>`;
    
    Object.entries(properties).forEach(([key, value]) => {
        if (value && key !== 'geometry' && typeof value !== 'object') {
            popupContent += `<div><strong>${key}:</strong> ${value}</div>`;
        }
    });
    
    popupContent += '</div>';

    L.popup()
        .setLatLng(latlng)
        .setContent(popupContent)
        .openOn(map);
}

function loadCategories(layers) {
    const categories = [...new Set(layers.map(layer => layer.category_name))];
    const categorySelect = document.getElementById('categorySelect');
    
    categorySelect.innerHTML = '<option value="">All Categories</option>';
    categories.forEach(category => {
        const option = document.createElement('option');
        option.value = category;
        option.textContent = category;
        categorySelect.appendChild(option);
    });

    console.log(`✅ Categories loaded:`, categories);
}

function filterLayersByCategory(categoryName) {
    const layerItems = document.querySelectorAll('.layer-item');
    let visibleCount = 0;
    
    layerItems.forEach(item => {
        const layerId = item.dataset.layerId;
        const layer = currentLayers.find(l => l.slug === layerId);
        
        if (!categoryName || layer?.category_name === categoryName) {
            item.style.display = 'flex';
            visibleCount++;
        } else {
            item.style.display = 'none';
            if (activeMVTLayers.has(layerId)) {
                removeLayer(layer);
                item.classList.remove('active');
            }
        }
    });

    console.log(`🏷️ Category filter applied: showing ${visibleCount} layers`);
}

function clearLayers() {
    clearAllLayers();
    
    document.getElementById('layersList').innerHTML = `
        <div class="loading-placeholder">
            Select a city to view layers
        </div>
    `;
    
    document.getElementById('categorySelect').innerHTML = '<option value="">All Categories</option>';
    
    currentCity = null;
    currentLayers = [];
    updateLayerCount();
}

/* ==========================================================================
   Application Initialization
   ========================================================================== */
console.log('🗺️ Geo Mapping Interface JavaScript loaded successfully');
updateStatus('JavaScript initialized - ready to load map', 'success');