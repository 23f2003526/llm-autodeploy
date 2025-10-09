// script.js

// Sample product data
const products = [
  { name: "Product A", sales: [10, 5, 8] },
  { name: "Product B", sales: [3, 7] },
  { name: "Product C", sales: [5, 5, 5, 5] },
];

// Utility function to calculate total sales for a product
function calculateTotal(salesArray) {
  return salesArray.reduce((sum, val) => sum + val, 0);
}

// Function to render the sales table
function renderTable() {
  const tbody = document.querySelector('#product-sales tbody');
  tbody.innerHTML = '';
  
  let overallTotal = 0;

  products.forEach(product => {
    const totalSales = calculateTotal(product.sales);
    overallTotal += totalSales;

    const row = document.createElement('tr');

    // Product Name cell
    const nameCell = document.createElement('td');
    nameCell.textContent = product.name;
    row.appendChild(nameCell);

    // Sales Entries cell
    const salesCell = document.createElement('td');
    product.sales.forEach((sale, index) => {
      const span = document.createElement('span');
      span.textContent = sale;
      salesCell.appendChild(span);
      if (index < product.sales.length - 1) {
        salesCell.appendChild(document.createTextNode(', '));
      }
    });
    row.appendChild(salesCell);

    // Total Sales cell
    const totalCell = document.createElement('td');
    totalCell.textContent = totalSales;
    row.appendChild(totalCell);

    tbody.appendChild(row);
  });

  updateTotalSales(overallTotal);
}

// Function to update total sales display
function updateTotalSales(total) {
  const totalSalesDiv = document.getElementById('total-sales');
  totalSalesDiv.textContent = `Total Sales: ${total}`;
}

// Initialize table render
document.addEventListener('DOMContentLoaded', () => {
  renderTable();

  // Check if table has at least one row
  if (document.querySelectorAll('#product-sales tbody tr').length >= 1) {
    console.log('Table has been rendered with product data.');
  } else {
    console.log('No product data found.');
  }
});