/** Shared JSON/HTTP helpers for the fixture and chat seeders. */

export async function api(server, token, pathname, init = {}) {
   const response = await fetch(`${server.apiUrl}${pathname}`, {
      ...init,
      headers: {
         Authorization: `Bearer ${token}`,
         ...(init.body instanceof FormData
            ? {}
            : { "content-type": "application/json" }),
         ...init.headers
      }
   });
   const text = await response.text();
   let body = text;
   try {
      body = text ? JSON.parse(text) : null;
   } catch {
      // Non-JSON error payloads are kept as text for the thrown message.
   }
   if (!response.ok) {
      throw new Error(
         `Request ${init.method ?? "GET"} ${pathname} failed with ${response.status}: ${text.slice(0, 400)}`
      );
   }
   return body;
}

export function queryString(params) {
   return new URLSearchParams(params).toString();
}
