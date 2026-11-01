## Metadata

* **Smell name:** Relying on Load-Time Side Effects
* **Expected smell location:** Top-level form
* **Affected forms:** `def`
* **Short explanation:** Evaluating side-effectful code (like network requests or DB connections) at load time makes the namespace hard to test, reload, or use in other contexts.

```Clojure
(ns app.config
  (:require [clojure.java.shell :as shell]))

; VALIDATION: SMELL START - Relying on Load-Time Side Effects
; VALIDATION: Reading environment variables and executing shell commands at load time
(def api-key
  (or (System/getenv "API_KEY")
      (:out (shell/sh "cat" "/secrets/api_key.txt"))))
; VALIDATION: SMELL END
```
