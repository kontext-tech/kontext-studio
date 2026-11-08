(function () {
   function invoke(command, args) {
      if (window.__TAURI__ && window.__TAURI__.core) {
         return window.__TAURI__.core.invoke(command, args);
      }
      return Promise.reject(new Error("Kontext desktop bridge unavailable"));
   }

   window.__KONTEXT_DESKTOP__ = {
      saveBlob: async function (blob, filename) {
         var buffer = await blob.arrayBuffer();
         var bytes = Array.from(new Uint8Array(buffer));
         return invoke("save_bytes", { name: filename, bytes: bytes });
      }
   };
})();
