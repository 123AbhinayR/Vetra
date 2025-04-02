import folium
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
    
    # Add layer control
    folium.LayerControl(collapsed=False).add_to(energy_map)
    
    # Create search control HTML
    search_html = """
    <style>
    .search-container {
        position: absolute;
        top: 100px;
        left: 12px;
        z-index: 1000;
        background: white;
        padding: 10px;
        border-radius: 5px;
        box-shadow: 0 0 10px rgba(0,0,0,0.2);
        max-width: 300px;
        max-height: 400px;
        overflow-y: auto;
        transition: transform 0.3s ease-in-out;
    }
    .search-container.collapsed {
        transform: translateX(-120%);
    }
    .search-toggle {
        position: absolute;
        top: 17px;
        left: 60px;
        width: 50px;
        height: 50px;
        background: #007bff;
        color: white;
        font-size: 24px;
        font-weight: bold;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        box-shadow: 0 0 5px rgba(0,0,0,0.2);
        z-index: 1001; /* Ensure the button is above other elements */
    }
    .search-box {
        width: 100%;
        padding: 5px;
        margin-bottom: 10px;
        border: 1px solid #ccc;
        border-radius: 3px;
    }
    .plant-list {
        list-style-type: none;
        padding: 0;
        margin: 0;
    }
    .plant-item {
        padding: 5px;
        cursor: pointer;
        border-bottom: 1px solid #eee;
    }
    .plant-item:hover {
        background-color: #f0f0f0;
    }
    .source-SUN {
        border-left: 4px solid yellow;
    }
    .source-WND {
        border-left: 4px solid red;
    }
    .source-WAT {
        border-left: 4px solid blue;
    }
    </style>
    
    <div class="search-toggle" id="searchToggle">☰</div>
    <div class="search-container collapsed" id="searchContainer">
        <input type="text" id="plantSearch" class="search-box" placeholder="Search plants...">
        <ul class="plant-list" id="plantList">
    """
    
    # Add plant items to the search
    for _, plant in data.iterrows():
        plant_name = str(plant['PlantName'])
        source = plant['PriEnergySource']
        output = plant['estimated_output']
        lat = plant['y']
        lon = plant['x']
        
        search_html += f"""
        <li class="plant-item source-{source}" 
            onclick="zoomToPlant({lat}, {lon})" 
            data-name="{plant_name.lower()}" 
            data-source="{source}">
            {plant_name} ({source}) - {output:.1f} MW
        </li>
        """
    
    # Close the list and container
    search_html += """
        </ul>
    </div>
    """
    
    # Add JavaScript for the search functionality
    search_js = """
    <script>
    // Function to zoom to a plant location
    function zoomToPlant(lat, lon) {
        console.log("Zoom function called with coordinates:", lat, lon);
        
        // Find the map object
        var mymap = Object.values(window).find(function(item) {
            return item && item._container && item._container.classList && 
                   item._container.classList.contains('leaflet-container');
        });
        
        if (mymap) {
            console.log("Map found, zooming to location");
            mymap.setView([lat, lon], 12);
            
            // Try to find and open popup for marker at this location
            setTimeout(function() {
                console.log("Searching for marker at location");
                mymap.eachLayer(function(layer) {
                    if (layer._latlng) {
                        var d = Math.sqrt(
                            Math.pow(layer._latlng.lat - lat, 2) + 
                            Math.pow(layer._latlng.lng - lon, 2)
                        );
                        
                        // If distance is very small (close to exact match)
                        if (d < 0.0001) {
                            console.log("Found marker, opening popup");
                            if (layer.openPopup) {
                                layer.openPopup();
                            }
                        }
                    }
                });
            }, 500);
        } else {
            console.error("Map not found");
        }
    }
    
    // Toggle search container visibility
    document.addEventListener('DOMContentLoaded', function() {
        // Get elements
        var searchToggle = document.getElementById('searchToggle');
        var searchContainer = document.getElementById('searchContainer');
        var plantSearch = document.getElementById('plantSearch');
        
        if (searchToggle && searchContainer) {
            searchToggle.addEventListener('click', function() {
                console.log("Search toggle clicked");
                searchContainer.classList.toggle('collapsed');
                if (!searchContainer.classList.contains('collapsed')) {
                    plantSearch.focus();
                }
            });
        } else {
            console.error("Search toggle or container not found");
        }
        
        // Filter plants as user types in search box
        if (plantSearch) {
            plantSearch.addEventListener('input', function() {
                var searchTerm = this.value.toLowerCase();
                var items = document.querySelectorAll('#plantList .plant-item');
                
                items.forEach(function(item) {
                    var name = item.getAttribute('data-name');
                    if (name.includes(searchTerm)) {
                        item.style.display = '';
                    } else {
                        item.style.display = 'none';
                    }
                });
            });
        }
        
        // Ensure map is accessible
        setTimeout(function() {
            window.energyMap = Object.values(window).find(function(item) {
                return item && item._container && item._container.classList && 
                       item._container.classList.contains('leaflet-container');
            });
            
            if (window.energyMap) {
                console.log("Map reference stored globally");
            } else {
                console.error("Could not store map reference");
            }
        }, 1000);
    });
    </script>
    """
    
    # Add the search control to the map
    energy_map.get_root().html.add_child(folium.Element(search_html + search_js))
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Save the map
    energy_map.save(output_path)
    print(f"Map saved as '{output_path}'")
    
    return output_path