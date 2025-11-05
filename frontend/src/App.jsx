import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  API_BASE_URL,
  askReceiptAssistant,
  extractReceipt,
  fetchReceipts,
  saveReceipt,
  saveReceiptToWallet,
} from './services/api';
import './App.css';

const DEFAULT_RECEIPT = {
  type_of_purchase: 'Retail',
  establishment_name: '',
  date: '',
  total: '',
  items: [],
};

const tabLabels = {
  upload: 'Upload & Extract',
  receipts: 'Saved Receipts',
  assistant: 'Insights Assistant',
};

function normalizeReceipt(raw) {
  if (!raw || typeof raw !== 'object') {
    return { ...DEFAULT_RECEIPT };
  }

  const items = Array.isArray(raw.items)
    ? raw.items.map((item) => ({
        name: item?.name ?? item?.item_name ?? '',
        price: item?.price ?? '',
        quantity: item?.quantity ?? 1,
      }))
    : [];

  return {
    type_of_purchase: raw.type_of_purchase || 'Retail',
    establishment_name: raw.establishment_name || '',
    date: raw.date || '',
    total: raw.total ?? '',
    items,
  };
}

function App() {
  const [activeTab, setActiveTab] = useState('upload');
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [extracted, setExtracted] = useState(null);
  const [formData, setFormData] = useState(DEFAULT_RECEIPT);
  const [saving, setSaving] = useState(false);
  const [receipts, setReceipts] = useState([]);
  const [receiptsError, setReceiptsError] = useState('');
  const [loadingReceipts, setLoadingReceipts] = useState(false);
  const [walletLoading, setWalletLoading] = useState({});
  const [globalMessage, setGlobalMessage] = useState(null);
  const [chatInput, setChatInput] = useState('');
  const [chatHistory, setChatHistory] = useState([]);
  const [chatLoading, setChatLoading] = useState(false);

  const showMessage = useCallback((type, text) => {
    setGlobalMessage({ type, text });
    if (text) {
      setTimeout(() => setGlobalMessage(null), 5000);
    }
  }, []);

  const loadReceipts = useCallback(async () => {
    setLoadingReceipts(true);
    setReceiptsError('');
    try {
      const response = await fetchReceipts();
      if (response?.status === 'success') {
        setReceipts(response.data ?? []);
      } else {
        throw new Error(response?.message || 'Failed to load receipts');
      }
    } catch (error) {
      setReceiptsError(error.message || 'Unable to load receipts');
    } finally {
      setLoadingReceipts(false);
    }
  }, []);

  useEffect(() => {
    loadReceipts();
  }, [loadReceipts]);

  const handleFileChange = (event) => {
    const file = event.target.files?.[0] || null;
    setSelectedFile(file);
  };

  const handleExtract = async (event) => {
    event.preventDefault();
    if (!selectedFile) {
      showMessage('error', 'Please choose a receipt image.');
      return;
    }

    setUploading(true);
    try {
      const response = await extractReceipt(selectedFile);
      if (response?.status !== 'success') {
        throw new Error(response?.message || 'Failed to extract receipt.');
      }

      const normalized = normalizeReceipt(response.data);
      setExtracted(response.data);
      setFormData(normalized);
      showMessage('success', 'Receipt extracted. Review details before saving.');
    } catch (error) {
      showMessage('error', error.message || 'Extraction failed.');
    } finally {
      setUploading(false);
    }
  };

  const updateField = (field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const updateItem = (index, field, value) => {
    setFormData((prev) => {
      const items = prev.items.map((item, i) =>
        i === index
          ? {
              ...item,
              [field]: ['price', 'quantity'].includes(field) && value !== ''
                ? Number(value)
                : value,
            }
          : item,
      );
      return { ...prev, items };
    });
  };

  const addItem = () => {
    setFormData((prev) => ({
      ...prev,
      items: [...prev.items, { name: '', price: 0, quantity: 1 }],
    }));
  };

  const removeItem = (index) => {
    setFormData((prev) => ({
      ...prev,
      items: prev.items.filter((_, i) => i !== index),
    }));
  };

  const handleSaveReceipt = async () => {
    setSaving(true);
    try {
      const payload = {
        ...formData,
        total: Number(formData.total) || 0,
        items: formData.items.map((item) => ({
          name: item.name || 'Unknown item',
          price: Number(item.price) || 0,
          quantity: Number(item.quantity) || 1,
        })),
      };

      const response = await saveReceipt(payload);
      if (response?.status !== 'success') {
        throw new Error(response?.message || 'Failed to save receipt.');
      }

      showMessage('success', 'Receipt saved to Firestore.');
      setExtracted(null);
      setFormData(DEFAULT_RECEIPT);
      setSelectedFile(null);
      await loadReceipts();
      setActiveTab('receipts');
    } catch (error) {
      showMessage('error', error.message || 'Could not save receipt.');
    } finally {
      setSaving(false);
    }
  };

  const handleSaveToWallet = async (receiptId) => {
    setWalletLoading((prev) => ({ ...prev, [receiptId]: true }));
    try {
      const response = await saveReceiptToWallet(receiptId);
      if (response?.status !== 'success') {
        throw new Error(response?.message || 'Wallet action failed.');
      }

      const saveUrl = response.saveUrl;
      showMessage('success', 'Wallet link generated. Opening new tab...');
      if (saveUrl) {
        window.open(saveUrl, '_blank', 'noopener,noreferrer');
      }
      await loadReceipts();
    } catch (error) {
      showMessage('error', error.message || 'Failed to save to wallet.');
    } finally {
      setWalletLoading((prev) => ({ ...prev, [receiptId]: false }));
    }
  };

  const handleSendPrompt = async (event) => {
    event.preventDefault();
    if (!chatInput.trim()) return;

    const prompt = chatInput.trim();
    setChatInput('');
    setChatHistory((prev) => [...prev, { role: 'user', text: prompt }]);
    setChatLoading(true);
    try {
      const response = await askReceiptAssistant(prompt);
      const reply = response?.reply || 'No response received.';
      setChatHistory((prev) => [...prev, { role: 'assistant', text: reply }]);
    } catch (error) {
      setChatHistory((prev) => [
        ...prev,
        { role: 'assistant', text: `Error: ${error.message || 'Unable to get assistant reply.'}` },
      ]);
    } finally {
      setChatLoading(false);
    }
  };

  const totalItems = useMemo(
    () => formData.items.reduce((sum, item) => sum + Number(item.price || 0) * Number(item.quantity || 0), 0),
    [formData.items],
  );

  const renderTabButton = (tabKey) => (
    <button
      key={tabKey}
      type="button"
      className={`tab-button ${activeTab === tabKey ? 'active' : ''}`}
      onClick={() => setActiveTab(tabKey)}
    >
      {tabLabels[tabKey]}
    </button>
  );

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <h1>Project R</h1>
          <p className="subtitle">Upload, review, save, and analyse receipts with Google Wallet integration.</p>
        </div>
        <span className="base-url">API: {API_BASE_URL}</span>
      </header>

      <nav className="tabs">{Object.keys(tabLabels).map(renderTabButton)}</nav>

      {globalMessage && (
        <div className={`global-message ${globalMessage.type}`}>{globalMessage.text}</div>
      )}

      <main className="tab-content">
        {activeTab === 'upload' && (
          <section className="card">
            <h2>Step 1 · Upload Receipt</h2>
            <p className="description">
              Upload a receipt image to extract data automatically. Review and adjust fields before storing in Firestore.
            </p>
            <form className="upload-form" onSubmit={handleExtract}>
              <label className="file-input">
                <span>Choose receipt image</span>
                <input type="file" accept="image/*" onChange={handleFileChange} />
              </label>
              {selectedFile && <p className="file-name">Selected: {selectedFile.name}</p>}
              <button type="submit" className="primary" disabled={uploading}>
                {uploading ? 'Extracting…' : 'Extract Receipt'}
              </button>
            </form>

            {extracted && (
              <div className="extracted-preview">
                <h3>Extracted Snapshot</h3>
                <pre>{JSON.stringify(extracted, null, 2)}</pre>
              </div>
            )}

            <div className="card divider">
              <h2>Step 2 · Review & Save</h2>
              <div className="form-grid">
                <label>
                  <span>Establishment</span>
                  <input
                    value={formData.establishment_name}
                    onChange={(e) => updateField('establishment_name', e.target.value)}
                    placeholder="Store or restaurant name"
                  />
                </label>
                <label>
                  <span>Type of Purchase</span>
                  <select
                    value={formData.type_of_purchase}
                    onChange={(e) => updateField('type_of_purchase', e.target.value)}
                  >
                    <option value="Restaurant">Restaurant</option>
                    <option value="Retail">Retail</option>
                    <option value="Other">Other</option>
                  </select>
                </label>
                <label>
                  <span>Purchase Date</span>
                  <input
                    value={formData.date}
                    onChange={(e) => updateField('date', e.target.value)}
                    placeholder="2025-01-31"
                  />
                </label>
                <label>
                  <span>Total (₹)</span>
                  <input
                    type="number"
                    step="0.01"
                    value={formData.total}
                    onChange={(e) => updateField('total', e.target.value)}
                  />
                </label>
              </div>

              <div className="items">
                <div className="items-header">
                  <h3>Line Items</h3>
                  <button type="button" className="secondary" onClick={addItem}>
                    Add Item
                  </button>
                </div>
                {formData.items.length === 0 && <p className="muted">No items yet. Add one above.</p>}
                {formData.items.map((item, index) => (
                  <div className="item-row" key={`item-${index}`}>
                    <input
                      value={item.name}
                      onChange={(e) => updateItem(index, 'name', e.target.value)}
                      placeholder="Item name"
                    />
                    <input
                      type="number"
                      step="0.01"
                      value={item.price}
                      onChange={(e) => updateItem(index, 'price', e.target.value)}
                      placeholder="Price"
                    />
                    <input
                      type="number"
                      min="1"
                      value={item.quantity}
                      onChange={(e) => updateItem(index, 'quantity', e.target.value)}
                      placeholder="Qty"
                    />
                    <button type="button" className="icon" onClick={() => removeItem(index)}>
                      ✕
                    </button>
                  </div>
                ))}

                {formData.items.length > 0 && (
                  <div className="items-summary">
                    <span>Calculated total from line items:</span>
                    <span>₹ {totalItems.toFixed(2)}</span>
                  </div>
                )}
              </div>

              <button
                type="button"
                className="primary"
                onClick={handleSaveReceipt}
                disabled={saving || !formData.establishment_name}
              >
                {saving ? 'Saving…' : 'Save to Firestore'}
              </button>
            </div>
          </section>
        )}

        {activeTab === 'receipts' && (
          <section className="card">
            <div className="card-header">
              <h2>Saved Receipts</h2>
              <button type="button" className="secondary" onClick={loadReceipts} disabled={loadingReceipts}>
                {loadingReceipts ? 'Refreshing…' : 'Refresh'}
              </button>
            </div>
            {receiptsError && <div className="error-banner">{receiptsError}</div>}
            {loadingReceipts && receipts.length === 0 && <p className="muted">Loading receipts…</p>}
            {!loadingReceipts && receipts.length === 0 && !receiptsError && (
              <p className="muted">No receipts stored yet. Upload one from the first tab.</p>
            )}

            <div className="receipt-grid">
              {receipts.map((receipt) => (
                <article className="receipt-card" key={receipt.id}>
                  <header>
                    <h3>{receipt.establishment_name || 'Unnamed receipt'}</h3>
                    <span className="tag">{receipt.type_of_purchase}</span>
                  </header>
                  <dl>
                    <div>
                      <dt>Date</dt>
                      <dd>{receipt.date || '—'}</dd>
                    </div>
                    <div>
                      <dt>Total</dt>
                      <dd>₹ {Number(receipt.total || 0).toFixed(2)}</dd>
                    </div>
                  </dl>
                  <h4>Items</h4>
                  <ul>
                    {(receipt.items || []).map((item, index) => (
                      <li key={`${receipt.id}-item-${index}`}>
                        <span>{item.name || 'Item'}</span>
                        <span>
                          ₹ {Number(item.price || 0).toFixed(2)} × {item.quantity || 1}
                        </span>
                      </li>
                    ))}
                    {(!receipt.items || receipt.items.length === 0) && <li className="muted">No line items</li>}
                  </ul>
                  <button
                    type="button"
                    className="primary"
                    onClick={() => handleSaveToWallet(receipt.id)}
                    disabled={walletLoading[receipt.id]}
                  >
                    {walletLoading[receipt.id] ? 'Creating Wallet Pass…' : 'Save to Google Wallet'}
                  </button>
                </article>
              ))}
            </div>
          </section>
        )}

        {activeTab === 'assistant' && (
          <section className="card assistant">
            <h2>Insights Assistant</h2>
            <p className="description">
              Ask questions about your stored receipts. The assistant pulls the latest data from Firestore.
            </p>
            <div className="chat-window">
              {chatHistory.length === 0 && <p className="muted">Start the conversation below.</p>}
              {chatHistory.map((entry, index) => (
                <div key={`chat-${index}`} className={`chat-bubble ${entry.role}`}>
                  <strong>{entry.role === 'user' ? 'You' : 'Assistant'}</strong>
                  <p>{entry.text}</p>
                </div>
              ))}
              {chatLoading && <p className="muted">Assistant is thinking…</p>}
            </div>
            <form className="chat-input" onSubmit={handleSendPrompt}>
              <textarea
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                placeholder="e.g., Summarize my restaurant spend last month"
                rows={3}
              />
              <button type="submit" className="primary" disabled={chatLoading || !chatInput.trim()}>
                {chatLoading ? 'Sending…' : 'Ask Assistant'}
              </button>
            </form>
          </section>
        )}
      </main>

      <footer className="app-footer">
        <span>Frontend connected to FastAPI backend · Google Wallet receipts demo</span>
      </footer>
    </div>
  );
}

export default App;
