import folium
from folium.plugins import MarkerCluster
import os
import json

def create_map(data, output_path):
    """Generate an interactive map with power plants in California."""
    # Initialize the map
    energy_map = folium.Map(location=[37.5, -119.5], zoom_start=6, control_scale=True, tiles="cartodbpositron")
    
    # Create feature groups for each power source type
    wind_group = folium.FeatureGroup(name="Wind Power", show=True).add_to(energy_map)
    solar_group = folium.FeatureGroup(name="Solar Power", show=True).add_to(energy_map)
    water_group = folium.FeatureGroup(name="Water Power", show=True).add_to(energy_map)
    
    # Create a list to store plant data for JavaScript
    plant_list = []
    
    # Add markers to the map with custom formatting
    for i, (_, plant) in enumerate(data.iterrows()):
        lat, lon = plant['y'], plant['x']
        energy_output = plant['estimated_output']
        plant_name = str(plant['PlantName'])
        source = plant['PriEnergySource']
        
        weather_info = f"""
            <b>{plant_name}</b><br>
            Source: {source}<br>
            Estimated Output: {energy_output:.2f} MW<br>
            Capacity: {plant['Capacity_Latest']} MW<br>
            Wind Speed: {plant['wind_speed']} m/s<br>
            Water Flow: {plant['water_flow']} mm/h<br>
            Cloud Cover: {plant['cloud_cover']}%<br>
        """
        
        # Define marker color and opacity based on energy source
        color = "yellow" if source == "SUN" else \
                "red" if source == "WND" else "blue"
        opacity = 0.8
        
        # Create a unique ID for this marker
        marker_id = f"marker_{i}"
        
        # Store plant data for JavaScript
        plant_list.append({
            'id': marker_id,
            'name': plant_name,
            'lat': lat,
            'lon': lon,
            'source': source,
            'output': energy_output
        })
        
        # Create marker with a custom ID in the tooltip HTML
        marker = folium.CircleMarker(
            location=[lat, lon],
            radius=6,
            color="black",
            fill=True,
            fill_color=color,
            fill_opacity=opacity,
            popup=weather_info,
            tooltip=plant_name
        )
        
        # Add marker to the appropriate feature group
        if source == "WND":
            marker.add_to(wind_group)
        elif source == "SUN":
            marker.add_to(solar_group)
        elif source == "WAT":
            marker.add_to(water_group)
    
    # Add layer control with overlays only
    folium.LayerControl(collapsed=False).add_to(energy_map)
    
    # Add HTML and JavaScript for search functionality
    search_html = """
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.3/css/all.min.css">
    <style>
    .search-container {
        position: absolute;
        top: 10px;
        left: 50px;
        z-index: 999;
    }
    .search-button {
        background: white;
        border: none;
        border-radius: 4px;
        padding: 8px;
        box-shadow: 0 0 8px rgba(0,0,0,0.3);
        cursor: pointer;
        display: flex;
        align-items: center;
        font-size: 14px;
    }
    .search-button i {
        margin-right: 5px;
    }
    .search-popup {
        display: none;
        position: absolute;
        top: 45px;
        left: 0;
        background: white;
        border-radius: 4px;
        width: 300px;
        box-shadow: 0 0 10px rgba(0,0,0,0.3);
        z-index: 1000;
    }
    .search-header {
        padding: 10px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 1px solid #eee;
    }
    .search-header h3 {
        margin: 0;
        font-size: 16px;
    }
    .close-search {
        cursor: pointer;
        font-size: 18px;
        color: #777;
    }
    .search-input {
        width: 100%;
        padding: 8px 10px;
        border: 1px solid #ddd;
        border-radius: 4px;
        box-sizing: border-box;
        margin-bottom: 10px;
    }
    .filter-buttons {
        display: flex;
        gap: 5px;
        margin-bottom: 10px;
    }
    .filter-button {
        padding: 5px 10px;
        border-radius: 4px;
        cursor: pointer;
        background: #eee;
        font-size: 12px;
    }
    .filter-button.active {
        background: #007bff;
        color: white;
    }
    .plant-list {
        max-height: 300px;
        overflow-y: auto;
        border-top: 1px solid #eee;
    }
    .plant-item {
        padding: 8px 10px;
        border-bottom: 1px solid #eee;
        cursor: pointer;
        display: flex;
        justify-content: space-between;
    }
    .plant-item:hover {
        background: #f5f5f5;
    }
    .plant-item[data-source="SUN"] {
        border-left: 4px solid yellow;
    }
    .plant-item[data-source="WND"] {
        border-left: 4px solid red;
    }
    .plant-item[data-source="WAT"] {
        border-left: 4px solid blue;
    }
    .plant-output {
        color: #777;
        font-size: 12px;
    }
    </style>
    
    <div class="search-container">
        <button class="search-button" id="searchButton">
            <i class="fas fa-search"></i> Search
        </button>
        <div class="search-popup" id="searchPopup">
            <div class="search-header">
                <h3>Plant Search</h3>
                <span class="close-search" id="closeSearch">&times;</span>
            </div>
            <div style="padding: 10px;">
                <input type="text" class="search-input" id="plantSearchInput" placeholder="Search plants...">
                <div class="filter-buttons">
                    <div class="filter-button active" data-filter="all">All</div>
                    <div class="filter-button" data-filter="SUN">Solar</div>
                    <div class="filter-button" data-filter="WND">Wind</div>
                    <div class="filter-button" data-filter="WAT">Water</div>
                </div>
            </div>
            <div class="plant-list" id="plantList">
                <!-- Plants will be added here -->
            </div>
        </div>
    </div>
    
    <script>
    // Plant data from Python
    const plantData = PLANT_DATA_PLACEHOLDER;
    
    document.addEventListener('DOMContentLoaded', function() {
        // Elements
        const searchButton = document.getElementById('searchButton');
        const searchPopup = document.getElementById('searchPopup');
        const closeSearch = document.getElementById('closeSearch');
        const searchInput = document.getElementById('plantSearchInput');
        const plantList = document.getElementById('plantList');
        const filterButtons = document.querySelectorAll('.filter-button');
        
        // Get map
        const map = document.querySelector('.folium-map')._leaflet_map;
        
        // Toggle search popup
        searchButton.addEventListener('click', function() {
            searchPopup.style.display = searchPopup.style.display === 'block' ? 'none' : 'block';
            if (searchPopup.style.display === 'block') {
                searchInput.focus();
            }
        });
        
        // Close search popup
        closeSearch.addEventListener('click', function() {
            searchPopup.style.display = 'none';
        });
        
        // Click outside to close
        document.addEventListener('click', function(event) {
            if (!event.target.closest('.search-container') && searchPopup.style.display === 'block') {
                searchPopup.style.display = 'none';
            }
        });
        
        // Handle filter buttons
        filterButtons.forEach(button => {
            button.addEventListener('click', function() {
                // Remove active class from all buttons
                filterButtons.forEach(btn => btn.classList.remove('active'));
                
                // Add active class to clicked button
                this.classList.add('active');
                
                // Update list
                updatePlantList();
            });
        });
        
        // Handle search input
        searchInput.addEventListener('input', updatePlantList);
        
        // Function to update plant list based on search and filter
        function updatePlantList() {
            const searchText = searchInput.value.toLowerCase();
            const activeFilter = document.querySelector('.filter-button.active').getAttribute('data-filter');
            
            // Clear current list
            plantList.innerHTML = '';
            
            // Filter plants
            const filteredPlants = plantData.filter(plant => {
                const nameMatch = plant.name.toLowerCase().includes(searchText);
                const sourceMatch = activeFilter === 'all' || plant.source === activeFilter;
                return nameMatch && sourceMatch;
            });
            
            // Sort plants by name
            filteredPlants.sort((a, b) => a.name.localeCompare(b.name));
            
            // Add filtered plants to list
            filteredPlants.forEach(plant => {
                const item = document.createElement('div');
                item.className = 'plant-item';
                item.setAttribute('data-source', plant.source);
                item.setAttribute('data-lat', plant.lat);
                item.setAttribute('data-lon', plant.lon);
                
                item.innerHTML = `
                    <span>${plant.name}</span>
                    <span class="plant-output">${plant.output.toFixed(1)} MW</span>
                `;
                
                // Add click handler
                item.addEventListener('click', function() {
                    // Get coordinates
                    const lat = parseFloat(this.getAttribute('data-lat'));
                    const lon = parseFloat(this.getAttribute('data-lon'));
                    
                    // Zoom to location
                    map.flyTo([lat, lon], 13);
                    
                    // Close search popup
                    searchPopup.style.display = 'none';
                    
                    // Wait for zoom to complete before trying to open popup
                    setTimeout(function() {
                        // Try to find the marker at this location
                        map.eachLayer(function(layer) {
                            if (layer._latlng && 
                                Math.abs(layer._latlng.lat - lat) < 0.0001 && 
                                Math.abs(layer._latlng.lng - lon) < 0.0001) {
                                
                                // Open popup
                                try {
                                    layer.openPopup();
                                } catch (e) {
                                    console.error('Error opening popup:', e);
                                }
                            }
                        });
                    }, 800); // Wait 800ms for zoom to complete
                });
                
                plantList.appendChild(item);
            });
            
            // Show message if no plants found
            if (filteredPlants.length === 0) {
                const message = document.createElement('div');
                message.textContent = 'No plants found';
                message.style.padding = '10px';
                message.style.textAlign = 'center';
                message.style.color = '#777';
                message.style.fontStyle = 'italic';
                plantList.appendChild(message);
            }
        }
        
        // Initial plant list update
        updatePlantList();
    });
    </script>
    """
    
    # Replace placeholder with actual plant data
    plant_json = json.dumps(plant_list)
    search_html = search_html.replace('PLANT_DATA_PLACEHOLDER', plant_json)
    
    # Add the search HTML to the map
    energy_map.get_root().html.add_child(folium.Element(search_html))
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Save the map
    energy_map.save(output_path)
    print(f"Map saved as '{output_path}'")
    
    return output_path