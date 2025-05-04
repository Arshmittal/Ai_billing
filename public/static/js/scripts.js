// static/js/scripts.js
document.addEventListener('DOMContentLoaded', function() {
    // Initialize signature pad
    const canvas = document.querySelector('#signature-pad canvas');
    const signaturePad = new SignaturePad(canvas, {
        backgroundColor: 'rgb(255, 255, 255)',
        penColor: 'rgb(0, 0, 0)'
    });
    
    // Handle window resize
    window.addEventListener('resize', resizeCanvas);
    
    function resizeCanvas() {
        const ratio = Math.max(window.devicePixelRatio || 1, 1);
        canvas.width = canvas.offsetWidth * ratio;
        canvas.height = canvas.offsetHeight * ratio;
        canvas.getContext('2d').scale(ratio, ratio);
        signaturePad.clear(); // Otherwise isEmpty() might return incorrect value
    }
    
    resizeCanvas();
    
    // Clear signature button
    document.getElementById('clear-signature').addEventListener('click', function() {
        signaturePad.clear();
    });
    
    // Handle form submission
    document.getElementById('accept_btn').addEventListener('click', function() {
        if (signaturePad.isEmpty()) {
            alert('Please provide a signature');
            return;
        }
        
        if (!document.getElementById('agree_checkbox').checked) {
            alert('Please check the agreement checkbox');
            return;
        }
        
        // Create form data with all fields
        const formData = collectFormData();
        formData.append('signature', signaturePad.toDataURL());
        
        // Preview the PDF
        previewDocument(formData);
    });
    
    // Generate and download PDF
    document.getElementById('generate_btn').addEventListener('click', function() {
        // Create form data with all fields
        const formData = collectFormData();
        
        if (!signaturePad.isEmpty()) {
            formData.append('signature', signaturePad.toDataURL());
        }
        
        generatePdf(formData);
    });
    
    // Clear form
    document.getElementById('clear_btn').addEventListener('click', function() {
        document.getElementById('program_name').value = '';
        document.getElementById('print_name_title').value = '';
        document.getElementById('date_review').value = '';
        document.getElementById('date_revision').value = '';
        document.getElementById('agree_checkbox').checked = false;
        signaturePad.clear();
    });
    
    // Helper function to collect form data
    function collectFormData() {
        const formData = new FormData();
        formData.append('client_name', document.getElementById('client_name').value);
        formData.append('document_type', document.getElementById('document_type').value);
        formData.append('program_name', document.getElementById('program_name').value);
        formData.append('print_name_title', document.getElementById('print_name_title').value);
        formData.append('date_review', document.getElementById('date_review').value);
        formData.append('date_revision', document.getElementById('date_revision').value);
        return formData;
    }
    
    // Preview document function
    function previewDocument(formData) {
        fetch('/preview_pdf', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok: ' + response.statusText);
            }
            return response.text();
        })
        .then(html => {
            // Create a new window with the preview
            const previewWindow = window.open('', '_blank');
            previewWindow.document.write(html);
            previewWindow.document.close();
        })
        .catch(error => {
            console.error('Error previewing document:', error);
            alert('Error previewing document: ' + error.message);
        });
    }
    
    // Generate PDF function
    function generatePdf(formData) {
        // Using form submission approach for file download
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = '/generate_pdf';
        form.target = '_blank';
        
        for (const [key, value] of formData.entries()) {
            const input = document.createElement('input');
            input.type = 'hidden';
            input.name = key;
            input.value = value;
            form.appendChild(input);
        }
        
        document.body.appendChild(form);
        form.submit();
        document.body.removeChild(form);
    }
});


