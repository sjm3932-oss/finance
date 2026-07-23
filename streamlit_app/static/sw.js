/// <reference lib="webworker" />
/* Couples Wealth Master / 부자뚱 — Web Push service worker */

self.addEventListener("push", (event) => {
  let data = { title: "부자뚱", body: "새 브리핑이 도착했습니다.", url: "/" };
  try {
    if (event.data) data = { ...data, ...event.data.json() };
  } catch (_) {
    /* ignore */
  }
  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      data: { url: data.url },
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || "/";
  event.waitUntil(clients.openWindow(url));
});
