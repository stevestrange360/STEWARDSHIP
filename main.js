// Main JavaScript for Stewardship Reminder System

$(document).ready(function() {
    console.log('Stewardship System Loaded');
    
    // Initialize tooltips
    initializeTooltips();
    
    // Initialize search functionality
    initializeSearch();
    
    // Initialize form validation
    initializeFormValidation();
    
    // Initialize auto-refresh for dashboard
    initializeAutoRefresh();
    
    // Initialize notification system
    initializeNotifications();
});

// Tooltips
function initializeTooltips() {
    $('[data-toggle="tooltip"]').tooltip();
}

// Search functionality
function initializeSearch() {
    $('#searchInput').on('keyup', function() {
        let searchText = $(this).val().toLowerCase();
        
        $('#debtorsTable tbody tr').each(function() {
            let name = $(this).find('td:first').text().toLowerCase();
            let debtType = $(this).find('td:eq(1)').text().toLowerCase();
            
            if (name.includes(searchText) || debtType.includes(searchText)) {
                $(this).show();
            } else {
                $(this).hide();
            }
        });
        
        // Show/hide no results message
        let visibleRows = $('#debtorsTable tbody tr:visible').length;
        if (visibleRows === 0) {
            if ($('#noResultsMessage').length === 0) {
                $('#debtorsTable tbody').append(`
                    <tr id="noResultsMessage">
                        <td colspan="8" class="text-center py-4">
                            <i class="bi bi-search fs-1 text-muted"></i>
                            <p class="text-muted mt-2">No matching records found</p>
                        </td>
                    </tr>
                `);
            }
        } else {
            $('#noResultsMessage').remove();
        }
    });
}

// Form validation
function initializeFormValidation() {
    // Phone number validation
    $('input[type="tel"]').on('input', function() {
        let phone = $(this).val().replace(/\D/g, '');
        if (phone.length > 11) {
            phone = phone.slice(0, 11);
        }
        $(this).val(phone);
    });
    
    // Amount validation
    $('input[type="number"]').on('blur', function() {
        let value = $(this).val();
        if (value) {
            // Ensure integer
            $(this).val(Math.floor(parseFloat(value)));
        }
    });
    
    // Initial payment cannot exceed total
    $('input[name="initial_payment"]').on('change', function() {
        let total = parseFloat($('input[name="total_amount"]').val()) || 0;
        let initial = parseFloat($(this).val()) || 0;
        
        if (initial > total) {
            $(this).addClass('is-invalid');
            showNotification('Initial payment cannot exceed total amount', 'danger');
        } else {
            $(this).removeClass('is-invalid');
        }
    });
}

// Auto-refresh dashboard
function initializeAutoRefresh() {
    // Refresh stats every 5 minutes
    setInterval(function() {
        if (window.location.pathname === '/') {
            refreshStats();
        }
    }, 300000);
}

function refreshStats() {
    $.ajax({
        url: '/api/stats',
        method: 'GET',
        success: function(data) {
            updateStats(data);
        },
        error: function() {
            console.log('Failed to refresh stats');
        }
    });
}

function updateStats(stats) {
    $('#totalMembers').text(stats.total_members);
    $('#totalCommitted').text('Tsh' + formatNumber(stats.total_committed));
    $('#pendingCount').text(stats.pending_count);
    $('#paidCount').text(stats.paid_count);
}

// Notification system
function initializeNotifications() {
    // Check for overdue debts
    checkOverdueDebts();
    
    // Check every hour
    setInterval(checkOverdueDebts, 3600000);
}

function checkOverdueDebts() {
    $.ajax({
        url: '/api/check-overdue',
        method: 'GET',
        success: function(data) {
            if (data.overdue_count > 0) {
                showNotification(
                    `${data.overdue_count} overdue debt(s) found. Send reminders!`,
                    'warning'
                );
            }
        }
    });
}

function showNotification(message, type = 'info') {
    // Create notification element
    let notification = `
        <div class="alert alert-${type} alert-dismissible fade show notification-toast" role="alert">
            <i class="bi bi-info-circle me-2"></i>
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    
    // Add to page
    $('#notificationArea').append(notification);
    
    // Auto remove after 5 seconds
    setTimeout(function() {
        $('.notification-toast').first().fadeOut('slow', function() {
            $(this).remove();
        });
    }, 5000);
}

// Format number with commas
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

// Export to Excel
function exportToExcel() {
    let table = document.getElementById('debtorsTable');
    let wb = XLSX.utils.table_to_book(table, {sheet: "Debtors"});
    XLSX.writeFile(wb, "debtors_report.xlsx");
}

// Print table
function printTable() {
    window.print();
}

// Send bulk reminders
function sendBulkReminders() {
    if (!confirm('Send reminders to all pending debtors?')) {
        return;
    }
    
    $.ajax({
        url: '/api/send-bulk-reminders',
        method: 'POST',
        success: function(data) {
            showNotification(`Reminders sent to ${data.sent} debtors`, 'success');
        },
        error: function() {
            showNotification('Failed to send reminders', 'danger');
        }
    });
}

// Payment quick entry
function quickPayment(debtId, memberName) {
    let amount = prompt(`Enter payment amount for ${memberName}:`, '');
    
    if (amount && !isNaN(amount) && parseFloat(amount) > 0) {
        $.ajax({
            url: `/api/quick-payment/${debtId}`,
            method: 'POST',
            data: { amount: amount },
            success: function(data) {
                showNotification(`Payment of Tsh${formatNumber(amount)} recorded`, 'success');
                location.reload();
            },
            error: function() {
                showNotification('Failed to record payment', 'danger');
            }
        });
    }
}

// Date formatting
function formatDate(dateString) {
    let date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

// Calculate days until due
function daysUntilDue(dueDate) {
    let today = new Date();
    let due = new Date(dueDate);
    let diffTime = due - today;
    let diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    return diffDays;
}

// Status color based on due date
function getDueDateStatus(dueDate) {
    let days = daysUntilDue(dueDate);
    
    if (days < 0) {
        return { class: 'text-danger', text: `${Math.abs(days)} days overdue` };
    } else if (days <= 7) {
        return { class: 'text-warning', text: `${days} days left` };
    } else {
        return { class: 'text-success', text: `${days} days left` };
    }
}

// Initialize when document is ready
$(document).ready(function() {
    // Add notification area
    $('body').prepend('<div id="notificationArea" style="position: fixed; top: 20px; right: 20px; z-index: 9999;"></div>');
    
    // Add loading indicator
    $(document).ajaxStart(function() {
        $('#loadingIndicator').show();
    }).ajaxStop(function() {
        $('#loadingIndicator').hide();
    });
});

// Loading indicator HTML (add to base.html)
const loadingHTML = `
    <div id="loadingIndicator" style="display: none; position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); z-index: 9999;">
        <div class="spinner"></div>
    </div>
`;