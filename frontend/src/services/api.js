const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, options);
  const contentType = response.headers.get('content-type') || '';

  let data;
  if (contentType.includes('application/json')) {
    data = await response.json();
  } else {
    data = await response.text();
  }

  if (!response.ok) {
    const message = typeof data === 'string' ? data : data?.message || 'Unexpected error';
    throw new Error(message);
  }

  return data;
}

export async function extractReceipt(file) {
  const formData = new FormData();
  formData.append('file', file);

  return request('/extract-receipt', {
    method: 'POST',
    body: formData,
  });
}

export async function saveReceipt(payload) {
  return request('/save-receipt', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function fetchReceipts() {
  return request('/receipts', {
    method: 'GET',
  });
}

export async function saveReceiptToWallet(receiptId) {
  return request(`/save-to-wallet/${receiptId}`, {
    method: 'POST',
  });
}

export async function askReceiptAssistant(prompt) {
  return request('/llm-receipt', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt }),
  });
}

export { API_BASE_URL };
