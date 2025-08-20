// Service Worker for Telegram Bot Keep Alive
const CACHE_NAME = 'telegram-bot-keep-alive-v1';
const BOT_API_URL = 'https://api.telegram.org/bot8062990910:AAHOwU-KMmWu6khDxveAzcW67_tupkv6kmg/getMe';

// Install event
self.addEventListener('install', (event) => {
  self.skipWaiting();
  console.log('Service Worker installed');
});

// Activate event
self.addEventListener('activate', (event) => {
  console.log('Service Worker activated');
});

// Background sync event
self.addEventListener('sync', (event) => {
  if (event.tag === 'bg-ping') {
    event.waitUntil(doBackgroundPing());
  }
});

// Periodic background sync
self.addEventListener('periodicsync', (event) => {
  if (event.tag === 'periodic-ping') {
    event.waitUntil(doBackgroundPing());
  }
});

// Background ping function
async function doBackgroundPing() {
  try {
    const response = await fetch(BOT_API_URL);
    console.log('Background ping successful at', new Date().toLocaleTimeString());
    
    // Send message to all clients
    const clients = await self.clients.matchAll();
    clients.forEach(client => {
      client.postMessage({
        type: 'BACKGROUND_PING_SUCCESS',
        time: new Date().toLocaleTimeString()
      });
    });
  } catch (error) {
    console.error('Background ping failed:', error);
  }
}

// Listen for messages from the main thread
self.addEventListener('message', (event) => {
  if (event.data.type === 'START_BACKGROUND_PING') {
    console.log('Starting background ping');
  }
});