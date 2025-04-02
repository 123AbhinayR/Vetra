import folium
import os

def create_map(data, output_path):
    """Generate an interactive map with power plants in California with direct zoom links."""
    # Initialize the map
    energy_map = folium.Map(location=[37.5, -119.5], zoom_start=6, control_scale=True, tiles="cartodbpositron")
    
    # Create feature groups for each power source type
    wind_group = folium.FeatureGroup(name="Wind Power", show=True).add_to(energy_map)
    solar_group = folium.FeatureGroup(name="Solar Power", show=True).add_to(energy_map)
    water_group = folium.FeatureGroup(name="Water Power", show=True).add_to(energy_map)
    
    # Dictionary to track all plants for the sidebar
    all_plants = []
    
    # Add markers to the map with custom formatting
    for _, plant in data.iterrows():
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
        
        marker = folium.CircleMarker(
            location=[lat, lon],
            radius=6,  # Marker size
            color="black",  # Border color
            fill=True,
            fill_color=color,
            fill_opacity=opacity,
            popup=weather_info,
            tooltip=plant_name  # Add tooltip for easier identification
        )
        
        # Add marker to the appropriate feature group
        if source == "WND":
            marker.add_to(wind_group)
        elif source == "SUN":
            marker.add_to(solar_group)
        elif source == "WAT":
            marker.add_to(water_group)
        
        # Store plant info for the sidebar
        all_plants.append({
            'name': plant_name,
            'lat': lat,
            'lon': lon,
            'source': source,
            'output': energy_output
        })
    
    # Add layer control
    folium.LayerControl(collapsed=False).add_to(energy_map)
    
    # Create a sidebar with direct links
    sidebar_html = """
    <style>
    .sidebar {
        position: absolute;
        left: 0;
        top: 0;
        bottom: 0;
        width: 300px;
        background: white;
        box-shadow: 0 0 15px rgba(0, 0, 0, 0.2);
        overflow-y: auto;
        z-index: 1000;
        transition: transform 0.3s;
        transform: translateX(-300px);
    }
    
    .sidebar.visible {
        transform: translateX(0);
    }
    
    .sidebar-header {
        background: #f8f9fa;
        padding: 10px;
        border-bottom: 1px solid #dee2e6;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    
    .sidebar-header h3 {
        margin: 0;
        font-size: 16px;
    }
    
    .close-btn {
        cursor: pointer;
        font-size: 20px;
    }
    
    .sidebar-content {
        padding: 10px;
    }
    
    .search-container {
        margin-bottom: 10px;
    }
    
    #plant-search {
        width: 100%;
        padding: 8px;
        border: 1px solid #ced4da;
        border-radius: 4px;
    }
    
    .filter-buttons {
        display: flex;
        gap: 5px;
        margin-bottom: 10px;
    }
    
    .filter-btn {
        padding: 5px 10px;
        background: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 4px;
        cursor: pointer;
    }
    
    .filter-btn.active {
        background: #007bff;
        color: white;
        border-color: #007bff;
    }
    
    .plant-link {
        display: block;
        padding: 8px;
        margin-bottom: 5px;
        border-radius: 4px;
        text-decoration: none;
        color: #212529;
        cursor: pointer;
    }
    
    .plant-link:hover {
        background: #f8f9fa;
    }
    
    .plant-link.sun {
        border-left: 4px solid #FFD700;
    }
    
    .plant-link.wind {
        border-left: 4px solid #FF4136;
    }
    
    .plant-link.water {
        border-left: 4px solid #0074D9;
    }
    
    .toggle-btn {
        position: absolute;
        left: 10px;
        top: 10px;
        z-index: 999;
        background: white;
        border: none;
        border-radius: 4px;
        padding: 8px 12px;
        box-shadow: 0 0 15px rgba(0, 0, 0, 0.2);
        cursor: pointer;
    }
    
    @media (max-width: 768px) {
        .sidebar {
            width: 250px;
        }
    }
    </style>
    
    <button id="toggle-sidebar" class="toggle-btn">🔍 Search Plants</button>
    
    <div id="sidebar" class="sidebar">
        <div class="sidebar-header">
            <h3>Plant Search</h3>
            <span id="close-sidebar" class="close-btn">&times;</span>
        </div>
        <div class="sidebar-content">
            <div class="search-container">
                <input type="text" id="plant-search" placeholder="Search plants...">
            </div>
            <div class="filter-buttons">
                <div id="filter-all" class="filter-btn active">All</div>
                <div id="filter-sun" class="filter-btn">Solar</div>
                <div id="filter-wind" class="filter-btn">Wind</div>
                <div id="filter-water" class="filter-btn">Water</div>
            </div>
            <div id="plant-list">
                <!-- Plants will be listed here -->
            </div>
        </div>
    </div>
    
    <script>
    // Add event listeners when the document is loaded
    document.addEventListener('DOMContentLoaded', function() {
        // Elements
        const sidebar = document.getElementById('sidebar');
        const toggleBtn = document.getElementById('toggle-sidebar');
        const closeBtn = document.getElementById('close-sidebar');
        const searchInput = document.getElementById('plant-search');
        const plantList = document.getElementById('plant-list');
        const filterBtns = document.querySelectorAll('.filter-btn');
        
        // Get map object
        const map = document.querySelector('.folium-map')._leaflet_map;
        
        // Toggle sidebar
        toggleBtn.addEventListener('click', function() {
            sidebar.classList.add('visible');
        });
        
        // Close sidebar
        closeBtn.addEventListener('click', function() {
            sidebar.classList.remove('visible');
        });
        
        // Plant data
        const plants = [
    """
    
    # Add all plants to the JavaScript array
    for plant in all_plants:
        name = plant['name'].replace("'", "\\'")  # Escape quotes
        sidebar_html += f"""
            {{
                name: '{name}',
                lat: {plant['lat']},
                lon: {plant['lon']},
                source: '{plant['source']}',
                output: {plant['output']}
            }},
        """
    
    sidebar_html += """
        ];
        
        // Initialize plant list
        function renderPlantList() {
            const searchText = searchInput.value.toLowerCase();
            const activeFilter = document.querySelector('.filter-btn.active').id;
            
            // Filter plants
            const filteredPlants = plants.filter(plant => {
                const matchesSearch = plant.name.toLowerCase().includes(searchText);
                let matchesFilter = true;
                
                if (activeFilter === 'filter-sun') {
                    matchesFilter = plant.source === 'SUN';
                } else if (activeFilter === 'filter-wind') {
                    matchesFilter = plant.source === 'WND';
                } else if (activeFilter === 'filter-water') {
                    matchesFilter = plant.source === 'WAT';
                }
                
                return matchesSearch && matchesFilter;
            });
            
            // Sort plants by name
            filteredPlants.sort((a, b) => a.name.localeCompare(b.name));
            
            // Clear plant list
            plantList.innerHTML = '';
            
            // Add plants to list
            filteredPlants.forEach(plant => {
                const plantItem = document.createElement('div');
                plantItem.textContent = plant.name;
                plantItem.className = 'plant-link';
                
                // Add source-specific class
                if (plant.source === 'SUN') {
                    plantItem.classList.add('sun');
                } else if (plant.source === 'WND') {
                    plantItem.classList.add('wind');
                } else if (plant.source === 'WAT') {
                    plantItem.classList.add('water');
                }
                
                // Add direct zoom handler that doesn't rely on markers
                plantItem.addEventListener('click', function() {
                    // Zoom to plant location
                    map.flyTo([plant.lat, plant.lon], 13);
                    
                    // Close sidebar
                    sidebar.classList.remove('visible');
                    
                    // After a delay, find the marker
                    setTimeout(() => {
                        let found = false;
                        
                        // This part uses brute force to try to find the marker
                        document.querySelectorAll('path.leaflet-interactive').forEach(element => {
                            // Try to get position
                            try {
                                const rect = element.getBoundingClientRect();
                                const point = L.point(rect.left + rect.width/2, rect.top + rect.height/2);
                                const latlng = map.containerPointToLatLng(point);
                                
                                // If close enough
                                if (Math.abs(latlng.lat - plant.lat) < 0.01 && 
                                    Math.abs(latlng.lng - plant.lon) < 0.01 && !found) {
                                    // Click the marker
                                    element.click();
                                    found = true;
                                }
                            } catch (e) {
                                console.error('Error finding marker:', e);
                            }
                        });
                    }, 1000);
                });
                
                plantList.appendChild(plantItem);
            });
            
            // Show message if no plants found
            if (filteredPlants.length === 0) {
                const noResults = document.createElement('div');
                noResults.textContent = 'No plants found.';
                noResults.style.padding = '10px';
                noResults.style.fontStyle = 'italic';
                noResults.style.color = '#6c757d';
                plantList.appendChild(noResults);
            }
        }
        
        // Search input handler
        searchInput.addEventListener('input', renderPlantList);
        
        // Filter button handlers
        filterBtns.forEach(btn => {
            btn.addEventListener('click', function() {
                // Remove active class from all buttons
                filterBtns.forEach(b => b.classList.remove('active'));
                
                // Add active class to clicked button
                this.classList.add('active');
                
                // Update plant list
                renderPlantList();
            });
        });
        
        // Initial render
        renderPlantList();
    });
    </script>
    """
    
    # Add the sidebar HTML to the map
    energy_map.get_root().html.add_child(folium.Element(sidebar_html))
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Save the map
    energy_map.save(output_path)
    print(f"Map saved as '{output_path}'")
    
    return output_path