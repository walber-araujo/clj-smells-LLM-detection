## Metadata

* **Smell name:** Relying on Load-Time Side Effects
* **Expected smell location:** Top-level form
* **Affected forms:** `def`
* **Short explanation:** Evaluating side-effectful code (like network requests or DB connections) at load time makes the namespace hard to test, reload, or use in other contexts.

```Clojure
(ns app.remote-config
  (:require [clj-http.client :as http]))

; VALIDATION: SMELL START - Relying on Load-Time Side Effects
; VALIDATION: Making an HTTP request at load time
(def remote-settings
  (:body (http/get "https://config.server/api/settings" {:as :json})))
; VALIDATION: SMELL END
```
