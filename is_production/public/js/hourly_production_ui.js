// apps/is_production/public/js/hourly_production_ui.js

frappe.provide('is_production.ui');

is_production.ui.HourlyProductionUI = class {
    constructor(frm) {
        console.log('Initializing HourlyProductionUI');
        this.frm = frm;
        this.isInitialized = false;
        this.eventNamespace = `hourlyProductionUI_${Math.random().toString(36).substr(2, 9)}`;
        this.init();
    }

    init() {
        // Prevent double initialization
        if (this.isInitialized) {
            console.log('UI already initialized, skipping');
            return;
        }

        console.log('Setting up UI');
        this.cleanup(); // Clean up any existing UI first
        this.setupEvents();
        this.loadUI();
        this.isInitialized = true;
        
        // Store reference on the form to prevent multiple instances
        this.frm._hourlyProductionUI = this;
    }

    cleanup() {
        console.log('Cleaning up existing UI');
        
        // Remove existing DOM elements
        const container = this.frm.fields_dict.dnd_html_excavator_ui.$wrapper[0];
        if (container) {
            container.innerHTML = '';
        }
        
        // Remove namespaced event listeners
        if (this.eventNamespace) {
            $(document).off(`.${this.eventNamespace}`);
        }
        
        // Clear drag and drop event listeners
        document.removeEventListener('dragend', this.stopAutoScroll);
        
        this.isInitialized = false;
    }

    setupEvents() {
        const me = this;
        const ns = this.eventNamespace;
        
        // Use namespaced events to prevent conflicts
        $(document).on(`change.${ns}`, '.truck-loads', function(e) {
            const rowName = this.getAttribute('data-row-name');
            const value = parseFloat(this.value) || 0;
            me.updateTruckField(rowName, 'loads', value);
        });

        $(document).on(`change.${ns}`, '.truck-geo-layer', function(e) {
            const rowName = this.getAttribute('data-row-name');
            const value = this.value;
            me.updateTruckField(rowName, 'geo_mat_layer_truck', value);
        });

        $(document).on(`change.${ns}`, '.dozer-production', function(e) {
            const rowName = $(this).data('dozer-name');
            const value = parseFloat(this.value) || 0;
            me.updateDozerField(rowName, 'bcm_hour', value);
        });

        $(document).on(`click.${ns}`, '.btn-remove-truck', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            // Prevent multiple clicks
            if ($(this).hasClass('processing')) {
                return;
            }
            $(this).addClass('processing');
            
            const rowName = this.getAttribute('data-row-name');
            const truckData = me.frm.doc.truck_loads.find(r => r.name === rowName);
            if (!truckData) {
                $(this).removeClass('processing');
                return;
            }

            // Save current values before unassigning
            const currentMatType = truckData.mat_type;
            const currentGeoLayer = truckData.geo_mat_layer_truck;

            // Mark document as dirty
            me.frm.dirty = true;
            me.frm.doc.__unsaved = 1;

            // Update local data immediately
            truckData.asset_name_shoval = null;
            truckData.loads = 0;
            truckData.mining_areas_trucks = null;

            Promise.all([
                frappe.model.set_value(truckData.doctype, truckData.name, 'asset_name_shoval', null),
                frappe.model.set_value(truckData.doctype, truckData.name, 'loads', 0),
                frappe.model.set_value(truckData.doctype, truckData.name, 'mining_areas_trucks', null)
            ]).then(() => {
                // Restore preserved values
                truckData.mat_type = currentMatType;
                truckData.geo_mat_layer_truck = currentGeoLayer;
                if (currentMatType) {
                    frappe.model.set_value(truckData.doctype, truckData.name, 'mat_type', currentMatType);
                }
                if (currentGeoLayer) {
                    frappe.model.set_value(truckData.doctype, truckData.name, 'geo_mat_layer_truck', currentGeoLayer);
                }

                // Create new unassigned card
                const newCardHtml = me.createTruckCard(truckData);
                const tempDiv = document.createElement('div');
                tempDiv.innerHTML = newCardHtml.trim();
                const newCardEl = tempDiv.firstChild;

                // Move to unassigned section
                const truckEl = document.querySelector(`.truck-block[data-row-name="${rowName}"]`);
                const unassigned = document.querySelector('#unassigned-trucks');
                
                if (truckEl && newCardEl && unassigned) {
                    // Remove placeholder if it exists
                    const placeholder = unassigned.querySelector('.placeholder-empty');
                    if (placeholder) {
                        placeholder.remove();
                    }
                    
                    // Replace the truck element
                    truckEl.replaceWith(newCardEl);
                    
                    // Move to unassigned container
                    unassigned.appendChild(newCardEl);
                }

                // Re-setup drag and drop for the new element
                me.setupDragAndDrop();
                
                // Refresh the child table and toolbar
                me.frm.refresh_field('truck_loads');
                me.frm.toolbar.refresh();
                
            }).catch((error) => {
                console.error('Error removing truck:', error);
                $(this).removeClass('processing');
            });
        });

        $(document).on(`change.${ns}`, '.dozer-area', function(e) {
            const dozerName = $(this).data('dozer-name');
            const value = this.value;
            me.updateDozerField(dozerName, 'mining_areas_dozer_child', value);
        });

        $(document).on(`change.${ns}`, '.dozer-service', function(e) {
            const dozerName = $(this).data('dozer-name');
            const value = this.value;
            me.updateDozerField(dozerName, 'dozer_service', value);
        });

        $(document).on(`change.${ns}`, '.dozer-geo-layer', function(e) {
            const dozerName = $(this).data('dozer-name');
            const value = this.value;
            me.updateDozerField(dozerName, 'geo_mat_layer_dozer', value);
        });

        $(document).on(`change.${ns}`, '.excavator-area', function() {
            const excavatorName = $(this).data('excavator-name');
            const area = $(this).val();
            
            // Update all trucks in this excavator block
            const container = $(this).closest('.excavator-block').find('.truck-container');
            container.find('.truck-block').each(function() {
                const rowName = $(this).data('row-name');
                me.updateTruckArea(rowName, area);
            });
            
            me.updateExcavatorDefaultArea(excavatorName, area);
        });
    }
    
    async loadUI() {
        // Prevent multiple loads
        if (this.isLoading) {
            console.log('UI already loading, skipping');
            return;
        }
        
        this.isLoading = true;
        
        // Clear existing UI
        this.frm.fields_dict.dnd_html_excavator_ui.$wrapper.empty();

        if (!this.frm.doc.location) {
            console.log('Skipping UI load - missing location');
            this.isLoading = false;
            return;
        }

        console.log('Loading UI');

        try {
            // Get all equipment at this location
            const [allExcavators, allDozers, allTrucks] = await Promise.all([
                this.getAssetsByCategory('Excavator'),
                this.getAssetsByCategory('Dozer'),
                this.getAssetsByCategory(['ADT', 'RIGID'])
            ]);

            // Create container
            const container = $(` 
                <div class="equipment-ui-container">
                    <div class="excavator-ui-section"></div>
                    <div class="dozer-ui-section"></div>
                </div>
            `);
            this.frm.fields_dict.dnd_html_excavator_ui.$wrapper.append(container);

            // Load both UIs
            this.loadExcavatorUI(allExcavators, allTrucks);
            this.loadDozersUI(allDozers);
            
        } catch (error) {
            console.error('Error loading UI:', error);
        } finally {
            this.isLoading = false;
        }
    }

    // Static method to get or create UI instance
    static getInstance(frm) {
        // Check if instance already exists and is valid
        if (frm._hourlyProductionUI && frm._hourlyProductionUI.isInitialized) {
            console.log('Returning existing UI instance');
            return frm._hourlyProductionUI;
        }
        
        // Clean up any existing instance
        if (frm._hourlyProductionUI) {
            frm._hourlyProductionUI.cleanup();
        }
        
        // Create new instance
        console.log('Creating new UI instance');
        return new is_production.ui.HourlyProductionUI(frm);
    }

    loadExcavatorUI(excavators, trucks) {
        const miningAreas = this.getMiningAreas();
        const areaOptions = miningAreas.map(area => 
            `<option value="${area}">${area}</option>`
        ).join('');

        // Create a map of trucks by excavator
        const trucksByExcavator = {};
        const unassignedTrucks = [];
        
        // Initialize with all excavators
        excavators.forEach(excavator => {
            trucksByExcavator[excavator] = [];
        });

        // Group trucks
        (this.frm.doc.truck_loads || []).forEach(truck => {
            if (truck.asset_name_shoval && trucksByExcavator[truck.asset_name_shoval]) {
                trucksByExcavator[truck.asset_name_shoval].push(truck);
            } else {
                unassignedTrucks.push(truck);
            }
        });

        // Generate HTML for ALL excavators
        let assignedHtml = '';
        excavators.forEach(excavator => {
            const trucks = trucksByExcavator[excavator] || [];
            let currentArea = '';
            
            // Try to find an area from assigned trucks
            if (trucks.length > 0) {
                const truckWithArea = trucks.find(t => t.mining_areas_trucks);
                currentArea = truckWithArea ? truckWithArea.mining_areas_trucks : '';
            }

            assignedHtml += `
                <div class="excavator-block" data-excavator-name="${excavator}">
                    <div class="excavator-header">
                        <img src="/assets/is_production/images/excavator (1).png" class="excavator-icon">
                        <h4>${excavator}</h4>
                        <div class="excavator-area-selector">
                            <label>Primary Area:</label>
                            <select class="form-control excavator-area" 
                                    data-excavator-name="${excavator}">
                                <option value="">Select Area</option>
                                ${areaOptions}
                                ${currentArea ? `<option value="${currentArea}" selected>${currentArea}</option>` : ''}
                            </select>
                        </div>
                    </div>
                    <div class="truck-container" id="excavator-${excavator.replace(/\s+/g, '-')}">
                        ${trucks.map(truck => this.createTruckCard(truck)).join('')}
                        ${trucks.length === 0 ? '<div class="placeholder-empty">Drop trucks here</div>' : ''}
                    </div>
                </div>
            `;
        });

        // Generate HTML for unassigned trucks
        const unassignedHtml = `
            <div class="excavator-block">
                <div class="excavator-header">
                    <img src="/assets/is_production/images/mining-truck.png" class="truck-icon">
                    <h4>Unassigned Trucks</h4>
                </div>
                <div class="truck-container" id="unassigned-trucks">
                    ${unassignedTrucks.map(truck => this.createTruckCard(truck)).join('')}
                    ${unassignedTrucks.length === 0 ? '<div class="placeholder-empty">No unassigned trucks</div>' : ''}
                </div>
            </div>
        `;

        // Set HTML
        const fullHtml = `
            <div class="dnd-ui-container">
                <div class="assigned-excavators">
                    ${assignedHtml}
                </div>
                <div class="unassigned-trucks">
                    ${unassignedHtml}
                </div>
            </div>
        `;

        this.frm.fields_dict.dnd_html_excavator_ui.$wrapper.find('.excavator-ui-section').html(fullHtml);
        this.setupDragAndDrop();
        this.setupAreaSelectors();
    }

    loadDozersUI(dozerNames) {
        if (!this.frm.doc.location) {
            console.log('Skipping Dozers UI - no location specified');
            return;
        }

        console.log('Loading Dozers UI');
        this.renderDozersUI(dozerNames);
    }

  renderDozersUI(dozerNames) {
    // Pull dozer service options from DocField meta
    const dozerServiceField = frappe.meta.get_docfield('Dozer Production', 'dozer_service');
    const serviceOptions = dozerServiceField?.options?.split('\n').filter(Boolean) || [];

    // Get mining areas for area dropdown
    const miningAreas = this.getMiningAreas();
    const areaOptions = miningAreas.map(area =>
        `<option value="${area}">${area}</option>`
    ).join('');

    // Get geo layer options
    const geoOptions = this.frm.dozer_geo_options_str ?
        this.frm.dozer_geo_options_str.split('\n').filter(Boolean) : [];
    const geoLayerOptions = geoOptions.map(option =>
        `<option value="${option}">${option}</option>`
    ).join('');

    let dozersHtml = `
        <div class="dozer-section">
            <h3 class="dozer-section-title">
                Dozers<img src="/assets/is_production/images/dozer.png" class="dozer-icon">
            </h3>
            <div class="dozer-container">
    `;

    dozerNames.forEach(dozerName => {
        const dozerData = this.frm.doc.dozer_production?.find(d => d.asset_name === dozerName) || {};

        const serviceOptionsHtml = // In renderDozersUI, replace the service options part with:
        `
            <option value="No Dozing" ${dozerData.dozer_service === 'No Dozing' ? 'selected' : ''}>No Dozing</option>
            <option value="Tip Dozing" ${dozerData.dozer_service === 'Tip Dozing' ? 'selected' : ''}>Tip Dozing</option>
            <option value="Production Dozing-50m" ${dozerData.dozer_service === 'Production Dozing-50m' ? 'selected' : ''}>Production Dozing-50m</option>
            <option value="Production Dozing-100m" ${dozerData.dozer_service === 'Production Dozing-100m' ? 'selected' : ''}>Production Dozing-100m</option>
            <option value="Levelling" ${dozerData.dozer_service === 'Levelling' ? 'selected' : ''}>Levelling</option>
        `;

        dozersHtml += `
            <div class="dozer-block" data-dozer-name="${dozerName}">
                <div class="dozer-header">
                    <div class="dozer-name">${dozerName}<img src="/assets/is_production/images/dozer.png" class="dozer-img"></div>
                </div>
                <div class="dozer-fields-row">
                    <div class="dozer-field">
                        <label>Service</label>
                        <select class="form-control dozer-service" data-dozer-name="${dozerName}">
                            ${serviceOptionsHtml}
                        </select>
                    </div>
                    <div class="dozer-field">
                <label>BCM/Hour</label>
                        <input type="number"
                            class="form-control dozer-production"
                            value="${dozerData.bcm_hour || 0}"
                            data-dozer-name="${dozerName}"
                            readonly
                            disabled>
                    </div>
                    <div class="dozer-field">
                        <label>Primary Working Area</label>
                        <select class="form-control dozer-area" data-dozer-name="${dozerName}">
                            <option value="">Select Area</option>
                            ${areaOptions}
                            ${dozerData.mining_areas_dozer_child ? `<option value="${dozerData.mining_areas_dozer_child}" selected>${dozerData.mining_areas_dozer_child}</option>` : ''}
                        </select>
                    </div>
                    <div class="dozer-field">
                        <label>Geo / Mat Layer</label>
                        <select class="form-control dozer-geo-layer" data-dozer-name="${dozerName}">
                            <option value="">Select Geo Layer</option>
                            ${geoLayerOptions}
                            ${dozerData.dozer_geo_mat_layer ? `<option value="${dozerData.dozer_geo_mat_layer}" selected>${dozerData.dozer_geo_mat_layer}</option>` : ''}
                        </select>
                    </div>
                </div>
            </div>
        `;
    });

    dozersHtml += `
            </div>
        </div>
    `;

    this.frm.fields_dict.dnd_html_excavator_ui.$wrapper.find('.dozer-ui-section').html(dozersHtml);

    // Rebind UI event handlers
    this.setupDozerEvents();
}


    getAssetsByCategory(category) {
        return new Promise((resolve) => {
            frappe.call({
                method: 'frappe.client.get_list',
                args: {
                    doctype: 'Asset',
                    fields: ['asset_name'],
                    filters: {
                        location: this.frm.doc.location,
                        asset_category: Array.isArray(category) ? ['in', category] : ['=', category],
                        docstatus: 1
                    },
                    order_by: 'asset_name asc'
                },
                callback: (r) => {
                    resolve(r.message ? r.message.map(e => e.asset_name) : []);
                }
            });
        });
    }

    createTruckCard(truck) {
    const isAssigned = !!truck.asset_name_shoval;
    console.log('Creating truck card for:', truck.asset_name_truck, 'isAssigned:', isAssigned, 'excavator:', truck.asset_name_shoval);
    
    const geoOptions = this.frm.truck_geo_options_str ? 
        this.frm.truck_geo_options_str.split('\n').filter(Boolean) : [];

    let optionsHtml = geoOptions.map(option => {
        const selected = option === truck.geo_mat_layer_truck ? 'selected' : '';
        return `<option value="${option}" ${selected}>${option}</option>`;
    }).join('');

    let areaHtml = '';
   
    return `
        <div class="truck-block" 
             data-truck-name="${truck.asset_name_truck}" 
             data-row-name="${truck.name}"
             draggable="true">
             
            <div class="truck-header">
                <img src="/assets/is_production/images/mining-truck.png" class="truck-icon">
                <div class="truck-name">${truck.asset_name_truck}</div>
                ${isAssigned ? `
                    <button type="button" class="btn-remove-truck" 
                            title="Move to Unassigned" data-row-name="${truck.name}">
                        ✖
                    </button>
                ` : ''}
            </div>

            ${isAssigned ? `
                <div class="truck-fields-row">
                    <div class="truck-field">
                        <label>Loads</label>
                        <input type="number" 
                               class="form-control truck-loads" 
                               value="${truck.loads || 0}" 
                               data-row-name="${truck.name}"
                               min="0" step="0.1">
                    </div>
                    
                    <div class="truck-field">
                        <label>Geo Layer</label>
                        <select class="form-control truck-geo-layer" data-row-name="${truck.name}">
                            <option value="">Select Geo Layer</option>
                            ${optionsHtml}
                        </select>
                    </div>
                    
                    ${areaHtml}
                </div>
            ` : ''}
        </div>
    `;
}
    setupDozerEvents() {
    const me = this;

    $(document).on('change', '.dozer-service', function () {
        const name = $(this).data('dozer-name');
        const value = this.value;
        me.updateDozerField(name, 'dozer_service', value);
    });

    $(document).on('change', '.dozer-production', function () {
        const name = $(this).data('dozer-name');
        const value = parseInt(this.value) || 0;
        me.updateDozerField(name, 'bcm_hour', value);
    });

    $(document).on('change', '.dozer-area', function () {
        const name = $(this).data('dozer-name');
        const value = this.value;
        me.updateDozerField(name, 'mining_areas_dozer_child', value);
    });

    $(document).on('change', '.dozer-geo-layer', function () {
        const name = $(this).data('dozer-name');
        const value = this.value;
        me.updateDozerField(name, 'dozer_geo_mat_layer', value);

        // Automatically set mat_type if map exists
        if (me.frm.geoMaterialMap && me.frm.geoMaterialMap[value]) {
            me.updateDozerField(name, 'mat_type', me.frm.geoMaterialMap[value]);
        }
    });
}

   

    setupDragAndDrop() {
    console.log('Setting up drag and drop');
    const truckBlocks = document.querySelectorAll('.truck-block');
    const containers = document.querySelectorAll('.truck-container');
    
    // Auto-scroll variables
    let scrollInterval = null;
    const scrollSpeed = 10; // pixels per interval
    const scrollZone = 50; // pixels from edge to trigger scrolling
    
    // Auto-scroll function
    const autoScroll = (e) => {
        const viewportHeight = window.innerHeight;
        const mouseY = e.clientY;
        
        // Clear existing interval
        if (scrollInterval) {
            clearInterval(scrollInterval);
            scrollInterval = null;
        }
        
        // Check if we're in the scroll zones
        if (mouseY < scrollZone) {
            // Scroll up
            scrollInterval = setInterval(() => {
                window.scrollBy(0, -scrollSpeed);
            }, 16); // ~60fps
        } else if (mouseY > viewportHeight - scrollZone) {
            // Scroll down
            scrollInterval = setInterval(() => {
                window.scrollBy(0, scrollSpeed);
            }, 16); // ~60fps
        }
    };
    
    // Stop auto-scroll function
    const stopAutoScroll = () => {
        if (scrollInterval) {
            clearInterval(scrollInterval);
            scrollInterval = null;
        }
    };

    truckBlocks.forEach(truck => {
        truck.addEventListener('dragstart', (e) => {
            truck.classList.add('dragging');
            // Store initial mouse position
            truck.dataset.initialY = e.clientY;
        });

        truck.addEventListener('drag', (e) => {
            // Only auto-scroll if we're actually dragging (mouse moved)
            if (e.clientY !== 0) { // clientY is 0 when drag ends
                autoScroll(e);
            }
        });

        truck.addEventListener('dragend', async (e) => {
    truck.classList.remove('dragging');
    stopAutoScroll(); // Stop scrolling when drag ends
    
    const rowName = truck.getAttribute('data-row-name');
    const rowData = this.frm.doc.truck_loads.find(r => r.name === rowName);
    if (!rowData) return;

    const newContainer = truck.parentElement.closest('.excavator-block');
    const newExcavator = newContainer?.querySelector('h4')?.textContent || null;
    const isNowUnassigned = newExcavator === 'Unassigned Trucks';
    
    // Save current values before changing
    const currentMatType = rowData.mat_type;
    const currentGeoLayer = rowData.geo_mat_layer_truck;

    // Mark document as dirty before making changes
    this.frm.dirty = true;
    this.frm.doc.__unsaved = 1;

    if (isNowUnassigned) {
        // Update the local data first
        rowData.asset_name_shoval = null;
        rowData.loads = 0;
        rowData.mining_areas_trucks = null;
        
        // Then update the server
        await Promise.all([
            frappe.model.set_value(rowData.doctype, rowData.name, 'asset_name_shoval', null),
            frappe.model.set_value(rowData.doctype, rowData.name, 'loads', 0),
            frappe.model.set_value(rowData.doctype, rowData.name, 'mining_areas_trucks', null)
        ]);
        
        // Restore preserved values
        rowData.mat_type = currentMatType;
        rowData.geo_mat_layer_truck = currentGeoLayer;
        if (currentMatType) {
            frappe.model.set_value(rowData.doctype, rowData.name, 'mat_type', currentMatType);
        }
        if (currentGeoLayer) {
            frappe.model.set_value(rowData.doctype, rowData.name, 'geo_mat_layer_truck', currentGeoLayer);
        }
    } else {
        // Get the excavator's primary area from its dropdown
        const excavatorAreaSelect = newContainer.querySelector('.excavator-area');
        const excavatorArea = excavatorAreaSelect ? excavatorAreaSelect.value : null;

        // Update the local data first
        rowData.asset_name_shoval = newExcavator;
        if (excavatorArea) {
            rowData.mining_areas_trucks = excavatorArea;
        }
        
        // Then update the server
        await Promise.all([
            frappe.model.set_value(rowData.doctype, rowData.name, 'asset_name_shoval', newExcavator),
            excavatorArea && frappe.model.set_value(rowData.doctype, rowData.name, 'mining_areas_trucks', excavatorArea)
        ]);
    }

    // Refresh the child table to show changes
    this.frm.refresh_field('truck_loads');
    
    // Update the toolbar to show save button
    this.frm.toolbar.refresh();

    // Now create the new card with the updated data
    const newCardHtml = this.createTruckCard(rowData);
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = newCardHtml.trim();
    const newCardEl = tempDiv.firstChild;
    truck.replaceWith(newCardEl);

    // Remove placeholder if needed
    document.querySelectorAll('.placeholder-empty').forEach(placeholder => {
        if (placeholder.parentElement.querySelector('.truck-block')) {
            placeholder.remove();
        }
    });

    // Re-setup drag and drop for the new element
    this.setupDragAndDrop();
    this.updateExcavatorAssignments();
});
    });

    containers.forEach(container => {
        container.addEventListener('dragover', e => {
            e.preventDefault();
            
            // Continue auto-scrolling during dragover
            autoScroll(e);
            
            const dragging = document.querySelector('.dragging');
            if (dragging && !container.contains(dragging)) {
                container.appendChild(dragging);
            }
        });
        
        container.addEventListener('dragleave', () => {
            // Don't stop scrolling on dragleave as it fires frequently
            // Only stop on dragend
        });
        
        container.style.minHeight = '40px';
    });
    
    // Add global dragend listener to ensure scrolling stops
    document.addEventListener('dragend', stopAutoScroll);
}

   updateDozerField(dozerName, fieldname, value) {
    const row = this.frm.doc.dozer_production?.find(d => d.asset_name === dozerName);
    if (row) {
        frappe.model.set_value(row.doctype, row.name, fieldname, value);

        if (fieldname === 'dozer_geo_mat_layer' && this.frm.geoMaterialMap && this.frm.geoMaterialMap[value]) {
            frappe.model.set_value(row.doctype, row.name, 'mat_type', this.frm.geoMaterialMap[value]);
        }
        
        // Add this new logic for service type changes
        if (fieldname === 'dozer_service') {
            this.handleDozerServiceChange(row);
        }
    }
    }



    getMiningAreas() {
        return (this.frm.doc.mining_areas_options || []).map(r => r.mining_areas).filter(v => v);
    }

    getDefaultAreaForExcavator(excavator) {
        // Implement custom logic for default areas if needed
        return '';
    }

    setupAreaSelectors() {
        const me = this;
        
        $(document).on('change', '.excavator-area', function() {
            const excavatorName = $(this).data('excavator-name');
            const area = $(this).val();
            
            // Update all trucks in this excavator block
            const container = $(this).closest('.excavator-block').find('.truck-container');
            container.find('.truck-block').each(function() {
                const rowName = $(this).data('row-name');
                me.updateTruckArea(rowName, area);
            });
            
            me.updateExcavatorDefaultArea(excavatorName, area);
        });
    }

    updateTruckArea(rowName, area) {
        const row = this.frm.doc.truck_loads.find(r => r.name === rowName);
        if (row) {
            // Update the local data immediately
            row.mining_areas_trucks = area;
            
            // Mark the document as dirty
            this.frm.dirty = true;
            this.frm.doc.__unsaved = 1;
            
            // Use frappe.model.set_value to properly register the change
            frappe.model.set_value(row.doctype, row.name, 'mining_areas_trucks', area);
            
            // Update UI immediately
            const truckBlock = $(`.truck-block[data-row-name="${rowName}"]`);
            if (truckBlock.length) {
                const areaHtml = area ? `<div class="truck-area">Area: ${area}</div>` : '';
                truckBlock.find('.truck-area').remove();
                if (area) {
                    truckBlock.find('.truck-fields').append(areaHtml);
                }
            }
            
            // Refresh the child table field to show changes
            this.frm.refresh_field('truck_loads');
            
            // Update the toolbar to show save button
            this.frm.toolbar.refresh();
        }
    }

    updateExcavatorDefaultArea(excavatorName, area) {
        console.log(`Excavator ${excavatorName} primary area set to ${area}`);
        
        // Mark the document as dirty when excavator area changes
        this.frm.dirty = true;
        this.frm.doc.__unsaved = 1;
        
        // Update the toolbar to show save button
        this.frm.toolbar.refresh();
        
        // Can be extended to store default areas if needed
    }

    updateExcavatorAssignments() {
        console.log('Updating excavator assignments');
        const assignments = {};
        
        document.querySelectorAll('.excavator-block').forEach(block => {
            const excavatorName = block.querySelector('h4').textContent;
            if (excavatorName !== 'Unassigned Trucks') {
                block.querySelectorAll('.truck-block').forEach(truck => {
                    const truckName = truck.getAttribute('data-truck-name');
                    assignments[truckName] = excavatorName;
                });
            }
        });

        this.frm.doc.truck_loads.forEach(row => {
            const newExcavator = assignments[row.asset_name_truck];
            if (newExcavator && newExcavator !== row.asset_name_shoval) {
                frappe.model.set_value(row.doctype, row.name, 'asset_name_shoval', newExcavator);
            } else if (!newExcavator && row.asset_name_shoval) {
                frappe.model.set_value(row.doctype, row.name, 'asset_name_shoval', null);
            }
        });
        
        this.frm.refresh_field('truck_loads');
    }

   updateTruckField(rowName, fieldname, value) {
        const row = this.frm.doc.truck_loads.find(r => r.name === rowName);
        if (row) {
            // Update the local data immediately
            row[fieldname] = value;
            
            // Mark the document as dirty
            this.frm.dirty = true;
            this.frm.doc.__unsaved = 1;
            
            // Use frappe.model.set_value to properly register the change
            frappe.model.set_value(row.doctype, row.name, fieldname, value);
            
            // Handle geo layer material mapping
            if (fieldname === 'geo_mat_layer_truck' && this.frm.geoMaterialMap && this.frm.geoMaterialMap[value]) {
                const matType = this.frm.geoMaterialMap[value];
                row.mat_type = matType;
                frappe.model.set_value(row.doctype, row.name, 'mat_type', matType);
            }
            
            // Calculate BCMS if loads changed
            if (fieldname === 'loads') {
                this.calculateBCMS(row.doctype, row.name);
            }
            
            // Refresh the child table field to show changes
            this.frm.refresh_field('truck_loads');
            
            // Update the toolbar to show save button
            this.frm.toolbar.refresh();
        }
    }