document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
    const pdfTab = document.getElementById('pdf-tab');
    const manualTab = document.getElementById('manual-tab');
    const pdfSection = document.getElementById('pdf-section');
    const manualSection = document.getElementById('manual-section');
    const resultsSection = document.getElementById('results-section');
    const pdfForm = document.getElementById('pdf-form');
    const manualForm = document.getElementById('manual-form');
    const resultsBody = document.getElementById('results-body');
    const loadingOverlay = document.getElementById('loading-overlay');
    const printBtn = document.getElementById('print-btn');
    const exportPdfBtn = document.getElementById('export-pdf-btn');
    const newEntryBtn = document.getElementById('new-entry-btn');

    // Tab switching
    pdfTab.addEventListener('click', () => {
        pdfTab.classList.add('active');
        manualTab.classList.remove('active');
        pdfSection.classList.add('section-active');
        pdfSection.classList.remove('section-hidden');
        manualSection.classList.add('section-hidden');
        manualSection.classList.remove('section-active');
    });

    manualTab.addEventListener('click', () => {
        manualTab.classList.add('active');
        pdfTab.classList.remove('active');
        manualSection.classList.add('section-active');
        manualSection.classList.remove('section-hidden');
        pdfSection.classList.add('section-hidden');
        pdfSection.classList.remove('section-active');
    });

    // PDF Form Submission
    pdfForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        loadingOverlay.classList.remove('loading-hidden');
        
        const formData = new FormData(pdfForm);
        try {
            const response = await fetch('http://localhost:5000/api/extract-pdf', {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                throw new Error('Server responded with an error');
            }
            
            const data = await response.json();
            displayResults(data);
            
            // Switch to results section
            pdfSection.classList.add('section-hidden');
            pdfSection.classList.remove('section-active');
            resultsSection.classList.add('section-active');
            resultsSection.classList.remove('section-hidden');
            
        } catch (error) {
            console.error('Error:', error);
            alert('Error processing PDF. Please try again.');
        } finally {
            loadingOverlay.classList.add('loading-hidden');
        }
    });

    // Manual Form Submission
    manualForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        loadingOverlay.classList.remove('loading-hidden');
        
        // Gather form data
        const formData = new FormData(manualForm);
        const jsonData = {};
        
        formData.forEach((value, key) => {
            jsonData[key] = value;
        });
        
        try {
            const response = await fetch('http://localhost:5000/api/manual-entry', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(jsonData)
            });
            
            if (!response.ok) {
                throw new Error('Server responded with an error');
            }
            
            const data = await response.json();
            displayResults(data);
            
            // Switch to results section
            manualSection.classList.add('section-hidden');
            manualSection.classList.remove('section-active');
            resultsSection.classList.add('section-active');
            resultsSection.classList.remove('section-hidden');
            
        } catch (error) {
            console.error('Error:', error);
            alert('Error saving data. Please try again.');
        } finally {
            loadingOverlay.classList.add('loading-hidden');
        }
    });

    // Display results in the table
    function displayResults(data) {
        resultsBody.innerHTML = '';
        
        if (data && data.services && data.services.length > 0) {
            data.services.forEach(service => {
                const row = document.createElement('tr');
                
                row.innerHTML = `
                    <td>${service.payer || ''}</td>
                    <td>${service.memberId || ''}</td>
                    <td>${service.serviceAuthNumber || ''}</td>
                    <td>${service.procedureServiceCode || ''} ${service.modifierCode ? ', ' + service.modifierCode : ''}</td>
                    <td>${service.dates || ''}</td>
                    <td>${service.units || ''}</td>
                    <td>${service.serviceRate || ''}</td>
                    <td>${service.usedUnits || '0'}</td>
                    <td>${service.totalHoursRemaining || ''}</td>
                    <td>${service.hoursPerDay || ''}</td>
                    <td>${service.hoursPerWeek || ''}</td>
                    <td>
                        <button class="btn secondary-btn view-btn" data-id="${service.id || ''}">View</button>
                    </td>
                `;
                
                resultsBody.appendChild(row);
            });
        } else {
            // No results
            const row = document.createElement('tr');
            row.innerHTML = `<td colspan="12" style="text-align: center;">No data found</td>`;
            resultsBody.appendChild(row);
        }
    }

    // Print functionality
    printBtn.addEventListener('click', () => {
        window.print();
    });

    // Export as PDF
    exportPdfBtn.addEventListener('click', async () => {
        loadingOverlay.classList.remove('loading-hidden');
        
        try {
            const response = await fetch('http://localhost:5000/api/export-pdf', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ table: resultsBody.innerHTML })
            });
            
            if (!response.ok) {
                throw new Error('Server responded with an error');
            }
            
            // Handle PDF download
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = 'service_authorization.pdf';
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            
        } catch (error) {
            console.error('Error:', error);
            alert('Error exporting PDF. Please try again.');
        } finally {
            loadingOverlay.classList.add('loading-hidden');
        }
    });

    // New Entry button
    newEntryBtn.addEventListener('click', () => {
        // Reset forms
        pdfForm.reset();
        manualForm.reset();
        
        // Go back to PDF upload section
        resultsSection.classList.add('section-hidden');
        resultsSection.classList.remove('section-active');
        pdfSection.classList.add('section-active');
        pdfSection.classList.remove('section-hidden');
        
        // Reset active tab
        pdfTab.classList.add('active');
        manualTab.classList.remove('active');
    });
});

