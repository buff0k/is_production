// File: public/js/offline_db.js (Pure IndexedDB, No `idb` dependency)

const DB_NAME = 'hourly_prod_offline_v1';
const STORE_NAME = 'pending_changes';

class OfflineManager {
  constructor() {
    this.dbPromise = this._initDB();
  }

  _initDB() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, 1);

      request.onupgradeneeded = (event) => {
        const db = event.target.result;
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          db.createObjectStore(STORE_NAME, { keyPath: 'name' });
        }
      };

      request.onsuccess = (event) => resolve(event.target.result);
      request.onerror = (event) => reject(event.target.error);
    });
  }

  async saveDoc(doc) {
    const db = await this.dbPromise;
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, 'readwrite');
      const store = tx.objectStore(STORE_NAME);

      store.put({
        ...doc,
        __offline: true,
        __timestamp: Date.now()
      });

      tx.oncomplete = () => resolve();
      tx.onerror = (event) => reject(event.target.error);
    });
  }

  async getDocs() {
    const db = await this.dbPromise;
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, 'readonly');
      const store = tx.objectStore(STORE_NAME);
      const request = store.getAll();

      request.onsuccess = () => resolve(request.result);
      request.onerror  = (event) => reject(event.target.error);
    });
  }

  async clearDoc(name) {
    const db = await this.dbPromise;
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, 'readwrite');
      const store = tx.objectStore(STORE_NAME);

      store.delete(name);

      tx.oncomplete = () => resolve();
      tx.onerror = (event) => reject(event.target.error);
    });
  }
}

window.offlineDB = new OfflineManager();
