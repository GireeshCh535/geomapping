// Minimal simple_map.js for combined vector tile demo

const API_BASE = '/api';
let map;
let vectorLayer;

function setStatus(msg) {
    document.getElementById('status').textContent = msg;
}

function initMap() {
    map = L.map('map').setView([12.9716, 77.5946], 11);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 18
    }).addTo(map);
}

async function loadCities() {
    setStatus('Loading cities...');
    const res = await fetch(`${API_BASE}/cities/`);
    const data = await res.json();
    const select = document.getElementById('citySelect');
    data.results.forEach(city => {
        const opt = document.createElement('option');
        opt.value = city.slug;
        opt.textContent = city.name;
        select.appendChild(opt);
    });
    setStatus('Select a city to view map.');
}

async function loadCity(citySlug) {
    setStatus(`Loading ${citySlug}...`);
    if (vectorLayer) {
        map.removeLayer(vectorLayer);
    }
    const res = await fetch(`${API_BASE}/cities/${citySlug}/complete/?force_tiles=true`);
    const data = await res.json();
    const tileUrl = 'http://localhost/api/tiles/bangalore/combined/{z}/{x}/{y}.png';
    vectorLayer = L.vectorGrid.protobuf(tileUrl, {
        rendererFactory: L.svg.tile,
        vectorTileLayerStyles: createCombinedStyles(data.layers),
        interactive: true
    });
    vectorLayer.on('click', function(e) {
        if (e.layer && e.layer.properties) {
            const p = e.layer.properties;
            L.popup()
                .setLatLng(e.latlng)
                .setContent(`<b>${p.layer_name || ''}</b><br>Category: ${p.category || ''}<br>Area: ${p.area || ''}`)
                .openOn(map);
        }
    });
    vectorLayer.addTo(map);
    setStatus(`Loaded ${citySlug}`);
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

document.addEventListener('DOMContentLoaded', () => {
    initMap();
    loadCities();
    document.getElementById('citySelect').addEventListener('change', function() {
        if (this.value) {
            loadCity(this.value);
        }
    });
}); 