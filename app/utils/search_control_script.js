// Store plant coordinates globally for easy access
var plantRegistry = {};

// Wait for the DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
    // Get elements
    const searchButton = document.getElementById('searchButton');
    const searchSidebar = document.getElementById('searchSidebar');
    const closeSearch = document.getElementById('closeSearch');
    const plantSearchInput = document.getElementById('plantSearchInput');
    const plantsList = document.getElementById('plantsList');
    const sourceFilters = document.getElementsByName('sourceFilter');
    
    // Toggle search sidebar when search button is clicked
    searchButton.addEventListener('click', function() {
        searchSidebar.classList.add('active');
        plantSearchInput.focus();
    });
    
    // Close search sidebar when close button is clicked
    closeSearch.addEventListener('click', function() {
        searchSidebar.classList.remove('active');
    });
    
    // Filter plants when text input changes
    plantSearchInput.addEventListener('input', filterPlants);
    
    // Filter plants when source filter changes
    sourceFilters.forEach(function(radio) {
        radio.addEventListener('change', filterPlants);
    });
    
    // Filter plants based on search input and selected filter
    function filterPlants() {
        const searchText = plantSearchInput.value.toLowerCase();
        const selectedSource = document.querySelector('input[name="sourceFilter"]:checked').value;
        const plantItems = document.querySelectorAll('.plant-item');
        let visibleCount = 0;
        
        plantItems.forEach(function(item) {
            const plantName = item.getAttribute('data-name').toLowerCase();
            const plantSource = item.getAttribute('data-source');
            
            const matchesSearch = plantName.includes(searchText);
            const matchesSource = selectedSource === 'all' || plantSource === selectedSource;
            
            if (matchesSearch && matchesSource) {
                item.style.display = 'block';
                visibleCount++;
            } else {
                item.style.display = 'none';
            }
        });
        
        // Show/hide no results message
        let noResultsMsg = document.querySelector('.no-results');
        if (visibleCount === 0) {
            if (!noResultsMsg) {
                noResultsMsg = document.createElement('div');
                noResultsMsg.className = 'no-results';
                noResultsMsg.textContent = 'No plants match your search';
                plantsList.appendChild(noResultsMsg);
            }
            noResultsMsg.style.display = 'block';
        } else if (noResultsMsg) {
            noResultsMsg.style.display = 'none';
        }
    }
    
    // Direct click handling for all plant items
    document.querySelectorAll('.plant-item').forEach(function(item) {
        item.addEventListener('click', function() {
            const lat = parseFloat(this.getAttribute('data-lat'));
            const lon = parseFloat(this.getAttribute('data-lon'));
            const plantId = this.getAttribute('data-id');
            
            // Register this plant for debugging
            console.log(`Clicked plant ${plantId} at [${lat}, ${lon}]`);
            
            // Handle the zoom
            zoomToPlant(lat, lon, plantId);
        });
    });
});

// Function to zoom to plant when clicked
function zoomToPlant(lat, lon, plantId) {
    console.log(`Zooming to [${lat}, ${lon}] for plant ${plantId}`);
    
    // Wait for map to be available
    function waitForMap() {
        if (document.querySelector('.folium-map') && document.querySelector('.folium-map')._leaflet_map) {
            var map = document.querySelector('.folium-map')._leaflet_map;
            
            // Close sidebar first (to avoid UI issues)
            document.getElementById('searchSidebar').classList.remove('active');
            
            // First zoom to the location
            map.setView([lat, lon], 13);
            
            // Store all layers with their distance to our target
            var candidateLayers = [];
            
            // Find all layers with coordinates
            map.eachLayer(function(layer) {
                if (layer._latlng) {
                    // Calculate distance to our target
                    var distance = Math.sqrt(
                        Math.pow(layer._latlng.lat - lat, 2) + 
                        Math.pow(layer._latlng.lng - lon, 2)
                    );
                    
                    candidateLayers.push({
                        layer: layer,
                        distance: distance
                    });
                }
            });
            
            // Sort by distance
            candidateLayers.sort(function(a, b) {
                return a.distance - b.distance;
            });
            
            // First try direct method - find the closest layer and open its popup
            if (candidateLayers.length > 0) {
                var closestLayer = candidateLayers[0].layer;
                console.log("Found closest layer:", closestLayer);
                
                // Try to open popup
                try {
                    if (closestLayer.openPopup) {
                        setTimeout(function() {
                            closestLayer.openPopup();
                        }, 500);
                    }
                } catch (e) {
                    console.log("Error opening popup:", e);
                }
            }
            
            // Fallback: Try to click any interactive elements at this location
            setTimeout(function() {
                // Get all circle markers and try click them
                var allMarkers = document.querySelectorAll('.leaflet-interactive');
                
                allMarkers.forEach(function(marker) {
                    try {
                        // Try to get position of this marker
                        var markerPosition = marker.getBoundingClientRect();
                        var centerX = markerPosition.left + markerPosition.width/2;
                        var centerY = markerPosition.top + markerPosition.height/2;
                        
                        // Convert to latlng
                        var containerPoint = L.point(centerX, centerY);
                        var markerLatLng = map.containerPointToLatLng(containerPoint);
                        
                        // If close enough, click it
                        var distance = Math.sqrt(
                            Math.pow(markerLatLng.lat - lat, 2) + 
                            Math.pow(markerLatLng.lng - lon, 2)
                        );
                        
                        if (distance < 0.01) {
                            console.log("Clicking marker at distance:", distance);
                            marker.click();
                        }
                    } catch (e) {
                        console.log("Error clicking marker:", e);
                    }
                });
            }, 800);
        } else {
            // Map not ready yet, retry after a delay
            setTimeout(waitForMap, 100);
        }
    }
    
    // Start waiting for map
    waitForMap();
}

// Register plant coordinates
function registerPlant(id, lat, lon) {
    plantRegistry[id] = {lat: lat, lon: lon};
}