// Function to zoom to a plant location
function zoomToPlant(lat, lon) {
    var mymap = Object.values(window).find(function(item) {
        return item && item._container && item._container.classList && item._container.classList.contains('leaflet-container');
    });
    if (mymap) {
        mymap.setView([lat, lon], 12);
    }
}

// Toggle search container visibility
document.getElementById('searchToggle').addEventListener('click', function() {
    var container = document.getElementById('searchContainer');
    container.classList.toggle('collapsed');
});

// Filter plants as user types in search box
document.getElementById('plantSearch').addEventListener('input', function() {
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