## Metadata

* **Smell name:** Relying on Load-Time Side Effects
* **Expected smell location:** Top-level form
* **Affected forms:** `def`
* **Short explanation:** Evaluating side-effectful code (like network requests or DB connections) at load time makes the namespace hard to test, reload, or use in other contexts.

```Clojure
(ns app.auth
  (:require [clj-http.client :as http]))

; VALIDATION: SMELL START - Relying on Load-Time Side Effects
; VALIDATION: Fetching a token from an external service during namespace load
(def auth-token
  (-> (http/post "https://auth.provider/token" 
                 {:form-params {:client_id "my-app" :secret "my-secret"} :as :json})
      :body :access_token))
; VALIDATION: SMELL END
```