updateDozerField(dozerName, fieldname, value) {
        const row = this.frm.doc.dozer_production?.find(d => d.asset_name === dozerName);
        if (row) {
            // Update the local data immediately
            row[fieldname] = value;
            
            // Mark the document as dirty
            this.frm.dirty = true;
            this.frm.doc.__unsaved = 1;
            
            // Use frappe.model.set_value to properly register the change
            frappe.model.set_value(row.doctype, row.name, fieldname, value);

            // Handle geo layer material mapping
            if (fieldname === 'dozer_geo_mat_layer' && this.frm.geoMaterialMap && this.frm.geoMaterialMap[value]) {
                const matType = this.frm.geoMaterialMap[value];
                row.mat_type = matType;
                frappe.model.set_value(row.doctype, row.name, 'mat_type', matType);
            }
            
            // Handle service type changes
            if (fieldname === 'dozer_service') {
                this.handleDozerServiceChange(row);
            }
            
            // Refresh the child table field to show changes
            this.frm.refresh_field('dozer_production');
            
            // Update the toolbar to show save button
            this.frm.toolbar.refresh();
        }
    }

calculateBCMS(doctype, name) {
    const row = this.frm.doc.truck_loads.find(r => r.name === name);
    if (row) {
        const loads = parseFloat(row.loads) || 0;
        const tf = parseFloat(row.tub_factor) || 0;
        const bcms = (!isNaN(loads) && !isNaN(tf)) ? loads * tf : 0;
        
        // Update local data
        row.bcms = bcms;
        
        // Mark document as dirty
        this.frm.dirty = true;
        this.frm.doc.__unsaved = 1;
        
        // Use frappe.model.set_value to register the change
        frappe.model.set_value(doctype, name, 'bcms', bcms);
        
        // Refresh the field
        this.frm.refresh_field('truck_loads');
        this.frm.toolbar.refresh();
    }
}

    // Add this to your HourlyProductionUI class
    // Inside your class definition (after all other methods), add:
    cleanup() {
    // Remove any DOM elements or event listeners your UI created
    const container = this.frm.fields_dict.dnd_html_excavator_ui.$wrapper[0];
    if (container) {
        container.innerHTML = '';
    }
    
    // Clear any jQuery event handlers
    $(document).off('.hourlyProductionUI');
    
    // Clear any other references
    this.container = null;
    // Add any other cleanup needed for your specific UI
    }

    // Add this new method to the class:
   // Replace the existing handleDozerServiceChange method with this updated version:

