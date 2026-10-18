// ===== CONFIG =====
// Base URL of your FastAPI backend. Change the port if yours is different.
const API_BASE_URL = "http://127.0.0.1:8000";

// Full list of products, kept in memory so search can filter locally
// without hitting the server on every keystroke.
let allProducts = [];

// Running count of alerts shown in the Alerts panel / sidebar badge.
let alertCount = 0;

// ===== AUTH HELPER =====
// Reads the token we saved in login.js. If it's missing, the user
// never logged in (or it was cleared), so send them to the login page.
function getToken() {
  const token = localStorage.getItem("access_token");
  if (!token) {
    window.location.href = "login.html";
    return null;
  }
  return token;
}

// ===== HELPER: decide badge/stripe status from quantity vs min_buffer =====
function getStockStatus(product) {
  const qty = product.quantity;
  const reorderLevel = product.min_buffer ?? 10; // fallback if field missing

  if (qty <= 0) return "critical";
  if (qty <= reorderLevel) return "warn";
  return "good";
}

function statusLabel(status) {
  if (status === "critical") return "Critical";
  if (status === "warn") return "Low Stock";
  return "In Stock";
}

// ===== BUILD ONE TABLE ROW FOR ONE PRODUCT =====
function renderProductRow(product) {
  const status = getStockStatus(product);
  const label = statusLabel(status);

  return `
    <tr class="row-status ${status}">
      <td>${product.name}</td>
      <td>${product.sku}</td>
      <td>${product.category ?? "-"}</td>
      <td>${product.quantity}</td>
      <td><span class="badge ${status}">${label}</span></td>
    </tr>
  `;
}

// ===== UPDATE STAT CARDS FROM REAL PRODUCT DATA =====
function updateStatCards(products) {
  document.getElementById("stat-total-products").textContent = products.length;

  const lowStockCount = products.filter(p => p.quantity <= (p.min_buffer ?? 10)).length;
  document.getElementById("stat-low-stock").textContent = lowStockCount;

  const totalValue = products.reduce((sum, p) => sum + (p.price * p.quantity), 0);
  document.getElementById("stat-inventory-value").textContent =
    "₹" + totalValue.toLocaleString("en-IN");

  const uniqueCategories = new Set(products.map(p => p.category)).size;
  document.getElementById("stat-categories").textContent = uniqueCategories;
}