document.addEventListener('DOMContentLoaded', function() {
    // Form submission handler
    const clientForm = document.getElementById('clientForm');
    clientForm.addEventListener('submit', function(e) {
        e.preventDefault();
        submitForm();
    });

    // Upload area functionality
    const uploadArea = document.getElementById('uploadArea');
    const photoInput = document.getElementById('photo');
    
    uploadArea.addEventListener('click', function() {
        photoInput.click();
    });
    
    uploadArea.addEventListener('dragover', function(e) {
        e.preventDefault();
        uploadArea.classList.add('highlight');
    });
    
    uploadArea.addEventListener('dragleave', function() {
        uploadArea.classList.remove('highlight');
    });
    
    uploadArea.addEventListener('drop', function(e) {
        e.preventDefault();
        uploadArea.classList.remove('highlight');
        
        if (e.dataTransfer.files.length) {
            photoInput.files = e.dataTransfer.files;
            updateFileName();
        }
    });
    
    photoInput.addEventListener('change', updateFileName);
    
    function updateFileName() {
        if (photoInput.files.length) {
            const fileName = photoInput.files[0].name;
            uploadArea.querySelector('p').textContent = fileName;
        }
    }

    // Date picker initialization for date fields
    // This is a simplified version - in a production app, you'd use a proper date picker library
    const dateFields = document.querySelectorAll('#birthdate, #dateOfAssessment, #startOfCare');
    dateFields.forEach(field => {
        field.addEventListener('focus', function() {
            field.type = 'date';
        });
        
        field.addEventListener('blur', function() {
            if (!field.value) {
                field.type = 'text';
            }
        });
    });

    // Form submission function
    function submitForm() {
        const formData = new FormData(clientForm);
        
        // Convert FormData to JSON
        const jsonData = {};
        formData.forEach((value, key) => {
            // Handle checkbox values
            if (key === 'primaryMobile' || key === 'secondaryMobile') {
                jsonData[key] = value === 'on';
            } else {
                jsonData[key] = value;
            }
        });
        
        // Send data to backend
        fetch('/api/save-client', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(jsonData)
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            console.log('Success:', data);
            alert('Client data saved successfully!');
            // Optionally reset form or redirect
            // clientForm.reset();
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Error saving client data. Please try again.');
        });
    }
});

document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".toggle-submenu").forEach(function (menuItem) {
        menuItem.addEventListener("click", function (e) {
            e.preventDefault();
            let parent = this.parentElement;
            let submenu = parent.querySelector(".submenu");

            // Close all other submenus
            document.querySelectorAll(".menu-item").forEach(function (item) {
                if (item !== parent) {
                    item.classList.remove("open");
                    item.querySelector(".submenu").style.display = "none";
                }
            });

            // Toggle current submenu
            parent.classList.toggle("open");
            submenu.style.display = submenu.style.display === "block" ? "none" : "block";
        });
    });
});



// document.addEventListener("DOMContentLoaded", function () {
//     document.querySelectorAll(".toggle-submenu").forEach(function (menuItem) {
//         menuItem.addEventListener("click", function (e) {
//             e.preventDefault();
//             let submenu = this.nextElementSibling;
//             submenu.style.display = submenu.style.display === "block" ? "none" : "block";
//         });
//     });
// });


// Main JavaScript file for the dashboard
document.addEventListener('DOMContentLoaded', function() {
    // Initialize sidebar menu toggles
    initSidebar();
    
    // Load dashboard data
    loadDashboardData();
    
    // Initialize charts
    initCharts();
    
    // Initialize calendar
    initCalendar();
});

// Sidebar functionality
function initSidebar() {
    document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll(".toggle-submenu").forEach(function (menuItem) {
            menuItem.addEventListener("click", function (e) {
                e.preventDefault();
                let parent = this.parentElement;
                let submenu = parent.querySelector(".submenu");
    
                // Close all other submenus
                document.querySelectorAll(".menu-item").forEach(function (item) {
                    if (item !== parent) {
                        item.classList.remove("open");
                        item.querySelector(".submenu").style.display = "none";
                    }
                });
    
                // Toggle current submenu
                parent.classList.toggle("open");
                submenu.style.display = submenu.style.display === "block" ? "none" : "block";
            });
        });
    });
}