async handleDozerServiceChange(row) {
    if (!this.frm.doc.month_prod_planning) return;
    
    // Get the dozing_tempo from Monthly Production Planning
    const mpp = await frappe.db.get_value('Monthly Production Planning', 
        this.frm.doc.month_prod_planning, 'dozing_tempo');
        
    const dozingTempo = mpp.message.dozing_tempo || 0;
    let bcmValue = 0;
    
    switch(row.dozer_service) {
        case 'Production Dozing-50m':
        case 'Production Dozing-100m':
            bcmValue = dozingTempo;
            break;
        case 'No Dozing':
        case 'Tip Dozing':
        case 'Levelling':
        default:
            bcmValue = 0;
    }
    
    // Update local data
    row.bcm_hour = bcmValue;
    
    // If "No Dozing" is selected, reset geo layer and area to default
    if (row.dozer_service === 'No Dozing') {
        row.dozer_geo_mat_layer = '';
        row.mining_areas_dozer_child = '';
        row.mat_type = '';
        
        // Update the server with reset values
        frappe.model.set_value(row.doctype, row.name, 'dozer_geo_mat_layer', '');
        frappe.model.set_value(row.doctype, row.name, 'mining_areas_dozer_child', '');
        frappe.model.set_value(row.doctype, row.name, 'mat_type', '');
        
        // Update the UI dropdowns
        const dozerBlock = $(`.dozer-block[data-dozer-name="${row.asset_name}"]`);
        if (dozerBlock.length) {
            dozerBlock.find('.dozer-geo-layer').val('');
            dozerBlock.find('.dozer-area').val('');
        }
    }
    
    // Mark document as dirty
    this.frm.dirty = true;
    this.frm.doc.__unsaved = 1;
    
    // Use frappe.model.set_value to register the change
    frappe.model.set_value(row.doctype, row.name, 'bcm_hour', bcmValue);

    // Update the UI field
    const dozerBlock = $(`.dozer-block[data-dozer-name="${row.asset_name}"]`);
    if (dozerBlock.length) {
        dozerBlock.find('.dozer-production').val(bcmValue);
    }
    
    // Refresh the child table field to show changes
    this.frm.refresh_field('dozer_production');
    
    // Update the toolbar to show save button
    this.frm.toolbar.refresh();
}

    

     calculateBCMS(doctype, name) {
        const row = this.frm.doc.truck_loads.find(r => r.name === name);
        if (row) {
            const loads = parseFloat(row.loads) || 0;
            const tf = parseFloat(row.tub_factor) || 0;
            const bcms = (!isNaN(loads) && !isNaN(tf)) ? loads * tf : 0;
            
            // Update local data
            row.bcms = bcms;
            
            // Mark document as dirty
            this.frm.dirty = true;
            this.frm.doc.__unsaved = 1;
            
            // Use frappe.model.set_value to register the change
            frappe.model.set_value(doctype, name, 'bcms', bcms);
            
            // Refresh the field
            this.frm.refresh_field('truck_loads');
            this.frm.toolbar.refresh();
        }
    }
};

console.log('HourlyProductionUI class registered');