// ===== SEARCH / FILTER PRODUCTS =====
function filterAndRenderProducts(searchTerm) {
  const term = searchTerm.trim().toLowerCase();

  const filtered = term === ""
    ? allProducts
    : allProducts.filter(p =>
        p.name.toLowerCase().includes(term) ||
        p.sku.toLowerCase().includes(term) ||
        (p.category ?? "").toLowerCase().includes(term)
      );

  const tbody = document.getElementById("product-table-body");
  if (filtered.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="5" style="text-align:center; color:#85868C; padding:24px;">
          No products match "${searchTerm}"
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = filtered.map(renderProductRow).join("");
}

// ===== MAIN FUNCTION: fetch products and render the table =====
async function loadProducts() {
  const tbody = document.getElementById("product-table-body");
  const token = getToken();
  if (!token) return; // getToken() already redirected to login.html

  try {
    const response = await fetch(`${API_BASE_URL}/products`, {
      headers: {
        "Authorization": `Bearer ${token}`,
      },
    });

    if (response.status === 401) {
      localStorage.removeItem("access_token");
      window.location.href = "login.html";
      return;
    }

    if (!response.ok) {
      throw new Error(`Server responded with status ${response.status}`);
    }

    const products = await response.json();

    allProducts = products; // save full list for search filtering
    updateStatCards(products);
    filterAndRenderProducts(document.getElementById("search-input").value);

  } catch (error) {
    console.error("Failed to load products:", error);
    tbody.innerHTML = `
      <tr>
        <td colspan="5" style="text-align:center; color:#DB4141; padding:24px;">
          Could not load products. Is your FastAPI server running at ${API_BASE_URL}?
        </td>
      </tr>
    `;
  }
}

// ===== POPULATE ALERTS WITH CURRENTLY LOW-STOCK PRODUCTS =====
// Runs once on page load, so existing low-stock items show up immediately,
// not just ones that become low-stock during this session.
function populateExistingAlerts(products) {
  const lowStockProducts = products.filter(p => p.quantity <= (p.min_buffer ?? 10));
  const alertsPanel = document.getElementById("alerts-panel");

  if (lowStockProducts.length === 0) {
    alertsPanel.innerHTML = `<p style="color:#85868C; text-align:center; padding:20px 0;">No alerts yet</p>`;
    return;
  }

  alertsPanel.innerHTML = ""; // clear the "No alerts yet" placeholder

  lowStockProducts.forEach(p => {
    const alertEl = document.createElement("div");
    alertEl.style.cssText = "padding:10px; border-bottom:1px solid #eee; font-size:14px;";
    alertEl.textContent = `${p.name} is low on stock! Only ${p.quantity} units left.`;
    alertsPanel.appendChild(alertEl);
  });

  alertCount = lowStockProducts.length;
  document.getElementById("alerts-badge").textContent = alertCount;
}

// ===== WEBSOCKET: LIVE LOW-STOCK ALERTS =====
function connectAlertsSocket() {
  const socket = new WebSocket("ws://127.0.0.1:8000/ws/alerts");

  socket.onmessage = (event) => {
    console.log("Live alert received:", event.data);
    loadProducts();

    const alertsPanel = document.getElementById("alerts-panel");
    if (alertCount === 0) {
      alertsPanel.innerHTML = "";
    }

    const alertEl = document.createElement("div");
    alertEl.style.cssText = "padding:10px; border-bottom:1px solid #eee; font-size:14px;";
    alertEl.textContent = `${new Date().toLocaleTimeString()} — ${event.data}`;
    alertsPanel.prepend(alertEl);

    alertCount++;
    document.getElementById("alerts-badge").textContent = alertCount;
  };

  socket.onclose = () => {
    console.warn("WebSocket disconnected. Retrying in 3s...");
    setTimeout(connectAlertsSocket, 3000);
  };
}

// ===== MODAL HELPERS =====
function openModal(id) {
  document.getElementById(id).style.display = "flex";
}
function closeModal(id) {
  document.getElementById(id).style.display = "none";
}

// ===== ADD PRODUCT =====
async function handleAddProduct(event) {
  event.preventDefault(); // stops the form from doing a normal page reload
  const token = getToken();
  const errorEl = document.getElementById("ap-error");
  errorEl.style.display = "none";

  const payload = {
    name: document.getElementById("ap-name").value,
    sku: document.getElementById("ap-sku").value,
    category: document.getElementById("ap-category").value,
    price: parseFloat(document.getElementById("ap-price").value),
    quantity: parseInt(document.getElementById("ap-quantity").value),
    min_buffer: parseInt(document.getElementById("ap-min-buffer").value) || 10,
  };

  try {
    const response = await fetch(`${API_BASE_URL}/products`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`,
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const errData = await response.json();
      throw new Error(errData.detail || "Failed to add product");
    }

    closeModal("add-product-modal");
    document.getElementById("add-product-form").reset();
    loadProducts(); // refresh the table
  } catch (error) {
    errorEl.textContent = error.message;
    errorEl.style.display = "block";
  }
}

// ===== SCAN PRODUCT =====
async function handleScanProduct(event) {
  event.preventDefault();
  const token = getToken();
  const errorEl = document.getElementById("scan-error");
  errorEl.style.display = "none";

  const sku = document.getElementById("scan-sku").value;
  const quantity = document.getElementById("scan-quantity").value;
  const direction = document.getElementById("scan-direction").value;

  try {
    const response = await fetch(
      `${API_BASE_URL}/products/scan/${sku}?quantity=${quantity}&direction=${direction}`,
      {
        method: "PUT",
        headers: { "Authorization": `Bearer ${token}` },
      }
    );

    if (!response.ok) {
      const errData = await response.json();
      throw new Error(errData.detail || "Scan failed");
    }

    closeModal("scan-modal");
    document.getElementById("scan-form").reset();
    loadProducts(); // refresh the table (WebSocket will also push an alert if low stock)
  } catch (error) {
    errorEl.textContent = error.message;
    errorEl.style.display = "block";
  }
}
// ===== PURCHASE ORDERS / AGENT PIPELINE =====
async function loadPurchaseOrders() {
  const token = getToken();
  const listEl = document.getElementById("orders-list");
  listEl.innerHTML = "Loading...";

  try {
    const response = await fetch(`${API_BASE_URL}/purchase-orders`, {
      headers: { "Authorization": `Bearer ${token}` },
    });
    const orders = await response.json();

    if (orders.length === 0) {
      listEl.innerHTML = `<p style="color:#85868C;">No purchase orders yet. Run the agent to generate some.</p>`;
      return;
    }

    listEl.innerHTML = orders.map(o => `
      <div class="order-row">
        <strong>${o.sku}</strong>
        <span class="order-status status-${o.status}">${o.status.replace("_", " ")}</span><br>
        Qty: ${o.quantity_ordered} &middot; Value: ₹${Number(o.order_value).toLocaleString("en-IN")}<br>
        <span style="color:#85868C; font-size:13px;">${o.reason}</span>
        ${o.status === "pending_approval" ? `
          <div style="margin-top:8px;">
            <button class="btn-approve" onclick="handleOrderDecision(${o.id}, 'approve')">Approve</button>
            <button class="btn-reject" onclick="handleOrderDecision(${o.id}, 'reject')">Reject</button>
          </div>` : ""}
      </div>
    `).join("");
  } catch (error) {
    listEl.innerHTML = `<p style="color:#DB4141;">Could not load purchase orders.</p>`;
  }
}

async function handleOrderDecision(orderId, decision) {
  const token = getToken();
  try {
    const response = await fetch(`${API_BASE_URL}/purchase-orders/${orderId}/${decision}`, {
      method: "PUT",
      headers: { "Authorization": `Bearer ${token}` },
    });
    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.detail || "Action failed");
    }
    loadPurchaseOrders(); // refresh the list to show the new status
  } catch (error) {
    alert(error.message);
  }
}

async function handleRunAgentNow() {
  const token = getToken();
  const btn = document.getElementById("run-agent-btn");
  btn.textContent = "Running...";
  btn.disabled = true;
  try {
    await fetch(`${API_BASE_URL}/agent/run-now`, {
      method: "POST",
      headers: { "Authorization": `Bearer ${token}` },
    });
    await loadPurchaseOrders();
  } finally {
    btn.textContent = "Run Forecasting Agent Now";
    btn.disabled = false;
  }
}
async function handleOrderDecision(orderId, decision) {
  const token = getToken();
  try {
    const response = await fetch(`${API_BASE_URL}/purchase-orders/${orderId}/${decision}`, {
      method: "PUT",
      headers: { "Authorization": `Bearer ${token}` },
    });
    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.detail || "Action failed");
    }
    loadPurchaseOrders();  // refresh the orders list
    loadProducts();        // NEW: refresh the product table too, since stock just changed
  } catch (error) {
    alert(error.message);
  }
}
// ===== WIRE UP EVERYTHING ON PAGE LOAD =====
// This is the ONLY DOMContentLoaded listener in the file — everything
// that needs to run on page load lives here, in one flat block.
document.addEventListener("DOMContentLoaded", async () => {
  await loadProducts();
  populateExistingAlerts(allProducts);
  connectAlertsSocket();

  document.getElementById("add-product-btn").addEventListener("click", () => openModal("add-product-modal"));
  document.getElementById("scan-btn").addEventListener("click", () => openModal("scan-modal"));
  document.getElementById("add-product-form").addEventListener("submit", handleAddProduct);
  document.getElementById("scan-form").addEventListener("submit", handleScanProduct);
  document.getElementById("scan-nav-link").addEventListener("click", (e) => {
  e.preventDefault();
  openModal("scan-modal");
});

  document.getElementById("search-input").addEventListener("input", (e) => {
    filterAndRenderProducts(e.target.value);
  });

  document.getElementById("alerts-nav-link").addEventListener("click", (e) => {
    e.preventDefault();
    openModal("alerts-modal");
  });
  document.getElementById("orders-btn").addEventListener("click", () => {
  openModal("orders-modal");
  loadPurchaseOrders();
});
document.getElementById("run-agent-btn").addEventListener("click", handleRunAgentNow);
});