// Load all dashboard data
function loadDashboardData() {
    // Fetch summary stats
    fetch('/api/stats/summary')
        .then(response => response.json())
        .then(data => {
            updateStatCards(data);
            updateClaimsSummary(data);
        })
        .catch(error => console.error('Error fetching stats summary:', error));
    
    // Fetch yearly revenue data
    fetch('/api/revenue/yearly')
        .then(response => response.json())
        .then(data => {
            updateYearlyRevenueChart(data);
        })
        .catch(error => console.error('Error fetching yearly revenue:', error));
    
    // Fetch payments by payer
    fetch('/api/payments/by_payer')
        .then(response => response.json())
        .then(data => {
            updatePaymentsByPayerChart(data);
        })
        .catch(error => console.error('Error fetching payments by payer:', error));
    
    // Fetch caregiver schedule
    fetch('/api/schedule/caregivers')
        .then(response => response.json())
        .then(data => {
            updateCaregiverSchedule(data);
        })
        .catch(error => console.error('Error fetching caregiver schedule:', error));
    
    // Fetch revenue by payer
    fetch('/api/revenue/by_payer')
        .then(response => response.json())
        .then(data => {
            updateRevenueByPayerTable(data);
        })
        .catch(error => console.error('Error fetching revenue by payer:', error));
}

// Update stat cards with fetched data
function updateStatCards(data) {
    // Update unpaid claims chart
    updateStatChart('unpaidClaimsChart', data.unpaid_claims.count, data.unpaid_claims.total);
    
    // Update unpaid hours chart
    updateHoursChart('unpaidHoursChart', data.unpaid_hours);
    
    // Update scheduled hours chart
    updateHoursChart('scheduledHoursChart', data.scheduled_hours);
    
    // Update worked hours chart
    updateHoursChart('workedHoursChart', data.worked_hours);
}

// Update stat chart with value
function updateStatChart(chartId, value, total) {
    const ctx = document.getElementById(chartId).getContext('2d');
    
    new Chart(ctx, {
        type: 'doughnut',
        data: {
            datasets: [{
                data: [value, total - value],
                backgroundColor: ['#3498db', '#ecf0f1'],
                borderWidth: 0
            }]
        },
        options: {
            cutout: '70%',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    enabled: false
                }
            }
        }
    });
    
    // Add text in the center
    const chartContainer = document.getElementById(chartId);
    const textElement = document.createElement('div');
    textElement.classList.add('stat-value');
    textElement.textContent = value + '/' + total;
    chartContainer.parentNode.insertBefore(textElement, chartContainer.nextSibling);
}

// Update hours chart with value
function updateHoursChart(chartId, value) {
    const ctx = document.getElementById(chartId).getContext('2d');
    
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: [''],
            datasets: [{
                data: [value],
                backgroundColor: '#2ecc71',
                borderWidth: 0,
                barThickness: 10
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    enabled: false
                }
            },
            scales: {
                x: {
                    display: false
                },
                y: {
                    display: false
                }
            }
        }
    });
    
    // Add text below the chart
    const chartContainer = document.getElementById(chartId);
    const textElement = document.createElement('div');
    textElement.classList.add('stat-value');
    textElement.textContent = value.toFixed(1) + ' hrs';
    chartContainer.parentNode.insertBefore(textElement, chartContainer.nextSibling);
}

// Update claims summary section
function updateClaimsSummary(data) {
    // Update denied claims
    document.querySelector('.claims-summary .claim-item:nth-child(1) .claim-value').textContent = 
        `${data.denied_claims.count}/${data.denied_claims.total}`;
    
    // Update voided claims
    document.querySelector('.claims-summary .claim-item:nth-child(2) .claim-value').textContent = 
        `${data.voided_claims.count}/${data.voided_claims.total}`;
    
    // Update replaced claims
    document.querySelector('.claims-summary .claim-item:nth-child(3) .claim-value').textContent = 
        `${data.replaced_claims.count}/${data.replaced_claims.total}`;
    
    // Update payroll
    document.querySelector('.claims-summary .claim-item:nth-child(4) .claim-value').textContent = 
        `$${data.payroll.paid.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}/$${data.payroll.total.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
}

// Initialize all charts
function initCharts() {
    // This function will be replaced by the data from the API
    // Placeholder setup for chart instances
}

// Update yearly revenue chart
function updateYearlyRevenueChart(data) {
    const ctx = document.getElementById('yearlyRevenueChart').getContext('2d');
    
    // Extract months and revenue values
    const months = data.map(item => item.month);
    const revenue = data.map(item => item.revenue);
    
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: months,
            datasets: [{
                label: 'Revenue',
                data: revenue,
                backgroundColor: 'rgba(52, 152, 219, 0.2)',
                borderColor: 'rgba(52, 152, 219, 1)',
                borderWidth: 2,
                pointBackgroundColor: 'rgba(52, 152, 219, 1)',
                pointBorderColor: '#fff',
                pointBorderWidth: 2,
                pointRadius: 5,
                fill: true,
                tension: 0.1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `$${context.parsed.y.toLocaleString('en-US')}`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        display: false
                    }
                },
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(value) {
                            return '$' + value.toLocaleString('en-US');
                        }
                    }
                }
            }
        }
    });
}

// Update payments by payer chart
function updatePaymentsByPayerChart(data) {
    const ctx = document.getElementById('paymentsByPayerChart').getContext('2d');
    
    // Extract payers and amounts
    const payers = data.map(item => item.payer);
    const amounts = data.map(item => item.amount);
    
    // Generate colors for each payer
    const colors = generateColors(payers.length);
    
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: payers,
            datasets: [{
                data: amounts,
                backgroundColor: colors,
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `$${context.parsed.y.toLocaleString('en-US')}`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        display: false
                    }
                },
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(value) {
                            return '$' + value.toLocaleString('en-US');
                        }
                    }
                }
            }
        }
    });
}

// Generate an array of colors for charts
function generateColors(count) {
    const colors = [
        '#3498db', '#2ecc71', '#f1c40f', '#e74c3c', '#9b59b6',
        '#1abc9c', '#e67e22', '#34495e', '#16a085', '#d35400'
    ];
    
    // If we need more colors than in our palette, we'll repeat them
    const result = [];
    for (let i = 0; i < count; i++) {
        result.push(colors[i % colors.length]);
    }
    
    return result;
}

// Update caregiver schedule with data
function updateCaregiverSchedule(data) {
    const calendarGrid = document.getElementById('calendar-grid');
    
    // Clear existing content
    calendarGrid.innerHTML = '';
    
    // Get current month and year
    const currentDate = new Date();
    const currentMonth = currentDate.getMonth();
    const currentYear = currentDate.getFullYear();
    
    // Get first day of the month
    const firstDay = new Date(currentYear, currentMonth, 1).getDay();
    
    // Get days in month
    const daysInMonth = new Date(currentYear, currentMonth + 1, 0).getDate();
    
    // Create calendar grid
    // Add empty cells for days before the first day of the month
    for (let i = 0; i < firstDay; i++) {
        const emptyDay = document.createElement('div');
        emptyDay.classList.add('calendar-day', 'empty');
        calendarGrid.appendChild(emptyDay);
    }
    
    // Add days of the month
    for (let day = 1; day <= daysInMonth; day++) {
        const dayElement = document.createElement('div');
        dayElement.classList.add('calendar-day');
        
        // Add day number
        const dayNumber = document.createElement('div');
        dayNumber.classList.add('day-number');
        dayNumber.textContent = day;
        dayElement.appendChild(dayNumber);
        
        // Check if there are any schedules for this day
        const daySchedules = data.filter(schedule => {
            const scheduleDate = new Date(schedule.date);
            return scheduleDate.getDate() === day;
        });
        
        // Add schedule items for this day
        daySchedules.forEach(schedule => {
            const scheduleItem = document.createElement('div');
            scheduleItem.classList.add('schedule-item');
            scheduleItem.style.backgroundColor = schedule.color || getRandomColor(schedule.caregiver_id);
            
            scheduleItem.innerHTML = `
                <div class="schedule-title">${schedule.caregiver_name}</div>
                <div class="schedule-subtitle">Client: ${schedule.client_name}</div>
            `;
            
            dayElement.appendChild(scheduleItem);
        });
        
        calendarGrid.appendChild(dayElement);
    }
}

// Get a random color based on an id string
function getRandomColor(id) {
    const colors = [
        '#3498db', '#2ecc71', '#f1c40f', '#e74c3c', '#9b59b6',
        '#1abc9c', '#e67e22', '#34495e', '#16a085', '#d35400'
    ];
    
    // Use the id to deterministically choose a color
    const index = parseInt(id.substring(0, 8), 16) % colors.length;
    return colors[index];
}

// Update revenue by payer table
function updateRevenueByPayerTable(data) {
    const tableBody = document.querySelector('.data-table tbody');
    
    // Clear existing content
    tableBody.innerHTML = '';
    
    if (data.length === 0) {
        const noDataRow = document.createElement('tr');
        noDataRow.innerHTML = '<td colspan="6" class="no-data">No data available in table</td>';
        tableBody.appendChild(noDataRow);
        
        // Update table footer info
        document.querySelector('.table-info').textContent = 'Showing 0 to 0 of 0 entries';
    } else {
        // Add data rows
        data.forEach(item => {
            const row = document.createElement('tr');
            
            row.innerHTML = `
                <td>${item.payer}</td>
                <td>$${item.this_month.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</td>
                <td>$${item.last_3_months.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</td>
                <td>$${item.last_6_months.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</td>
                <td>$${item.last_12_months.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</td>
                <td>$${item.lifetime.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</td>
            `;
            
            tableBody.appendChild(row);
        });
        
        // Update table footer info
        document.querySelector('.table-info').textContent = `Showing 1 to ${data.length} of ${data.length} entries`;
    }
}
// Initialize calendar
function initCalendar() {
    const calendarHeader = document.querySelector('.calendar-header');
    if (!calendarHeader) return;
    
    // Get current date info
    const now = new Date();
    const currentMonth = now.getMonth();
    const currentYear = now.getFullYear();
    
    // Create month and year display
    const monthNames = [
        'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
    ];
    
    // Set calendar title to current month and year
    const calendarTitle = document.querySelector('.calendar-title');
    if (calendarTitle) {
        calendarTitle.textContent = `${monthNames[currentMonth]} ${currentYear}`;
    }
    
    // Add event listeners for previous and next month buttons
    const prevButton = document.querySelector('.calendar-prev');
    const nextButton = document.querySelector('.calendar-next');
    
    if (prevButton) {
        prevButton.addEventListener('click', function() {
            navigateCalendar(-1);
        });
    }
    
    if (nextButton) {
        nextButton.addEventListener('click', function() {
            navigateCalendar(1);
        });
    }
    
    // Add event listeners for day elements to show detailed view
    const calendarDays = document.querySelectorAll('.calendar-day:not(.empty)');
    calendarDays.forEach(day => {
        day.addEventListener('click', function() {
            showDayDetail(this);
        });
    });
}

// Navigate calendar by moving forward or backward
function navigateCalendar(direction) {
    // Get current displayed month and year
    const calendarTitle = document.querySelector('.calendar-title');
    if (!calendarTitle) return;
    
    const monthYearParts = calendarTitle.textContent.split(' ');
    const monthNames = [
        'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
    ];
    
    let month = monthNames.indexOf(monthYearParts[0]);
    let year = parseInt(monthYearParts[1]);
    
    // Calculate new month and year
    month += direction;
    if (month < 0) {
        month = 11;
        year--;
    } else if (month > 11) {
        month = 0;
        year++;
    }
    
    // Update calendar title
    calendarTitle.textContent = `${monthNames[month]} ${year}`;
    
    // Fetch and update calendar data for the new month
    fetch(`/api/schedule/caregivers?month=${month + 1}&year=${year}`)
        .then(response => response.json())
        .then(data => {
            updateCaregiverSchedule(data);
        })
        .catch(error => console.error('Error fetching caregiver schedule:', error));
}

// Show detailed view for a selected day
function showDayDetail(dayElement) {
    // Remove active class from previously selected day
    const activeDays = document.querySelectorAll('.calendar-day.active');
    activeDays.forEach(day => day.classList.remove('active'));
    
    // Add active class to selected day
    dayElement.classList.add('active');
    
    // Get day number
    const dayNumber = dayElement.querySelector('.day-number').textContent;
    
    // Get current month and year from calendar title
    const calendarTitle = document.querySelector('.calendar-title');
    if (!calendarTitle) return;
    
    const monthYearParts = calendarTitle.textContent.split(' ');
    const monthNames = [
        'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
    ];
    
    const month = monthNames.indexOf(monthYearParts[0]);
    const year = parseInt(monthYearParts[1]);
    
    // Format date for API request
    const date = new Date(year, month, parseInt(dayNumber));
    const formattedDate = `${year}-${(month + 1).toString().padStart(2, '0')}-${dayNumber.padStart(2, '0')}`;
    
    // Show day detail panel if it exists
    const dayDetailPanel = document.querySelector('.day-detail-panel');
    if (dayDetailPanel) {
        // Update day detail panel title
        const dayDetailTitle = dayDetailPanel.querySelector('.day-detail-title');
        if (dayDetailTitle) {
            dayDetailTitle.textContent = `Appointments for ${monthNames[month].substring(0, 3)} ${dayNumber}, ${year}`;
        }
        
        // Show the panel
        dayDetailPanel.style.display = 'block';
        
        // Fetch detailed appointments for this day
        fetch(`/api/schedule/details?date=${formattedDate}`)
            .then(response => response.json())
            .then(data => {
                updateDayDetailContent(dayDetailPanel, data);
            })
            .catch(error => console.error('Error fetching day details:', error));
    }
}

// Update day detail panel with appointment data
function updateDayDetailContent(panel, appointments) {
    const detailContent = panel.querySelector('.day-detail-content');
    if (!detailContent) return;
    
    // Clear existing content
    detailContent.innerHTML = '';
    
    if (appointments.length === 0) {
        detailContent.innerHTML = '<div class="no-appointments">No appointments scheduled for this day.</div>';
        return;
    }
    
    // Sort appointments by time
    appointments.sort((a, b) => {
        return new Date(`2000-01-01T${a.start_time}`) - new Date(`2000-01-01T${b.start_time}`);
    });
    
    // Create appointments list
    appointments.forEach(appointment => {
        const appointmentItem = document.createElement('div');
        appointmentItem.classList.add('appointment-item');
        
        // Format times
        const startTime = formatTime(appointment.start_time);
        const endTime = formatTime(appointment.end_time);
        
        appointmentItem.innerHTML = `
            <div class="appointment-time">${startTime} - ${endTime}</div>
            <div class="appointment-details">
                <div class="caregiver-name">${appointment.caregiver_name}</div>
                <div class="client-name">Client: ${appointment.client_name}</div>
                <div class="appointment-type">Service: ${appointment.service_type}</div>
                <div class="appointment-address">
                    <i class="fas fa-map-marker-alt"></i> ${appointment.address}
                </div>
            </div>
        `;
        
        // Add background color based on caregiver
        const colorBar = document.createElement('div');
        colorBar.classList.add('appointment-color');
        colorBar.style.backgroundColor = appointment.color || getRandomColor(appointment.caregiver_id);
        appointmentItem.insertBefore(colorBar, appointmentItem.firstChild);
        
        detailContent.appendChild(appointmentItem);
    });
}

// Format time from 24-hour to 12-hour format
function formatTime(time24) {
    const [hours, minutes] = time24.split(':');
    let period = 'AM';
    let hour = parseInt(hours);
    
    if (hour >= 12) {
        period = 'PM';
        if (hour > 12) {
            hour -= 12;
        }
    }
    
    if (hour === 0) {
        hour = 12;
    }
    
    return `${hour}:${minutes} ${period}`;
}

// scripts.js - Handling employee data submission and image upload

document.addEventListener('DOMContentLoaded', function() {
    const employeeForm = document.getElementById('employeeForm');
    const uploadArea = document.getElementById('uploadArea');
    const profileImageInput = document.getElementById('profileImage');
    const closeBtn = document.querySelector('.close');
    const cancelBtn = document.querySelector('.btn-cancel');
    
    // Initialize any datepickers for date fields
    initializeDatePickers();
    
    // Load ZIP codes and managers for dropdown options
    loadZipCodes();
    loadManagers();
    
    // Handle drag and drop for file upload
    initializeFileUpload();
    
    // Form submission handler
    employeeForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        try {
            // First save the employee data
            const employeeData = collectFormData();
            const savedEmployee = await saveEmployeeData(employeeData);
            
            // If employee was saved successfully and we have a profile image, upload it
            if (savedEmployee.success && profileImageInput.files.length > 0) {
                await uploadProfileImage(savedEmployee.employeeId, profileImageInput.files[0]);
            }
            
            // Show success message and reset form
            showNotification('Employee saved successfully!', 'success');
            employeeForm.reset();
            
        } catch (error) {
            showNotification(`Error: ${error.message}`, 'error');
        }
    });
    
    // Close modal handlers
    if (closeBtn) {
        closeBtn.addEventListener('click', closeModal);
    }
    
    if (cancelBtn) {
        cancelBtn.addEventListener('click', function(e) {
            e.preventDefault();
            closeModal();
        });
    }
    
    // Function to collect all form data
    function collectFormData() {
        const formData = {};
        
        // Get all form inputs and process them
        const inputs = employeeForm.querySelectorAll('input, select, textarea');
        inputs.forEach(input => {
            // Skip the file input as it's handled separately
            if (input.type === 'file') return;
            
            // Only include fields with values
            if (input.value) {
                formData[input.name] = input.value;
            }
        });
        
        return formData;
    }
    
    // Function to save employee data via API
    async function saveEmployeeData(employeeData) {
        const response = await fetch('/api/save-employee', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(employeeData)
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.message || 'Failed to save employee data');
        }
        
        return data;
    }
    
    // Function to upload profile image
    async function uploadProfileImage(employeeId, imageFile) {
        const formData = new FormData();
        formData.append('profileImage', imageFile);
        
        const response = await fetch(`/api/upload-profile-image/${employeeId}`, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.message || 'Failed to upload profile image');
        }
        
        return data;
    }
    
    // Initialize file upload area with drag and drop functionality
    function initializeFileUpload() {
        // Click to upload
        uploadArea.addEventListener('click', function() {
            profileImageInput.click();
        });
        
        // Show file name when selected
        profileImageInput.addEventListener('change', function() {
            if (this.files.length > 0) {
                uploadArea.querySelector('p').textContent = this.files[0].name;
                uploadArea.classList.add('has-file');
            }
        });
        
        // Drag and drop functionality
        uploadArea.addEventListener('dragover', function(e) {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });
        
        uploadArea.addEventListener('dragleave', function() {
            uploadArea.classList.remove('dragover');
        });
        
        uploadArea.addEventListener('drop', function(e) {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            
            if (e.dataTransfer.files.length > 0) {
                profileImageInput.files = e.dataTransfer.files;
                uploadArea.querySelector('p').textContent = e.dataTransfer.files[0].name;
                uploadArea.classList.add('has-file');
            }
        });
    }
    
    // Load ZIP codes for dropdown (could be from an API)
    function loadZipCodes() {
        const zipSelect = document.getElementById('zipCode');
        
        // Example data - in a real app, fetch from an API
        const zipCodes = [
            { code: '10001', city: 'New York', state: 'NY' },
            { code: '90001', city: 'Los Angeles', state: 'CA' },
            { code: '60601', city: 'Chicago', state: 'IL' }
        ];
        
        zipCodes.forEach(zip => {
            const option = document.createElement('option');
            option.value = zip.code;
            option.textContent = `${zip.code} - ${zip.city}, ${zip.state}`;
            zipSelect.appendChild(option);
        });
        
        // When ZIP is selected, auto-fill city and state
        zipSelect.addEventListener('change', function() {
            const selected = zipCodes.find(zip => zip.code === this.value);
            if (selected) {
                document.getElementById('city').value = selected.city;
                document.getElementById('state').value = selected.state;
            }
        });
    }
    
    // Load managers for "Reports To" dropdown
    async function loadManagers() {
        try {
            const response = await fetch('/api/employees?role=manager');
            const data = await response.json();
            
            if (data.success) {
                const reportsToSelect = document.getElementById('reportsTo');
                
                data.employees.forEach(manager => {
                    const option = document.createElement('option');
                    option.value = manager._id;
                    option.textContent = `${manager.firstName} ${manager.lastName}`;
                    reportsToSelect.appendChild(option);
                });
            }
        } catch (error) {
            console.error('Error loading managers:', error);
        }
    }
    
    // Initialize date pickers for date fields
    function initializeDatePickers() {
        // This is a placeholder - replace with your preferred date picker library
        // For example, using flatpickr, bootstrap datepicker, etc.
        const dateFields = document.querySelectorAll('.input-group.date input');
        
        dateFields.forEach(field => {
            // Initialize date picker for each date field
            // Example: flatpickr(field, { dateFormat: 'Y-m-d' });
            
            // This is just a basic validation for now
            field.addEventListener('change', function() {
                // Simple date format validation
                const regex = /^\d{4}-\d{2}-\d{2}$/;
                if (!regex.test(this.value)) {
                    this.classList.add('error');
                } else {
                    this.classList.remove('error');
                }
            });
        });
    }
    
    // Close the modal
    function closeModal() {
        // Hide the modal or navigate away
        const modal = document.querySelector('.modal');
        if (modal) {
            modal.classList.add('hidden');
        }
    }
    
    // Display notifications/feedback to the user
    function showNotification(message, type) {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        
        // Add to document
        document.body.appendChild(notification);
        
        // Remove after delay
        setTimeout(() => {
            notification.classList.add('fade-out');
            setTimeout(() => {
                notification.remove();
            }, 500);
        }, 3000);
    }
});